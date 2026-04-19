"""Case recording helpers for the gda CLI."""

from __future__ import annotations

from pathlib import Path

from src.case import CaseFile, save_case
from src.engine.planner import LLMClient, PlanningLoop


def record_goal(
    goal: str,
    app: str,
    output_path: Path,
    max_cycles: int,
    llm_client: LLMClient,
) -> CaseFile:
    """Run the planning loop, record executed steps, and persist a case file."""
    planner = PlanningLoop(
        goal=goal,
        app=app,
        max_cycles=max_cycles,
        llm_client=llm_client,
    )
    case = planner.run()
    save_case(case, output_path)
    return case
