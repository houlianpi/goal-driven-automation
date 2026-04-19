"""Step recording helpers for the planning loop."""

from __future__ import annotations

from src.case.schema import Step
from src.time_utils import utc_now


class StepRecorder:
    """Record executed steps with stable timestamps."""

    def __init__(self) -> None:
        self._steps: list[Step] = []
        self._screenshot_paths: list[str | None] = []

    def record_step(
        self,
        action: str,
        target: str | None,
        value: str | None,
        result: str | None,
        screenshot_path: str | None,
    ) -> Step:
        """Append one executed step to the in-memory recording."""
        step = Step(
            action=action,
            target=target,
            value=value,
            result=result,
            timestamp=utc_now().isoformat(),
        )
        self._steps.append(step)
        self._screenshot_paths.append(screenshot_path)
        return step

    def get_steps(self) -> list[Step]:
        """Return the recorded steps in execution order."""
        return self._steps
