"""Unit tests for case replay helpers."""

from __future__ import annotations

from pathlib import Path

from src.case import CaseFile, CaseMeta, Step, save_case
from src.cli.run import run_case, run_case_result, run_path, run_results_for_path


def test_run_case_executes_all_steps(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "cases" / "login.yaml"
    save_case(
        CaseFile(
            meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
            steps=[
                Step(action="launch", target="com.apple.Safari"),
                Step(action="input", target="Search", value="github.com"),
                Step(action="tap", target="Sign in"),
            ],
        ),
        case_path,
    )
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeAdapter:
        def execute(self, action, params):
            calls.append((action.name, params))
            return type("Result", (), {"success": True})()

    monkeypatch.setattr("src.cli.run.FsqAdapter", FakeAdapter)

    success = run_case(case_path)

    assert success is True
    assert calls == [
        ("launch", {"target": "com.apple.Safari"}),
        ("input", {"target": "Search", "value": "github.com"}),
        ("tap", {"target": "Sign in"}),
    ]


def test_run_case_result_returns_structured_failure(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "cases" / "login.yaml"
    save_case(
        CaseFile(
            meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
            steps=[Step(action="tap", target="Sign in")],
        ),
        case_path,
    )

    class FakeAdapter:
        def execute(self, action, params):
            return type("Result", (), {"success": False, "error": "not found", "duration_ms": 12})()

    monkeypatch.setattr("src.cli.run.FsqAdapter", FakeAdapter)

    result = run_case_result(case_path)

    assert result.success is False
    assert result.case_path == case_path
    assert result.goal == "登录 GitHub"
    assert result.steps_results[0].action == "tap"
    assert result.steps_results[0].success is False
    assert result.error == "not found"


def test_run_path_executes_all_yaml_cases_in_directory(monkeypatch, tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    save_case(
        CaseFile(
            meta=CaseMeta(goal="打开 Safari", app="Safari", created="2026-04-19T14:30:00Z"),
            steps=[Step(action="launch", target="com.apple.Safari")],
        ),
        cases_dir / "a.yaml",
    )
    save_case(
        CaseFile(
            meta=CaseMeta(goal="点击 Sign in", app="Safari", created="2026-04-19T14:31:00Z"),
            steps=[Step(action="tap", target="Sign in")],
        ),
        cases_dir / "nested" / "b.yaml",
    )
    executed: list[str] = []

    def fake_run_case_result(path: Path, adapter=None):
        executed.append(path.name)
        return type("CaseResult", (), {"success": True})()

    monkeypatch.setattr("src.cli.run.run_case_result", fake_run_case_result)

    success = run_path(cases_dir)

    assert success is True
    assert executed == ["a.yaml", "b.yaml"]


def test_run_path_fails_when_any_case_fails(monkeypatch, tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    save_case(
        CaseFile(
            meta=CaseMeta(goal="打开 Safari", app="Safari", created="2026-04-19T14:30:00Z"),
            steps=[Step(action="launch", target="com.apple.Safari")],
        ),
        cases_dir / "a.yaml",
    )
    save_case(
        CaseFile(
            meta=CaseMeta(goal="点击 Sign in", app="Safari", created="2026-04-19T14:31:00Z"),
            steps=[Step(action="tap", target="Sign in")],
        ),
        cases_dir / "b.yaml",
    )

    def fake_run_case_result(path: Path, adapter=None):
        return type("CaseResult", (), {"success": path.name != "b.yaml"})()

    monkeypatch.setattr("src.cli.run.run_case_result", fake_run_case_result)

    success = run_path(cases_dir)

    assert success is False


def test_run_results_for_path_returns_single_case_result(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "cases" / "single.yaml"
    save_case(
        CaseFile(
            meta=CaseMeta(goal="打开 Safari", app="Safari", created="2026-04-19T14:30:00Z"),
            steps=[Step(action="launch", target="com.apple.Safari")],
        ),
        case_path,
    )

    class FakeAdapter:
        def execute(self, action, params):
            return type("Result", (), {"success": True, "error": "", "duration_ms": 7})()

    results = run_results_for_path(case_path, adapter=FakeAdapter())

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].case_path == case_path
