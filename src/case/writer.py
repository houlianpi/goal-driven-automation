"""YAML writer for case documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.case.schema import CaseFile, Postcondition, Step


def save_case(case: CaseFile, path: str | Path) -> None:
    """Serialize a case dataclass tree to YAML."""

    case_path = Path(path)
    case_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "goal": case.meta.goal,
            "app": case.meta.app,
            "created": case.meta.created,
            "tags": list(case.meta.tags),
            "variables": list(case.meta.variables),
        },
        "steps": [_step_to_dict(step) for step in case.steps],
        "postconditions": [_postcondition_to_dict(condition) for condition in case.postconditions],
    }

    with case_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=False, sort_keys=False)


def _step_to_dict(step: Step) -> dict[str, Any]:
    data: dict[str, Any] = {"action": step.action}
    if step.target is not None:
        data["target"] = step.target
    if step.value is not None:
        data["value"] = step.value
    if step.result is not None:
        data["result"] = step.result
    if step.timestamp is not None:
        data["timestamp"] = step.timestamp
    return data


def _postcondition_to_dict(condition: Postcondition) -> dict[str, Any]:
    data: dict[str, Any] = {
        "assert": condition.assert_type,
        "target": condition.target,
    }
    if condition.value is not None:
        data["value"] = condition.value
    return data
