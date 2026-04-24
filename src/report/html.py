"""HTML report generation for case replay results."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path


@dataclass(frozen=True)
class StepResult:
    """Structured result for one replayed step."""

    action: str
    target: str | None
    value: str | None
    success: bool
    error: str | None
    duration_ms: int


@dataclass(frozen=True)
class CaseResult:
    """Structured result for one replayed case."""

    case_path: Path | None
    goal: str
    app: str
    success: bool
    steps_results: list[StepResult] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None


class ReportGenerator:
    """Generate a simple standalone HTML report for batch runs."""

    def generate_report(self, results: list[CaseResult], output_path: Path) -> None:
        """Write one HTML report summarizing all case results."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._render_html(results), encoding="utf-8")

    def _render_html(self, results: list[CaseResult]) -> str:
        total_cases = len(results)
        passed_cases = sum(1 for result in results if result.success)
        failed_cases = total_cases - passed_cases
        total_duration = sum(result.duration_ms for result in results)
        case_sections = "\n".join(self._render_case(result) for result in results)
        return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>GDA Report</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: #fffdf8;
      --ink: #1f2933;
      --muted: #52606d;
      --border: #d9d1bf;
      --success: #1f7a4c;
      --failure: #b42318;
      --accent: #8d5a2b;
    }}
    body {{ font-family: Georgia, "Iowan Old Style", serif; background: linear-gradient(180deg, #efe7d8, var(--bg)); color: var(--ink); margin: 0; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 48px; }}
    .hero {{ background: rgba(255,255,255,0.72); border: 1px solid var(--border); border-radius: 18px; padding: 24px; backdrop-filter: blur(6px); }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-top: 18px; }}
    .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 14px; }}
    .case {{ margin-top: 20px; background: rgba(255,255,255,0.82); border: 1px solid var(--border); border-radius: 18px; overflow: hidden; }}
    .case-header {{ padding: 18px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }}
    .badge.success {{ background: #dff3e7; color: var(--success); }}
    .badge.failure {{ background: #fce4e2; color: var(--failure); }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 12px 20px; border-bottom: 1px solid #ebe3d5; vertical-align: top; }}
    th {{ font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--accent); }}
    .error {{ color: var(--failure); white-space: pre-wrap; }}
    .path {{ font-family: Menlo, Monaco, monospace; font-size: 13px; color: var(--muted); }}
    @media (max-width: 720px) {{
      .case-header {{ display: block; }}
      th, td {{ padding: 10px 12px; font-size: 14px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class=\"hero\">
      <h1>Goal-Driven Automation Report</h1>
      <p>Batch execution summary for recorded cases.</p>
      <div class=\"summary\">
        <div class=\"card\"><strong>{total_cases}</strong><br />Cases</div>
        <div class=\"card\"><strong>{passed_cases}</strong><br />Passed</div>
        <div class=\"card\"><strong>{failed_cases}</strong><br />Failed</div>
        <div class=\"card\"><strong>{total_duration}</strong><br />Total ms</div>
      </div>
    </section>
    {case_sections}
  </main>
</body>
</html>
"""

    def _render_case(self, result: CaseResult) -> str:
        status_class = "success" if result.success else "failure"
        status_label = "passed" if result.success else "failed"
        steps_rows = "\n".join(self._render_step(step) for step in result.steps_results)
        case_error = (
            f"<p class=\"error\">{escape(result.error)}</p>" if result.error else ""
        )
        path_markup = (
            f"<div class=\"path\">{escape(str(result.case_path))}</div>" if result.case_path else ""
        )
        return f"""
    <section class=\"case\">
      <div class=\"case-header\">
        <div>
          <h2>{escape(result.goal)}</h2>
          <div class=\"meta\">App: {escape(result.app)} | Duration: {result.duration_ms}ms</div>
          {path_markup}
          {case_error}
        </div>
        <span class=\"badge {status_class}\">{status_label}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Action</th>
            <th>Target</th>
            <th>Value</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {steps_rows}
        </tbody>
      </table>
    </section>
"""

    def _render_step(self, step: StepResult) -> str:
        status_label = "passed" if step.success else "failed"
        return f"""
          <tr>
            <td>{escape(step.action)}</td>
            <td>{escape(step.target or '')}</td>
            <td>{escape(step.value or '')}</td>
            <td>{status_label}</td>
            <td>{step.duration_ms}ms</td>
            <td class=\"error\">{escape(step.error or '')}</td>
          </tr>
"""
