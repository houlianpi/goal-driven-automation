"""Unit tests for Compiler."""
import pytest
from src.compiler.compiler import Compiler, CompilerError, compile_step, compile_plan


class TestCompiler:
    """Test Compiler class."""
    
    def test_compile_simple_step(self):
        """Test compiling a simple step."""
        compiler = Compiler()
        step = {
            "step_id": "step_1",
            "action": "session_start",
            "args": {},
        }
        result = compiler.compile_step(step)
        assert result["command"] == "mac session start"
        assert "session_id" in result["expected_evidence"]
    
    def test_compile_step_with_args(self):
        """Test compiling step with arguments."""
        compiler = Compiler()
        step = {
            "step_id": "step_2",
            "action": "activate_app",
            "args": {"app_name": "Safari"},
        }
        result = compiler.compile_step(step)
        assert "Safari" in result["command"]
        assert "activate" in result["command"]
    
    def test_compile_step_missing_required_arg(self):
        """Test that missing required arg raises error."""
        compiler = Compiler()
        step = {
            "step_id": "step_3",
            "action": "activate_app",
            "args": {},  # Missing app_name
        }
        with pytest.raises(CompilerError, match="Missing required arg"):
            compiler.compile_step(step)
    
    def test_compile_unknown_action(self):
        """Test that unknown action raises error."""
        compiler = Compiler()
        step = {
            "step_id": "step_4",
            "action": "unknown_action",
            "args": {},
        }
        with pytest.raises(CompilerError, match="Unknown action"):
            compiler.compile_step(step)
    
    def test_compile_plan(self):
        """Test compiling entire plan."""
        compiler = Compiler()
        plan = {
            "plan_id": "test_plan",
            "steps": [
                {"step_id": "s1", "action": "session_start", "args": {}},
                {"step_id": "s2", "action": "wait", "args": {"ms": 1000}},
                {"step_id": "s3", "action": "session_end", "args": {}},
            ],
        }
        result = compiler.compile_plan(plan)
        assert result["compiled"] is True
        assert len(result["steps"]) == 3
        assert all("command" in s for s in result["steps"])
    
    def test_compile_hotkey(self):
        """Test compiling hotkey action with array args."""
        compiler = Compiler()
        step = {
            "step_id": "step_5",
            "action": "hotkey",
            "args": {"keys": ["cmd", "t"]},
        }
        result = compiler.compile_step(step)
        assert "cmd t" in result["command"]


class TestHelperFunctions:
    """Test module-level helper functions."""
    
    def test_compile_step_function(self):
        """Test compile_step helper."""
        step = {"step_id": "s1", "action": "session_start", "args": {}}
        result = compile_step(step)
        assert "command" in result
    
    def test_compile_plan_function(self):
        """Test compile_plan helper."""
        plan = {
            "plan_id": "p1",
            "steps": [{"step_id": "s1", "action": "session_start", "args": {}}],
        }
        result = compile_plan(plan)
        assert result["compiled"] is True
