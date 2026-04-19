"""Unit tests for the new gda CLI entry point."""

from __future__ import annotations

from pathlib import Path

from src.case import CaseFile, CaseMeta, Step
from src.cli.main import build_parser, cmd_goal, main


def test_build_parser_accepts_immediate_goal() -> None:
    parser = build_parser()

    args = parser.parse_args(["--app", "Safari", "登录 GitHub"])

    assert args.app == "Safari"
    assert args.max_cycles == 10
    assert args.goal == "登录 GitHub"
    assert args.command is None


def test_cmd_goal_replays_cached_case(monkeypatch) -> None:
    cached_case = CaseFile(
        meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
        steps=[Step(action="tap", target="Sign in")],
    )

    class FakeCache:
        def get(self, goal: str, app: str):
            assert goal == "登录 GitHub"
            assert app == "Safari"
            return cached_case

        def put(self, goal: str, app: str, case: CaseFile):
            raise AssertionError("cache.put should not be called on hit")

    replayed: list[CaseFile] = []

    monkeypatch.setattr("src.cli.main.CaseCache", FakeCache)
    monkeypatch.setattr("src.cli.main.run_loaded_case", lambda case: replayed.append(case) or True)

    exit_code = cmd_goal(build_parser().parse_args(["登录 GitHub"]))

    assert exit_code == 0
    assert replayed == [cached_case]


def test_cmd_goal_plans_and_caches_on_miss(monkeypatch) -> None:
    planned_case = CaseFile(
        meta=CaseMeta(goal="搜索天气", app="Safari", created="2026-04-19T14:30:00Z"),
        steps=[Step(action="input", target="Search", value="weather")],
    )
    stored: list[tuple[str, str, CaseFile]] = []

    class FakeCache:
        def get(self, goal: str, app: str):
            return None

        def put(self, goal: str, app: str, case: CaseFile):
            stored.append((goal, app, case))

    monkeypatch.setattr("src.cli.main.CaseCache", FakeCache)
    monkeypatch.setattr("src.cli.main._plan_case", lambda goal, app, max_cycles, llm_client=None: planned_case)
    monkeypatch.setattr("src.cli.main.run_loaded_case", lambda case: True)

    exit_code = cmd_goal(build_parser().parse_args(["搜索天气"]))

    assert exit_code == 0
    assert stored == [("搜索天气", "Safari", planned_case)]


def test_main_routes_run_command(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "cases"
    called: list[Path] = []

    monkeypatch.setattr("src.cli.main.run_path", lambda path: called.append(path) or True)

    exit_code = main(["run", str(case_path)])

    assert exit_code == 0
    assert called == [case_path]


def test_main_routes_record_command(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "cases" / "recorded.yaml"
    recorded: list[tuple[str, str, Path, int]] = []

    monkeypatch.setattr(
        "src.cli.main.record_goal",
        lambda goal, app, output_path, max_cycles, llm_client: recorded.append(
            (goal, app, output_path, max_cycles)
        ),
    )
    monkeypatch.setattr("src.cli.main._default_llm_client", lambda: lambda prompt: prompt)

    exit_code = main(["record", "登录 GitHub", "-o", str(output_path)])

    assert exit_code == 0
    assert recorded == [("登录 GitHub", "Safari", output_path, 10)]


def test_main_routes_fix_command(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "cases" / "failed.yaml"
    called: list[Path] = []

    monkeypatch.setattr("src.cli.main.fix_case", lambda path, llm_client: called.append(path) or True)
    monkeypatch.setattr("src.cli.main._default_fix_llm_client", lambda: lambda prompt: prompt)

    exit_code = main(["fix", str(case_path)])

    assert exit_code == 0
    assert called == [case_path]


def test_main_routes_run_report_command(monkeypatch, tmp_path: Path) -> None:
    cases_path = tmp_path / "cases"
    report_path = tmp_path / "report.html"
    results = [type("CaseResult", (), {"success": True})()]
    generated: list[tuple[list[object], Path]] = []

    class FakeReportGenerator:
        def generate_report(self, incoming_results, output_path):
            generated.append((incoming_results, output_path))

    monkeypatch.setattr("src.cli.main.run_results_for_path", lambda path: results)
    monkeypatch.setattr("src.cli.main.ReportGenerator", FakeReportGenerator)

    exit_code = main(["run", str(cases_path), "--report", "html", "--output", str(report_path)])

    assert exit_code == 0
    assert generated == [(results, report_path)]
