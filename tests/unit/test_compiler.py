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
        assert result["command"] == "mac input hotkey command+t"
        assert result["argv"] == ["mac", "input", "hotkey", "command+t"]

    def test_compile_quotes_spaced_text_without_literal_quotes_in_argv(self):
        """Test spaced arguments stay single argv items without embedded quote characters."""
        compiler = Compiler()
        step = {
            "step_id": "step_text",
            "action": "type",
            "params": {"text": "hello world"},
        }

        result = compiler.compile_step(step)

        assert result["argv"] == ["mac", "input", "text", "hello world"]
        assert '"hello world"' not in result["argv"]

    def test_compile_type_step_ignores_context_metadata_for_command_generation(self):
        """Test context metadata on type steps does not change compiled fsq-mac command."""
        compiler = Compiler()
        step = {
            "step_id": "step_text_context",
            "action": "type",
            "params": {
                "text": "hello world",
                "app": "Safari",
                "requires_focused_target": True,
            },
        }

        result = compiler.compile_step(step)

        assert result["compiled_action"] == "type_text"
        assert result["argv"] == ["mac", "input", "text", "hello world"]

    def test_compile_click_step_ignores_context_metadata_for_command_generation(self):
        """Test context metadata on click steps does not change compiled fsq-mac command."""
        compiler = Compiler()
        step = {
            "step_id": "step_click_context",
            "action": "click",
            "params": {
                "selector": "Submit",
                "app": "Microsoft Edge",
                "locator_text": "Submit",
                "locator_role": "button",
            },
        }

        result = compiler.compile_step(step)

        assert result["compiled_action"] == "element_click"
        assert result["argv"] == ["mac", "element", "click", "Submit", "--strategy", "accessibility_id"]

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
    
    def test_compile_assert_without_locator_falls_back_to_non_blocking_wait(self):
        """Test condition-only semantic assert still compiles for generic goal verification."""
        compiler = Compiler()
        step = {
            "step_id": "step_5",
            "action": "assert",
            "params": {"condition": "url.contains('example.com')"},
        }
        result = compiler.compile_step(step)

        assert result["compiled_action"] == "wait"
        assert result["argv"] == ["sleep", "0"]


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
