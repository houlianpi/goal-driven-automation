"""Unit tests for prompt building and XML parsing."""

from __future__ import annotations

import pytest

from src.actions.action_space import ACTION_SPACE
from src.llm.parser import parse_xml_response
from src.llm.prompt import build_planning_prompt


def test_build_planning_prompt_includes_core_context_and_xml_contract():
    """Prompt should include the planning inputs and response schema."""
    prompt = build_planning_prompt(
        goal="登录 GitHub",
        screenshot_desc="Safari showing the GitHub home page",
        ui_tree={"window": "GitHub", "buttons": ["Sign in"]},
        history=[{"action": "launch", "result": "success"}],
        action_space=ACTION_SPACE,
    )

    assert "登录 GitHub" in prompt
    assert "Safari showing the GitHub home page" in prompt
    assert "launch|tap|input|hotkey|assert|wait" in prompt
    assert "<response>" in prompt
    assert '"name": "tap"' in prompt


def test_parse_xml_response_returns_structured_result():
    """Valid planner XML should parse into a dataclass."""
    xml = """
    <response>
      <thought>用户想要登录 GitHub，当前应点击 Sign in。</thought>
      <log>Clicking Sign in button</log>
      <action>
        <type>tap</type>
        <target>Sign in</target>
        <value></value>
      </action>
      <should_continue>true</should_continue>
    </response>
    """

    parsed = parse_xml_response(xml)

    assert parsed.thought.startswith("用户想要登录 GitHub")
    assert parsed.log == "Clicking Sign in button"
    assert parsed.action_type == "tap"
    assert parsed.action_target == "Sign in"
    assert parsed.action_value == ""
    assert parsed.should_continue is True


def test_parse_xml_response_extracts_response_from_markdown_fence():
    """Parser should tolerate extra wrapper text around the XML block."""
    xml = """
    ```xml
    <response>
      <thought>Done</thought>
      <log>Waiting</log>
      <action>
        <type>wait</type>
        <target>1000</target>
        <value></value>
      </action>
      <should_continue>false</should_continue>
    </response>
    ```
    """

    parsed = parse_xml_response(xml)

    assert parsed.action_type == "wait"
    assert parsed.should_continue is False


def test_parse_xml_response_rejects_invalid_boolean():
    """Boolean contract violations should raise a helpful error."""
    xml = """
    <response>
      <thought>Test</thought>
      <log>Test</log>
      <action>
        <type>tap</type>
        <target>Sign in</target>
        <value></value>
      </action>
      <should_continue>maybe</should_continue>
    </response>
    """

    with pytest.raises(ValueError, match="Invalid boolean"):
        parse_xml_response(xml)


def test_parse_xml_response_rejects_unsupported_action_type():
    """Action type must stay inside the declared architecture contract."""
    xml = """
    <response>
      <thought>Test</thought>
      <log>Test</log>
      <action>
        <type>scroll</type>
        <target>down</target>
        <value></value>
      </action>
      <should_continue>true</should_continue>
    </response>
    """

    with pytest.raises(ValueError, match="Unsupported action type"):
        parse_xml_response(xml)


def test_parse_xml_response_rejects_missing_required_fields():
    """Required tags must be present and non-empty."""
    xml = """
    <response>
      <thought></thought>
      <log>Test</log>
      <action>
        <type>tap</type>
        <target>Sign in</target>
        <value></value>
      </action>
      <should_continue>true</should_continue>
    </response>
    """

    with pytest.raises(ValueError, match="Missing required <thought>"):
        parse_xml_response(xml)
