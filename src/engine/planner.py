"""Goal-driven planning loop built on top of fsq-mac actions."""

from __future__ import annotations

import json
from pathlib import Path
import inspect
import subprocess
import tempfile
from typing import Any, Callable, Protocol, Sequence, Union
from uuid import uuid4

from src.actions.action_space import ACTION_SPACE, ActionDefinition
from src.actions.fsq_adapter import ExecutionResult, FsqAdapter
from src.case.schema import CaseFile, CaseMeta, Step
from src.engine.recorder import StepRecorder
from src.llm import PlanningResponse, build_planning_prompt, parse_xml_response
from src.time_utils import utc_now


class PromptPlanningClient(Protocol):
    """LLM client accepting a rendered planning prompt."""

    def plan(self, prompt: str) -> str:
        """Return one XML planning response for the provided prompt."""


class ContextPlanningClient(Protocol):
    """LLM client accepting structured planning context."""

    def plan(
        self,
        *,
        goal: str,
        app: str,
        screenshot_desc: str,
        ui_tree: Any,
        history: Sequence[dict[str, Any]],
        action_space: Sequence[ActionDefinition],
        prompt: str,
    ) -> str:
        """Return one XML planning response for the provided context."""


LLMClient = Union[Callable[[str], str], PromptPlanningClient, ContextPlanningClient]


class PlanningLoop:
    """Observe, plan, execute, and record until the goal completes."""

    def __init__(
        self,
        goal: str,
        app: str,
        max_cycles: int = 10,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.goal = goal
        self.app = app
        self.max_cycles = max_cycles
        self.llm_client = llm_client
        self.history: list[dict[str, Any]] = []
        self.recorder = StepRecorder()
        self.steps: list[Step] = self.recorder.get_steps()
        self.adapter = FsqAdapter()

    def run(self) -> CaseFile:
        """Run the observe-plan-act loop and convert results into a case."""
        cycle = 0

        while cycle < self.max_cycles:
            screenshot_path = self.capture_screenshot()
            ui_tree = self.get_ui_tree()
            screenshot_desc = f"Current screenshot saved at: {screenshot_path}"
            response = self.plan_next_action(screenshot_desc, ui_tree)
            result = self._execute_response(response)
            step = self.recorder.record_step(
                action=response.action_type,
                target=response.action_target,
                value=response.action_value or None,
                result=self._format_step_result(result),
                screenshot_path=screenshot_path,
            )
            self.history.append(
                {
                    "cycle": cycle + 1,
                    "thought": response.thought,
                    "log": response.log,
                    "action": {
                        "type": response.action_type,
                        "target": response.action_target,
                        "value": response.action_value,
                    },
                    "result": {
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                        "duration_ms": result.duration_ms,
                    },
                    "recorded_step": {
                        "action": step.action,
                        "target": step.target,
                        "value": step.value,
                        "result": step.result,
                        "timestamp": step.timestamp,
                    },
                    "screenshot_path": screenshot_path,
                    "screenshot_summary": screenshot_desc,
                    "ui_tree": ui_tree,
                }
            )

            goal_achieved = self._goal_achieved(response, result)
            cycle += 1

            if not response.should_continue or goal_achieved:
                break

        return self.to_case_file()

    def capture_screenshot(self) -> str:
        """Capture a screenshot through fsq-mac and return the saved path."""
        output_dir = Path(tempfile.gettempdir()) / "gda-planning-loop"
        output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = output_dir / f"{uuid4().hex}.png"
        completed = subprocess.run(
            [self.adapter.cli_path, "capture", "screenshot", str(screenshot_path)],
            shell=False,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or "Failed to capture screenshot."
            raise RuntimeError(message)
        return str(screenshot_path)

    def get_ui_tree(self) -> dict[str, Any]:
        """Capture the current UI tree and return it as structured data."""
        commands = (
            [self.adapter.cli_path, "ui", "tree"],
            [self.adapter.cli_path, "capture", "ui-tree"],
        )
        last_error = "Failed to capture UI tree."

        for command in commands:
            completed = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            stdout = completed.stdout.strip()
            if completed.returncode == 0 and stdout:
                try:
                    parsed = json.loads(stdout)
                except json.JSONDecodeError:
                    return {"raw": stdout}
                if isinstance(parsed, dict):
                    return parsed
                return {"tree": parsed}

            if completed.stderr.strip():
                last_error = completed.stderr.strip()

        raise RuntimeError(last_error)

    def plan_next_action(self, screenshot_desc: str, ui_tree: dict[str, Any]) -> PlanningResponse:
        """Build the planning prompt, invoke the LLM, and parse the XML response."""
        prompt = build_planning_prompt(
            goal=self.goal,
            screenshot_desc=screenshot_desc,
            ui_tree=ui_tree,
            history=self.history[-5:],
            action_space=ACTION_SPACE,
        )
        raw_response = self._call_llm(prompt, screenshot_desc, ui_tree)
        return parse_xml_response(raw_response)

    def to_case_file(self) -> CaseFile:
        """Convert the recorded execution into a case document."""
        return CaseFile(
            meta=CaseMeta(
                goal=self.goal,
                app=self.app,
                created=utc_now().isoformat(),
            ),
            steps=list(self.steps),
        )

    def _call_llm(self, prompt: str, screenshot_desc: str, ui_tree: dict[str, Any]) -> str:
        """Invoke the injected planner client using the supported adapter styles."""
        if self.llm_client is None:
            raise ValueError("PlanningLoop requires an llm_client to plan the next action.")

        if callable(self.llm_client) and not hasattr(self.llm_client, "plan"):
            return self.llm_client(prompt)

        planner = getattr(self.llm_client, "plan", None)
        if planner is None:
            raise TypeError("llm_client must be callable or expose a .plan(...) method.")

        signature = inspect.signature(planner)
        accepts_prompt_only = len(signature.parameters) == 1 and any(
            parameter.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
            for parameter in signature.parameters.values()
        )
        if accepts_prompt_only:
            return planner(prompt)
        return planner(
            goal=self.goal,
            app=self.app,
            screenshot_desc=screenshot_desc,
            ui_tree=ui_tree,
            history=self.history[-5:],
            action_space=ACTION_SPACE,
            prompt=prompt,
        )

    def _execute_response(self, response: PlanningResponse) -> ExecutionResult:
        """Translate one planning response into an fsq-mac action execution."""
        action = self._get_action_definition(response.action_type)
        params = self._build_action_params(response)
        return self.adapter.execute(action, params)

    def _get_action_definition(self, action_name: str) -> ActionDefinition:
        """Look up the concrete action definition by planner action type."""
        for action in ACTION_SPACE:
            if action.name == action_name:
                return action
        raise ValueError(f"Unknown action type: {action_name}")

    def _build_action_params(self, response: PlanningResponse) -> dict[str, Any]:
        """Map the planner XML contract into fsq-mac action parameters."""
        if response.action_type in {"launch", "tap", "wait"}:
            return {"target": response.action_target}
        if response.action_type == "input":
            return {"target": response.action_target, "value": response.action_value}
        if response.action_type == "hotkey":
            return {"keys": response.action_target}
        if response.action_type == "assert":
            assert_type, assert_target = self._parse_assert_target(response.action_target)
            return {
                "type": assert_type,
                "target": assert_target,
                "value": response.action_value,
            }
        raise ValueError(f"Unsupported planner action type: {response.action_type}")

    def _parse_assert_target(self, target: str) -> tuple[str, str]:
        """Allow compact planner syntax for assert actions."""
        if "::" in target:
            assert_type, assert_target = target.split("::", 1)
            normalized_type = assert_type.strip()
            normalized_target = assert_target.strip()
            if normalized_type and normalized_target:
                return normalized_type, normalized_target
        return "contains", target

    def _format_step_result(self, result: ExecutionResult) -> str:
        """Convert adapter output into the case step result field."""
        if result.success:
            return "success"
        if result.error:
            return result.error
        return "failure"

    def _goal_achieved(self, response: PlanningResponse, result: ExecutionResult) -> bool:
        """Determine whether the loop should treat the goal as achieved."""
        if result.output:
            try:
                payload = json.loads(result.output)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict) and payload.get("goal_achieved") is True:
                return True
        return result.success and not response.should_continue
