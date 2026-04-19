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
    planned_case = CaseFile(
        meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
        steps=[Step(action="tap", target="Sign in")],
    )
    saved: list[tuple[CaseFile, Path]] = []

    monkeypatch.setattr("src.cli.main._plan_case", lambda goal, app, max_cycles, llm_client=None: planned_case)
    monkeypatch.setattr("src.cli.main.save_case", lambda case, path: saved.append((case, path)))

    exit_code = main(["record", "登录 GitHub", "-o", str(output_path)])

    assert exit_code == 0
    assert saved == [(planned_case, output_path)]
