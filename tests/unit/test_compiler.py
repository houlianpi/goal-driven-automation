"""Unit tests for Compiler."""
import pytest
from src.compiler.compiler import Compiler, CompilerError, compile_step, compile_plan


class TestCompiler:
    """Test Compiler class."""
    
    def test_compile_semantic_launch_step(self):
        """Test compiling semantic launch step."""
        compiler = Compiler()
        step = {
            "step_id": "step_1",
            "action": "launch",
            "params": {"app": "Safari"},
        }
        result = compiler.compile_step(step)
        assert result["compiled_action"] == "launch_app"
        assert result["command"] == "mac app launch com.apple.Safari"
        assert result["argv"] == ["mac", "app", "launch", "com.apple.Safari"]
        assert "process_running" in result["expected_evidence"]
    
    def test_compile_shortcut_step(self):
        """Test compiling semantic shortcut step."""
        compiler = Compiler()
        step = {
            "step_id": "step_2",
            "action": "shortcut",
            "params": {"keys": ["command", "t"]},
        }
        result = compiler.compile_step(step)
        assert result["compiled_action"] == "hotkey"
        assert result["command"] == "mac input hotkey command t"
        assert result["argv"] == ["mac", "input", "hotkey", "command", "t"]

    def test_compile_quotes_spaced_text_without_literal_quotes_in_argv(self):
        """Test spaced arguments stay single argv items without embedded quote characters."""
        compiler = Compiler()
        step = {
            "step_id": "step_text",
            "action": "type",
            "params": {"text": "hello world"},
        }

        result = compiler.compile_step(step)

        assert result["argv"] == ["mac", "input", "type", "hello world"]
        assert '"hello world"' not in result["argv"]

    def test_compile_rejects_unresolved_placeholders(self, tmp_path):
        """Test unresolved registry placeholders fail compilation."""
        registry = tmp_path / "actions.yaml"
        registry.write_text(
            """
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id} {missing}
"""
        )

        compiler = Compiler(registry)
        with pytest.raises(CompilerError, match="Unresolved template placeholders"):
            compiler.compile_step({"step_id": "s1", "action": "launch", "params": {"app": "Safari"}})
    
    def test_compile_step_missing_required_arg(self):
        """Test that missing required arg raises error."""
        compiler = Compiler()
        step = {
            "step_id": "step_3",
            "action": "launch",
            "params": {},
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
                {"step_id": "s1", "action": "launch", "params": {"app": "Safari"}},
                {"step_id": "s2", "action": "wait", "params": {"seconds": 1}},
                {"step_id": "s3", "action": "shortcut", "params": {"keys": ["return"]}},
            ],
        }
        result = compiler.compile_plan(plan)
        assert result["compiled"] is True
        assert len(result["steps"]) == 3
        assert all("command" in s for s in result["steps"])
    
    def test_compile_assert_requires_locator(self):
        """Test semantic assert requires compiler-resolvable target."""
        compiler = Compiler()
        step = {
            "step_id": "step_5",
            "action": "assert",
            "params": {"condition": "url.contains('example.com')"},
        }
        with pytest.raises(CompilerError, match="requires 'locator' or 'selector'"):
            compiler.compile_step(step)


class TestHelperFunctions:
    """Test module-level helper functions."""
    
    def test_compile_step_function(self):
        """Test compile_step helper."""
        step = {"step_id": "s1", "action": "launch", "params": {"app": "Safari"}}
        result = compile_step(step)
        assert "command" in result
    
    def test_compile_plan_function(self):
        """Test compile_plan helper."""
        plan = {
            "plan_id": "p1",
            "steps": [{"step_id": "s1", "action": "launch", "params": {"app": "Safari"}}],
        }
        result = compile_plan(plan)
        assert result["compiled"] is True
