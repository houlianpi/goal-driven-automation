"""
Plan IR Compiler - Compiles Plan IR steps into executable CLI commands.
"""
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


class CompilerError(Exception):
    """Raised when compilation fails."""
    pass


class Compiler:
    """Compiles Plan IR steps into fsq-mac CLI commands."""

    APP_BUNDLE_IDS = {
        "Microsoft Edge": "com.microsoft.edgemac",
        "Safari": "com.apple.Safari",
        "Google Chrome": "com.google.Chrome",
        "Firefox": "org.mozilla.firefox",
        "Finder": "com.apple.finder",
        "Terminal": "com.apple.Terminal",
        "Notes": "com.apple.Notes",
        "Mail": "com.apple.mail",
    }

    # Element actions that use flag-based locators (via __element_argv__)
    _ELEMENT_ACTIONS = {
        "element_click": "click",
        "element_right_click": "right-click",
        "element_double_click": "double-click",
        "element_type": "type",
        "element_scroll": "scroll",
        "element_hover": "hover",
    }

    # Assert actions that use flag-based locators
    _ASSERT_ACTIONS = {
        "assert_visible": "visible",
        "assert_enabled": "enabled",
        "assert_text": "text",
        "assert_value": "value",
    }

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize compiler with action registry."""
        if registry_path is None:
            registry_path = Path(__file__).parent.parent.parent / "registry" / "actions.yaml"
        self.registry = self._load_registry(registry_path)

    def _load_registry(self, path: Path) -> Dict[str, Any]:
        """Load action registry from YAML file."""
        if not path.exists():
            raise CompilerError(f"Registry not found: {path}")
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("actions", {})

    def compile_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compile a single Plan IR step into CLI command.

        Args:
            step: Plan IR step with action and args

        Returns:
            Compiled step with 'command' field added
        """
        action_name = step.get("action")
        if not action_name:
            raise CompilerError("Step missing 'action' field")

        capability_action, compiled_args = self._resolve_action(step)
        action_def = self.registry[capability_action]

        # Validate required args (skip for element/assert actions whose args are all optional locators)
        compile_to = action_def.get("compile_to", "")
        if compile_to not in ("__element_argv__", "__assert_argv__"):
            for arg_name, arg_spec in action_def.get("args", {}).items():
                if arg_spec.get("required", False) and arg_name not in compiled_args:
                    raise CompilerError(f"Missing required arg '{arg_name}' for action '{action_name}'")

        # Fill in defaults
        for arg_name, arg_spec in action_def.get("args", {}).items():
            if arg_name not in compiled_args and "default" in arg_spec:
                compiled_args[arg_name] = arg_spec["default"]

        # Build command based on compile_to marker
        if compile_to == "__element_argv__":
            verb = self._ELEMENT_ACTIONS[capability_action]
            argv = self._build_element_argv(verb, compiled_args)
            command = " ".join(shlex.quote(a) for a in argv)
        elif compile_to == "__assert_argv__":
            verb = self._ASSERT_ACTIONS[capability_action]
            argv = self._build_assert_argv(verb, compiled_args)
            command = " ".join(shlex.quote(a) for a in argv)
        else:
            command = self._compile_template(action_def["compile_to"], compiled_args)
            argv = self._compile_argv(command)

        return {
            **step,
            "compiled_action": capability_action,
            "command": command,
            "argv": argv,
            "expected_evidence": action_def.get("expected_evidence", []),
            "retry_policy": step.get("retry_policy", action_def.get("default_retry", {})),
        }

    def _build_element_argv(self, verb: str, args: Dict[str, Any]) -> List[str]:
        """Build argv for element commands using v0.3.0 flag-based locators."""
        argv = ["mac", "element", verb]

        # Ref-based locators (e.g. "e0") go as positional arg
        if args.get("ref"):
            argv.append(str(args["ref"]))

        # For element type, text is a positional arg
        if verb == "type" and args.get("text"):
            argv.append(str(args["text"]))

        # Scroll direction is positional (not a flag)
        if verb == "scroll" and args.get("direction"):
            argv.append(str(args["direction"]))

        # Flag-based locators
        if args.get("role"):
            argv += ["--role", str(args["role"])]
        if args.get("name"):
            argv += ["--name", str(args["name"])]
        if args.get("label"):
            argv += ["--label", str(args["label"])]
        if args.get("id"):
            argv += ["--id", str(args["id"])]
        if args.get("xpath"):
            argv += ["--xpath", str(args["xpath"])]

        return argv

    def _build_assert_argv(self, verb: str, args: Dict[str, Any]) -> List[str]:
        """Build argv for assert commands using v0.3.0 flag-based locators."""
        argv = ["mac", "assert", verb]

        # For text/value assertions, expected value is a positional arg
        if verb in ("text", "value") and args.get("expected"):
            argv.append(str(args["expected"]))

        # Ref-based locator
        if args.get("ref"):
            argv.append(str(args["ref"]))

        # Flag-based locators
        if args.get("role"):
            argv += ["--role", str(args["role"])]
        if args.get("name"):
            argv += ["--name", str(args["name"])]
        if args.get("label"):
            argv += ["--label", str(args["label"])]
        if args.get("id"):
            argv += ["--id", str(args["id"])]

        return argv

    def _resolve_action(self, step: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Resolve a semantic Plan IR action to a registry action."""
        action_name = step["action"]
        args = dict(step.get("args", step.get("params", {})))

        if action_name == "launch":
            app_name = args.get("app")
            if not app_name:
                raise CompilerError("Missing required arg 'app' for action 'launch'")
            return "launch_app", {"bundle_id": self.APP_BUNDLE_IDS.get(app_name, app_name)}

        if action_name == "shortcut":
            keys = args.get("keys", [])
            if isinstance(keys, list):
                combo = "+".join(str(key) for key in keys)
            else:
                combo = str(keys)
            return "hotkey", {"combo": combo}

        if action_name == "type":
            return "type_text", {"text": args.get("text", "")}

        if action_name == "click":
            return "element_click", self._resolve_element_locator(args)

        if action_name == "wait":
            seconds = args.get("seconds")
            if seconds is None:
                seconds = args.get("timeout_ms", 0) / 1000.0
            return "wait", {"seconds": max(0.0, float(seconds))}

        if action_name == "assert":
            locator = args.get("locator", args.get("selector"))
            if not locator:
                return "wait", {"seconds": 0}
            resolved = self._resolve_element_locator(args)
            return "assert_visible", resolved

        if action_name == "capture":
            capture_type = args.get("type", "screenshot")
            if capture_type == "screenshot":
                return "capture_screenshot", {"path": args.get("path", "./screenshot.png")}
            if capture_type == "ui_tree":
                return "capture_ui_tree", {}
            raise CompilerError("Unsupported capture params: 'both' requires multiple capability actions")

        # Legacy: menu_select → menu_click
        if action_name == "menu_select":
            menu_path = args.get("menu_path", [])
            if isinstance(menu_path, list):
                menu_path = " > ".join(str(item) for item in menu_path)
            return "menu_click", {"menu_path": menu_path}

        if action_name in self.registry:
            return action_name, args

        raise CompilerError(f"Unknown action: {action_name}")

    def _resolve_element_locator(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Plan IR element params to v0.3.0 flag-based locator args.

        Supports both new-style params (role, name, label, id, ref) and
        legacy params (locator + strategy).
        """
        result = {}

        # Pass through new-style params directly
        for key in ("ref", "role", "name", "label", "id"):
            if key in args and args[key]:
                result[key] = args[key]

        # Legacy: locator + strategy → flag-based
        if not result and args.get("locator", args.get("selector")):
            locator = args.get("locator", args.get("selector"))
            strategy = args.get("strategy", "accessibility_id")
            if strategy == "accessibility_id":
                result["id"] = locator
            elif strategy == "xpath":
                result["xpath"] = locator
            else:
                result["name"] = locator

        # Carry over locator metadata from goal parser
        if args.get("locator_role"):
            result["role"] = args["locator_role"]
        if args.get("locator_text"):
            result["name"] = args["locator_text"]

        return result

    def _compile_template(self, template: str, args: Dict[str, Any]) -> str:
        """Compile command template with arguments."""
        result = template
        for key, value in args.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                if isinstance(value, list):
                    value_str = " ".join(shlex.quote(str(v)) for v in value)
                else:
                    value_str = shlex.quote(str(value))
                result = result.replace(placeholder, value_str)
        unresolved = re.findall(r"\{[^{}]+\}", result)
        if unresolved:
            raise CompilerError(f"Unresolved template placeholders: {', '.join(unresolved)}")
        return result

    def _compile_argv(self, command: str) -> List[str]:
        """Convert a rendered command string into structured argv."""
        try:
            return shlex.split(command)
        except ValueError as exc:
            raise CompilerError(f"Failed to split compiled command into argv: {exc}") from exc

    def compile_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compile entire Plan IR into executable plan.

        Args:
            plan: Plan IR with steps

        Returns:
            Compiled plan with all steps having 'command' fields
        """
        compiled_steps = []
        for step in plan.get("steps", []):
            compiled_steps.append(self.compile_step(step))

        return {
            **plan,
            "steps": compiled_steps,
            "compiled": True,
        }


def load_registry(path: str) -> Dict[str, Any]:
    """Load action registry from path."""
    compiler = Compiler(Path(path))
    return compiler.registry


def compile_step(step: Dict[str, Any], registry_path: Optional[str] = None) -> Dict[str, Any]:
    """Compile a single step."""
    path = Path(registry_path) if registry_path else None
    compiler = Compiler(path)
    return compiler.compile_step(step)


def compile_plan(plan: Dict[str, Any], registry_path: Optional[str] = None) -> Dict[str, Any]:
    """Compile entire plan."""
    path = Path(registry_path) if registry_path else None
    compiler = Compiler(path)
    return compiler.compile_plan(plan)
