"""Unit tests for case repair helpers."""

from __future__ import annotations

from pathlib import Path

from src.case import CaseFile, CaseMeta, Step, load_case, save_case
from src.cli.fix import fix_case
from src.report.html import CaseResult, StepResult


def test_fix_case_updates_yaml_when_repair_succeeds(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "cases" / "failed.yaml"
    save_case(
        CaseFile(
            meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
            steps=[Step(action="tap", target="Wrong button")],
        ),
        case_path,
    )

    results = iter(
        [
            CaseResult(
                case_path=case_path,
                goal="登录 GitHub",
                app="Safari",
                success=False,
                steps_results=[
                    StepResult(
                        action="tap",
                        target="Wrong button",
                        value=None,
                        success=False,
                        error="element not found",
                        duration_ms=11,
                    )
                ],
                duration_ms=11,
                error="element not found",
            ),
            CaseResult(
                case_path=case_path,
                goal="登录 GitHub",
                app="Safari",
                success=True,
                steps_results=[
                    StepResult(
                        action="tap",
                        target="Sign in",
                        value=None,
                        success=True,
                        error=None,
                        duration_ms=9,
                    )
                ],
                duration_ms=9,
                error=None,
            ),
        ]
    )

    monkeypatch.setattr("src.cli.fix.execute_loaded_case", lambda case, case_path=None: next(results))

    llm_calls: list[str] = []

    def fake_llm(prompt: str) -> str:
        llm_calls.append(prompt)
        return """
steps:
  - action: tap
    target: Sign in
"""

    assert fix_case(case_path, fake_llm) is True
    assert llm_calls
    repaired_case = load_case(case_path)
    assert repaired_case.steps[0].target == "Sign in"


def test_fix_case_returns_false_when_llm_output_is_invalid(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "cases" / "failed.yaml"
    save_case(
        CaseFile(
            meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
            steps=[Step(action="tap", target="Wrong button")],
        ),
        case_path,
    )

    monkeypatch.setattr(
        "src.cli.fix.execute_loaded_case",
        lambda case, case_path=None: CaseResult(
            case_path=case_path,
            goal="登录 GitHub",
            app="Safari",
            success=False,
            steps_results=[
                StepResult(
                    action="tap",
                    target="Wrong button",
                    value=None,
                    success=False,
                    error="element not found",
                    duration_ms=11,
                )
            ],
            duration_ms=11,
            error="element not found",
        ),
    )

    assert fix_case(case_path, lambda prompt: "[]") is False
