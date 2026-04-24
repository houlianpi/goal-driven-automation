"""Replay helpers for recorded case files."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from src.actions import ACTION_SPACE, ActionDefinition, FsqAdapter
from src.case import CaseFile, load_case
from src.report.html import CaseResult, StepResult


def run_case(case_path: Path) -> bool:
    """Load one case file from disk and replay it."""
    return run_case_result(case_path).success


def run_case_result(case_path: Path, adapter: FsqAdapter | None = None) -> CaseResult:
    """Load one case file from disk and replay it with structured results."""
    case = load_case(case_path)
    return execute_loaded_case(case, case_path=case_path, adapter=adapter)


def run_loaded_case(case: CaseFile, adapter: FsqAdapter | None = None) -> bool:
    """Replay one already-loaded case."""
    return execute_loaded_case(case, adapter=adapter).success


def execute_loaded_case(
    case: CaseFile,
    *,
    case_path: Path | None = None,
    adapter: FsqAdapter | None = None,
) -> CaseResult:
    """Replay one already-loaded case and return structured per-step results."""
    runner = adapter or FsqAdapter()
    started_at = time.perf_counter()
    step_results: list[StepResult] = []
    case_error: str | None = None

    for step in case.steps:
        try:
            action = _get_action_definition(step.action)
            params = _build_step_params(step.action, step.target, step.value)
            result = runner.execute(action, params)
            error = getattr(result, "error", "") or None
            duration_ms = int(getattr(result, "duration_ms", 0))
            step_results.append(
                StepResult(
                    action=step.action,
                    target=step.target,
                    value=step.value,
                    success=result.success,
                    error=error,
                    duration_ms=duration_ms,
                )
            )
            if not result.success:
                case_error = error or f"Step '{step.action}' failed."
                break
        except (TypeError, ValueError) as exc:
            case_error = str(exc)
            step_results.append(
                StepResult(
                    action=step.action,
                    target=step.target,
                    value=step.value,
                    success=False,
                    error=case_error,
                    duration_ms=0,
                )
            )
            break

    duration_ms = int((time.perf_counter() - started_at) * 1000)
    success = case_error is None
    return CaseResult(
        case_path=case_path,
        goal=case.meta.goal,
        app=case.meta.app,
        success=success,
        steps_results=step_results,
        duration_ms=duration_ms,
        error=case_error,
    )


def run_path(path: Path) -> bool:
    """Replay one case file or every case file under a directory."""
    return all(result.success for result in run_results_for_path(path))


def run_results_for_path(path: Path, adapter: FsqAdapter | None = None) -> list[CaseResult]:
    """Replay one case file or every case file under a directory with structured results."""
    if path.is_dir():
        case_paths = sorted(candidate for candidate in path.rglob("*.yaml") if candidate.is_file())
        if not case_paths:
            raise FileNotFoundError(f"No case files found under: {path}")
        return [run_case_result(case_path, adapter=adapter) for case_path in case_paths]

    return [run_case_result(path, adapter=adapter)]


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
