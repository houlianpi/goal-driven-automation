"""Unit tests for HTML report generation."""

from __future__ import annotations

from pathlib import Path

from src.report.html import CaseResult, ReportGenerator, StepResult


def test_generate_report_writes_expected_html(tmp_path: Path) -> None:
    output_path = tmp_path / "report.html"
    results = [
        CaseResult(
            case_path=Path("cases/login.yaml"),
            goal="登录 GitHub",
            app="Safari",
            success=False,
            steps_results=[
                StepResult(
                    action="tap",
                    target="Sign in",
                    value=None,
                    success=False,
                    error="element not found",
                    duration_ms=15,
                )
            ],
            duration_ms=15,
            error="element not found",
        )
    ]

    ReportGenerator().generate_report(results, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "Goal-Driven Automation Report" in html
    assert "登录 GitHub" in html
    assert "element not found" in html
    assert "cases/login.yaml" in html
