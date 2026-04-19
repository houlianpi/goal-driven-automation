"""Prompt builder for planning the next UI action."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from typing import Any, Mapping, Sequence


def build_planning_prompt(
    goal: str,
    screenshot_desc: str,
    ui_tree: Any,
    history: Sequence[Mapping[str, Any]],
    action_space: Sequence[Any],
) -> str:
    """Build the planner prompt for the next action decision."""
    action_space_block = _to_json_block([_normalize_action(action) for action in action_space])
    history_block = _to_json_block(list(history))
    ui_tree_block = _stringify_context(ui_tree)

    return """You are a macOS UI automation planner.
Your task is to choose the single best next action for advancing the user goal.

Rules:
- Use only one action from the provided action space.
- Base the decision on the goal, screenshot description, UI tree, and recent history.
- Keep <thought> concise and grounded in the current UI state.
- Keep <log> short and execution-oriented.
- Populate <value> only when the chosen action requires it. Otherwise return an empty tag.
- Set <should_continue>true</should_continue> when more actions are still needed after this step.
- Set <should_continue>false</should_continue> only when the goal is complete or no further safe action should run.
- Return XML only. Do not include Markdown fences or extra prose.

Goal:
{goal}

Screenshot Description:
{screenshot_desc}

UI Tree:
{ui_tree_block}

Recent History:
{history_block}

Available Action Space:
{action_space_block}

Return exactly this XML structure:
<response>
  <thought>Reason about the current UI state and why this action is next.</thought>
  <log>Short execution log message</log>
  <action>
    <type>launch|tap|input|hotkey|assert|wait</type>
    <target>Element or target description</target>
    <value>Optional action value</value>
  </action>
  <should_continue>true</should_continue>
</response>
""".format(
        goal=goal.strip(),
        screenshot_desc=screenshot_desc.strip(),
        ui_tree_block=ui_tree_block,
        history_block=history_block,
        action_space_block=action_space_block,
    )


def _normalize_action(action: Any) -> Any:
    """Normalize action objects for prompt serialization."""
    if is_dataclass(action):
        return asdict(action)
    if isinstance(action, Mapping):
        return dict(action)
    return str(action)


def _stringify_context(value: Any) -> str:
    """Serialize arbitrary prompt context into readable text."""
    if isinstance(value, str):
        return value.strip()
    return _to_json_block(value)


def _to_json_block(value: Any) -> str:
    """Render context values as indented JSON for the prompt."""
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
