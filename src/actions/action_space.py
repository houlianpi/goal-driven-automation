"""Action registry for planning and compilation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionDefinition:
    """One supported semantic action."""

    name: str
    description: str
    params: dict[str, str]
    fsq_cmd: str


ACTION_SPACE: list[ActionDefinition] = [
    ActionDefinition(
        name="launch",
        description="Launch an application",
        params={"target": "bundle_id"},
        fsq_cmd="mac app launch {target}",
    ),
    ActionDefinition(
        name="tap",
        description="Click/tap an element",
        params={"target": "element_description"},
        fsq_cmd='mac element click "{target}"',
    ),
    ActionDefinition(
        name="input",
        description="Type text into an element",
        params={"target": "element", "value": "text"},
        fsq_cmd='mac element type "{target}" --text "{value}"',
    ),
    ActionDefinition(
        name="hotkey",
        description="Press keyboard shortcut",
        params={"keys": "key_combo"},
        fsq_cmd='mac input hotkey "{keys}"',
    ),
    ActionDefinition(
        name="assert",
        description="Verify a condition",
        params={"type": "assertion_type", "target": "element", "value": "expected"},
        fsq_cmd='mac assert {type} "{target}" "{value}"',
    ),
    ActionDefinition(
        name="wait",
        description="Wait for condition or time",
        params={"target": "condition_or_ms"},
        fsq_cmd="mac wait {target}",
    ),
]
