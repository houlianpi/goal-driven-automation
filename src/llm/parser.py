"""XML parser for LLM planning responses."""

from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET


_RESPONSE_PATTERN = re.compile(r"<response\b[\s\S]*?</response>", re.IGNORECASE)
_SUPPORTED_ACTION_TYPES = {"launch", "tap", "input", "hotkey", "assert", "wait"}


@dataclass(frozen=True)
class PlanningResponse:
    """Structured planning decision returned by the LLM."""

    thought: str
    log: str
    action_type: str
    action_target: str
    action_value: str
    should_continue: bool


def parse_xml_response(xml_str: str) -> PlanningResponse:
    """Parse a planner XML response into structured fields."""
    candidate = _extract_response_block(xml_str)

    try:
        root = ET.fromstring(candidate)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML response: {exc}") from exc

    if root.tag != "response":
        raise ValueError("Expected root element <response>.")

    action = root.find("action")
    if action is None:
        raise ValueError("Missing required <action> element.")

    action_type = _require_text(action, "type")
    if action_type not in _SUPPORTED_ACTION_TYPES:
        raise ValueError(f"Unsupported action type: {action_type}")

    action_target = _require_text(action, "target")

    return PlanningResponse(
        thought=_require_text(root, "thought"),
        log=_require_text(root, "log"),
        action_type=action_type,
        action_target=action_target,
        action_value=_optional_text(action, "value"),
        should_continue=_parse_bool(_require_text(root, "should_continue")),
    )


def _extract_response_block(xml_str: str) -> str:
    """Extract the XML response body from model output."""
    stripped = xml_str.strip()
    match = _RESPONSE_PATTERN.search(stripped)
    if match is None:
        raise ValueError("No <response>...</response> block found in planner output.")
    return match.group(0)


def _require_text(parent: ET.Element, tag: str) -> str:
    """Return normalized non-empty text for a required child tag."""
    value = _optional_text(parent, tag)
    if not value:
        raise ValueError(f"Missing required <{tag}> value.")
    return value


def _optional_text(parent: ET.Element, tag: str) -> str:
    """Return normalized text for an optional child tag."""
    child = parent.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_bool(value: str) -> bool:
    """Parse the XML boolean text for should_continue."""
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid boolean value for <should_continue>: {value}")
