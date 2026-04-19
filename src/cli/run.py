"""Replay helpers for recorded case files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.actions import ACTION_SPACE, ActionDefinition, FsqAdapter
from src.case import CaseFile, load_case


def run_case(case_path: Path) -> bool:
    """Load one case file from disk and replay it."""
    case = load_case(case_path)
    return run_loaded_case(case)


def run_loaded_case(case: CaseFile, adapter: FsqAdapter | None = None) -> bool:
    """Replay one already-loaded case."""
    runner = adapter or FsqAdapter()

    for step in case.steps:
        action = _get_action_definition(step.action)
        params = _build_step_params(step.action, step.target, step.value)
        result = runner.execute(action, params)
        if not result.success:
            return False

    return True


def run_path(path: Path) -> bool:
    """Replay one case file or every case file under a directory."""
    if path.is_dir():
        case_paths = sorted(candidate for candidate in path.rglob("*.yaml") if candidate.is_file())
        if not case_paths:
            raise FileNotFoundError(f"No case files found under: {path}")
        return all(run_case(case_path) for case_path in case_paths)

    return run_case(path)


def _get_action_definition(action_name: str) -> ActionDefinition:
    for action in ACTION_SPACE:
        if action.name == action_name:
            return action
    raise ValueError(f"Unknown action type: {action_name}")


def _build_step_params(action_name: str, target: str | None, value: str | None) -> dict[str, Any]:
    if action_name in {"launch", "tap", "wait"}:
        if target is None:
            raise ValueError(f"Action '{action_name}' requires a target.")
        return {"target": target}
    if action_name == "input":
        if target is None or value is None:
            raise ValueError("Action 'input' requires target and value.")
        return {"target": target, "value": value}
    if action_name == "hotkey":
        if target is None:
            raise ValueError("Action 'hotkey' requires keys in target.")
        return {"keys": target}
    if action_name == "assert":
        if target is None:
            raise ValueError("Action 'assert' requires a target.")
        assert_type, assert_target = _parse_assert_target(target)
        return {
            "type": assert_type,
            "target": assert_target,
            "value": value,
        }
    raise ValueError(f"Unsupported action type: {action_name}")


def _parse_assert_target(target: str) -> tuple[str, str]:
    if "::" in target:
        assert_type, assert_target = target.split("::", 1)
        normalized_type = assert_type.strip()
        normalized_target = assert_target.strip()
        if normalized_type and normalized_target:
            return normalized_type, normalized_target
    return "contains", target
