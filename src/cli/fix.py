"""Repair helpers for failed case files."""

from __future__ import annotations

from collections.abc import Callable
import inspect
from pathlib import Path
from typing import Any, Protocol, Union

import yaml

from src.case import CaseFile, load_case, save_case
from src.case.loader import parse_case_data
from src.cli.run import CaseResult, execute_loaded_case


class PromptFixClient(Protocol):
    """LLM client accepting a rendered repair prompt."""

    def fix(self, prompt: str) -> str:
        """Return repaired case YAML for the provided prompt."""


FixLLMClient = Union[Callable[[str], str], PromptFixClient, Any]


def fix_case(case_path: Path, llm_client: FixLLMClient) -> bool:
    """Analyze a failed case, attempt a repair, and persist it on success."""
    case = load_case(case_path)
    initial_result = execute_loaded_case(case, case_path=case_path)
    if initial_result.success:
        return True

    prompt = _build_fix_prompt(case, initial_result)
    repaired_case = _parse_repaired_case(case, _call_fix_llm(llm_client, prompt))
    if repaired_case is None:
        return False

    repaired_result = execute_loaded_case(repaired_case, case_path=case_path)
    if not repaired_result.success:
        return False

    save_case(repaired_case, case_path)
    return True


def _build_fix_prompt(case: CaseFile, result: CaseResult) -> str:
    failed_steps = [step for step in result.steps_results if not step.success]
    failure_lines = [
        f"- action={step.action!r}, target={step.target!r}, value={step.value!r}, error={step.error!r}"
        for step in failed_steps
    ]
    payload = yaml.safe_dump(_case_to_data(case), allow_unicode=False, sort_keys=False)
    failure_summary = "\n".join(failure_lines) if failure_lines else f"- overall_error={result.error!r}"
    return (
        "Repair this failed GDA case. Return YAML only.\n"
        "You may return either a full case document or only a mapping with steps/postconditions.\n"
        "Keep valid steps unchanged unless necessary.\n\n"
        f"Failure summary:\n{failure_summary}\n\n"
        f"Current case:\n{payload}"
    )


def _call_fix_llm(llm_client: FixLLMClient, prompt: str) -> str:
    if callable(llm_client) and not hasattr(llm_client, "fix"):
        return llm_client(prompt)

    fixer = getattr(llm_client, "fix", None)
    if fixer is None:
        fixer = getattr(llm_client, "plan", None)
    if fixer is None:
        raise TypeError("llm_client must be callable or expose .fix(...) / .plan(...).")

    signature = inspect.signature(fixer)
    if len(signature.parameters) != 1:
        raise TypeError("fix llm_client must accept exactly one prompt argument.")
    return fixer(prompt)


def _parse_repaired_case(original_case: CaseFile, raw_response: str) -> CaseFile | None:
    parsed = yaml.safe_load(raw_response)
    if not isinstance(parsed, dict):
        return None

    if "meta" in parsed:
        try:
            return parse_case_data(parsed)
        except (TypeError, ValueError, KeyError):
            return None

    merged = {
        "meta": _case_to_data(original_case)["meta"],
        "steps": parsed.get("steps", []),
        "postconditions": parsed.get("postconditions", _case_to_data(original_case)["postconditions"]),
    }
    try:
        return parse_case_data(merged)
    except (TypeError, ValueError, KeyError):
        return None


def _case_to_data(case: CaseFile) -> dict[str, Any]:
    return {
        "meta": {
            "goal": case.meta.goal,
            "app": case.meta.app,
            "created": case.meta.created,
            "tags": list(case.meta.tags),
            "variables": list(case.meta.variables),
        },
        "steps": [
            {
                key: value
                for key, value in {
                    "action": step.action,
                    "target": step.target,
                    "value": step.value,
                    "result": step.result,
                    "timestamp": step.timestamp,
                }.items()
                if value is not None
            }
            for step in case.steps
        ],
        "postconditions": [
            {
                key: value
                for key, value in {
                    "assert": condition.assert_type,
                    "target": condition.target,
                    "value": condition.value,
                }.items()
                if value is not None
            }
            for condition in case.postconditions
        ],
    }
