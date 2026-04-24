"""Unit tests for case recording helpers."""

from __future__ import annotations

from pathlib import Path

from src.case import CaseFile, CaseMeta, Step
from src.cli.record import record_goal


def test_record_goal_runs_planning_loop_and_saves_case(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "cases" / "recorded.yaml"
    planned_case = CaseFile(
        meta=CaseMeta(goal="登录 GitHub", app="Safari", created="2026-04-19T14:30:00Z"),
        steps=[Step(action="tap", target="Sign in")],
    )
    saved: list[tuple[CaseFile, Path]] = []

    class FakePlanningLoop:
        def __init__(self, goal, app, max_cycles, llm_client):
            assert goal == "登录 GitHub"
            assert app == "Safari"
            assert max_cycles == 4
            assert llm_client is fake_llm

        def run(self) -> CaseFile:
            return planned_case

    def fake_llm(prompt: str) -> str:
        return prompt

    monkeypatch.setattr("src.cli.record.PlanningLoop", FakePlanningLoop)
    monkeypatch.setattr("src.cli.record.save_case", lambda case, path: saved.append((case, path)))

    result = record_goal("登录 GitHub", "Safari", output_path, 4, fake_llm)

    assert result is planned_case
    assert saved == [(planned_case, output_path)]
