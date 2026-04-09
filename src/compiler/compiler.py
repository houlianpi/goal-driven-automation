"""
Plan IR Compiler - Compiles Plan IR steps into executable CLI commands.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


class CompilerError(Exception):
    """Raised when compilation fails."""
    pass


class Compiler:
    """Compiles Plan IR steps into fsq-mac CLI commands."""
    
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
        
        if action_name not in self.registry:
            raise CompilerError(f"Unknown action: {action_name}")
        
        action_def = self.registry[action_name]
        args = step.get("args", {})
        
        # Validate required args
        for arg_name, arg_spec in action_def.get("args", {}).items():
            if arg_spec.get("required", False) and arg_name not in args:
                raise CompilerError(f"Missing required arg '{arg_name}' for action '{action_name}'")
        
        # Fill in defaults
        for arg_name, arg_spec in action_def.get("args", {}).items():
            if arg_name not in args and "default" in arg_spec:
                args[arg_name] = arg_spec["default"]
        
        # Compile template
        command = self._compile_template(action_def["compile_to"], args)
        
        return {
            **step,
            "command": command,
            "expected_evidence": action_def.get("expected_evidence", []),
            "retry_policy": step.get("retry_policy", action_def.get("default_retry", {})),
        }
    
    def _compile_template(self, template: str, args: Dict[str, Any]) -> str:
        """Compile command template with arguments."""
        result = template
        for key, value in args.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                if isinstance(value, list):
                    # Handle array args (e.g., hotkey keys)
                    value_str = " ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                result = result.replace(placeholder, value_str)
        return result
    
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
