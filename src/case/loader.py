"""YAML loader for case documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.case.schema import CaseFile, CaseMeta, Postcondition, Step


def load_case(path: str | Path) -> CaseFile:
    """Load a case YAML file from disk into dataclasses."""

    case_path = Path(path)
    with case_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise TypeError("case file root must be a mapping")

    return parse_case_data(data)


def parse_case_data(data: dict[str, Any]) -> CaseFile:
    """Parse an in-memory YAML mapping into a case dataclass tree."""
    return _parse_case_file(data)


def _parse_case_file(data: dict[str, Any]) -> CaseFile:
    meta_data = _require_mapping(data, "meta")
    steps_data = _require_list(data.get("steps", []), "steps")
    postconditions_data = _require_list(data.get("postconditions", []), "postconditions")

    meta = CaseMeta(
        goal=_require_str(meta_data, "goal", scope="meta"),
        app=_require_str(meta_data, "app", scope="meta"),
        created=_require_str(meta_data, "created", scope="meta"),
        tags=_require_str_list(meta_data.get("tags", []), "tags", scope="meta"),
        variables=_require_str_list(meta_data.get("variables", []), "variables", scope="meta"),
    )

    steps = [
        Step(
            action=_require_str(step_data, "action", scope=f"steps[{index}]"),
            target=_optional_str(step_data, "target", scope=f"steps[{index}]"),
            value=_optional_str(step_data, "value", scope=f"steps[{index}]"),
            result=_optional_str(step_data, "result", scope=f"steps[{index}]"),
            timestamp=_optional_str(step_data, "timestamp", scope=f"steps[{index}]"),
        )
        for index, step_data in enumerate(_iter_mappings(steps_data, "steps"))
    ]

    postconditions = [
        Postcondition(
            assert_type=_require_str(condition_data, "assert", scope=f"postconditions[{index}]"),
            target=_require_str(condition_data, "target", scope=f"postconditions[{index}]"),
            value=_optional_str(condition_data, "value", scope=f"postconditions[{index}]"),
        )
        for index, condition_data in enumerate(_iter_mappings(postconditions_data, "postconditions"))
    ]

    return CaseFile(meta=meta, steps=steps, postconditions=postconditions)


def _iter_mappings(items: list[Any], field_name: str) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(f"{field_name}[{index}] must be a mapping")
        mappings.append(item)
    return mappings


def _require_mapping(data: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = data.get(field_name)
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a mapping")
    return value


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")
    return value


def _require_str(data: dict[str, Any], field_name: str, *, scope: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{scope}.{field_name} must be a non-empty string")
    return value


def _optional_str(data: dict[str, Any], field_name: str, *, scope: str) -> str | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{scope}.{field_name} must be a string when provided")
    return value


def _require_str_list(value: Any, field_name: str, *, scope: str) -> list[str]:
    items = _require_list(value, f"{scope}.{field_name}")
    strings: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item:
            raise TypeError(f"{scope}.{field_name}[{index}] must be a non-empty string")
        strings.append(item)
    return strings
