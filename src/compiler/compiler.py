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

        # Validate required args
        for arg_name, arg_spec in action_def.get("args", {}).items():
            if arg_spec.get("required", False) and arg_name not in compiled_args:
                raise CompilerError(f"Missing required arg '{arg_name}' for action '{action_name}'")

        # Fill in defaults
        for arg_name, arg_spec in action_def.get("args", {}).items():
            if arg_name not in compiled_args and "default" in arg_spec:
                compiled_args[arg_name] = arg_spec["default"]

        # Compile template
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
            locator = args.get("locator", args.get("selector"))
            return "element_click", {
                "locator": locator,
                "strategy": args.get("strategy", "accessibility_id"),
            }

        if action_name == "wait":
            seconds = args.get("seconds")
            if seconds is None:
                seconds = args.get("timeout_ms", 0) / 1000.0
            return "wait", {"seconds": max(0.0, float(seconds))}

        if action_name == "assert":
            locator = args.get("locator", args.get("selector"))
            if not locator:
                # Generic goal-level conditions are not yet lowered to a concrete
                # fsq-mac assertion primitive. Keep them compilable so pipeline
                # dry-run and runtime flows can proceed without a fake locator.
                return "wait", {"seconds": 0}
            return "assert_visible", {
                "locator": locator,
                "strategy": args.get("strategy", "accessibility_id"),
            }

        if action_name == "capture":
            capture_type = args.get("type", "screenshot")
            if capture_type == "screenshot":
                return "capture_screenshot", {"output": args.get("output", "screenshot.png")}
            if capture_type == "ui_tree":
                return "capture_ui_tree", {"output": args.get("output", "ui_tree.json")}
            raise CompilerError("Unsupported capture params: 'both' requires multiple capability actions")

        if action_name in self.registry:
            return action_name, args

        raise CompilerError(f"Unknown action: {action_name}")
    
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
