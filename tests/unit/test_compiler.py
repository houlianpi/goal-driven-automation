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
        # locator_role → --role, locator_text → --name; legacy selector → --id
        # app context metadata is not in argv
        assert "--role" in result["argv"]
        assert "--name" in result["argv"]
        assert "Microsoft Edge" not in result["argv"]

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


class TestV030Compatibility:
    """Tests for fsq-mac v0.3.0 flag-based locator compilation."""

    def test_element_click_with_role_and_name(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_click",
            "args": {"role": "AXButton", "name": "OK"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "click", "--role", "AXButton", "--name", "OK"]

    def test_element_click_with_ref(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_click",
            "args": {"ref": "e0"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "click", "e0"]

    def test_element_type_with_text_and_locator(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_type",
            "args": {"role": "AXTextField", "text": "hello world"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "type", "hello world", "--role", "AXTextField"]

    def test_element_type_with_ref(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_type",
            "args": {"ref": "e3", "text": "hello"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "type", "e3", "hello"]

    def test_menu_click_from_array(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "menu_select",
            "args": {"menu_path": ["File", "Open"]},
        }
        result = compiler.compile_step(step)
        assert result["compiled_action"] == "menu_click"
        assert result["argv"] == ["mac", "menu", "click", "File > Open"]

    def test_menu_click_from_string(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "menu_click",
            "args": {"menu_path": "File > Save"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "menu", "click", "File > Save"]

    def test_activate_app_uses_mac_app_activate(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "activate_app",
            "args": {"bundle_id": "com.apple.Safari"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "app", "activate", "com.apple.Safari"]

    def test_terminate_app_includes_allow_dangerous(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "terminate_app",
            "args": {"bundle_id": "com.apple.Safari"},
        }
        result = compiler.compile_step(step)
        assert "--allow-dangerous" in result["argv"]

    def test_window_focus_uses_index(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "window_focus",
            "args": {"index": 0},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "window", "focus", "0"]

    def test_assert_visible_with_role_name(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "assert_visible",
            "args": {"role": "AXButton", "name": "OK"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "assert", "visible", "--role", "AXButton", "--name", "OK"]

    def test_assert_text_with_expected(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "assert_text",
            "args": {"expected": "Hello", "name": "label1"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "assert", "text", "Hello", "--name", "label1"]

    def test_assert_app_running(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "assert_app_running",
            "args": {"bundle_id": "com.apple.Safari"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "assert", "app-running", "com.apple.Safari"]

    def test_wait_element_with_positional_locator(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "wait_for_element",
            "args": {"locator": "Save", "timeout_ms": 5000},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == [
            "mac", "wait", "element",
            "Save",
            "--timeout", "5000",
        ]

    def test_capture_ui_tree_no_output_flag(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "capture",
            "params": {"type": "ui_tree"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "capture", "ui-tree"]
        assert "--output" not in result["argv"]

    def test_click_legacy_locator_maps_to_id_flag(self):
        """Legacy Plan IR click with default accessibility_id strategy maps to --id flag."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "click",
            "params": {"selector": "Submit"},
        }
        result = compiler.compile_step(step)
        assert result["compiled_action"] == "element_click"
        assert "--id" in result["argv"]
        assert "Submit" in result["argv"]

    def test_retry_policy_uses_max_attempts_key(self):
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "launch",
            "params": {"app": "Safari"},
        }
        result = compiler.compile_step(step)
        assert "max_attempts" in result["retry_policy"]

    def test_element_find_uses_positional_locator(self):
        """element find takes a required positional locator, not flag-based."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_find",
            "args": {"locator": "Save"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "find", "Save"]

    def test_element_find_first_match_true_emits_flag(self):
        """element find should emit --first-match when requested."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_find",
            "args": {"locator": "Save", "first_match": True},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "find", "Save", "--first-match"]

    def test_element_drag_uses_two_positional_refs(self):
        """element drag takes source and target as positional args."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_drag",
            "args": {"source": "e0", "target": "e5"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "drag", "e0", "e5"]

    def test_capture_screenshot_uses_positional_path(self):
        """capture screenshot takes a positional path, not --output flag."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "capture",
            "params": {"type": "screenshot"},
        }
        result = compiler.compile_step(step)
        assert "--output" not in result["argv"]
        assert result["argv"][0:3] == ["mac", "capture", "screenshot"]

    def test_click_legacy_xpath_maps_to_xpath_flag(self):
        """Legacy xpath strategy maps to --xpath flag."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "click",
            "params": {"selector": "//button[@id='submit']", "strategy": "xpath"},
        }
        result = compiler.compile_step(step)
        assert "--xpath" in result["argv"]
        assert "//button[@id='submit']" in result["argv"]

    def test_wait_window_takes_positional_title(self):
        """wait window requires a positional title arg."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "wait_window",
            "args": {"title": "Main Window", "timeout_ms": 5000},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "wait", "window", "Main Window", "--timeout", "5000"]

    def test_element_scroll_direction_is_positional(self):
        """element scroll takes direction as positional, not --direction flag."""
        compiler = Compiler()
        step = {
            "step_id": "s1",
            "action": "element_scroll",
            "args": {"direction": "down", "role": "AXScrollArea"},
        }
        result = compiler.compile_step(step)
        assert result["argv"] == ["mac", "element", "scroll", "down", "--role", "AXScrollArea"]
        assert "--direction" not in result["argv"]
