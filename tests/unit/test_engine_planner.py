"""Unit tests for the planning loop and step recorder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.actions.fsq_adapter import ExecutionResult
from src.case.schema import CaseFile
from src.engine.planner import PlanningLoop
from src.engine.recorder import StepRecorder
from src.llm.parser import PlanningResponse


class StaticPromptClient:
    """Simple prompt-based planner client for tests."""

    def __init__(self, xml_response: str) -> None:
        self.xml_response = xml_response
        self.prompts: list[str] = []

    def plan(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.xml_response


class StructuredPlanningClient:
    """Structured planner client variant used to verify injection flexibility."""

    def __init__(self, xml_response: str) -> None:
        self.xml_response = xml_response
        self.calls: list[dict[str, object]] = []

    def plan(
        self,
        *,
        goal: str,
        app: str,
        screenshot_desc: str,
        ui_tree: object,
        history: list[dict[str, object]],
        action_space: object,
        prompt: str,
    ) -> str:
        self.calls.append(
            {
                "goal": goal,
                "app": app,
                "screenshot_desc": screenshot_desc,
                "ui_tree": ui_tree,
                "history": history,
                "prompt": prompt,
                "action_space": action_space,
            }
        )
        return self.xml_response


class FakePlanningLoop(PlanningLoop):
    """Testing seam for planning loop state capture."""

    def __init__(self, *args, screenshots: list[str], ui_trees: list[dict[str, object]], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._screenshots = screenshots
        self._ui_trees = ui_trees
        self.capture_calls = 0
        self.ui_tree_calls = 0

    def capture_screenshot(self) -> str:
        path = self._screenshots[self.capture_calls]
        self.capture_calls += 1
        return path

    def get_ui_tree(self) -> dict[str, object]:
        tree = self._ui_trees[self.ui_tree_calls]
        self.ui_tree_calls += 1
        return tree


def test_step_recorder_records_timestamped_steps():
    """Recorder should produce step dataclasses with timestamps."""
    recorder = StepRecorder()

    step = recorder.record_step(
        action="tap",
        target="Sign in",
        value=None,
        result="success",
        screenshot_path="/tmp/step-1.png",
    )

    assert step.action == "tap"
    assert step.target == "Sign in"
    assert step.result == "success"
    assert step.timestamp is not None
    assert recorder.get_steps() == [step]


def test_planning_loop_runs_until_should_continue_is_false():
    """Loop should record executed steps and stop when the planner says done."""
    first_xml = """
    <response>
      <thought>Open Safari first.</thought>
      <log>Launching Safari</log>
      <action>
        <type>launch</type>
        <target>com.apple.Safari</target>
        <value></value>
      </action>
      <should_continue>true</should_continue>
    </response>
    """
    second_xml = """
    <response>
      <thought>The page is ready.</thought>
      <log>Click Sign in</log>
      <action>
        <type>tap</type>
        <target>Sign in</target>
        <value></value>
      </action>
      <should_continue>false</should_continue>
    </response>
    """
    responses = iter([first_xml, second_xml])
    loop = FakePlanningLoop(
        goal="登录 GitHub",
        app="Safari",
        max_cycles=5,
        llm_client=lambda prompt: next(responses),
        screenshots=["/tmp/s1.png", "/tmp/s2.png"],
        ui_trees=[{"window": "Safari"}, {"buttons": ["Sign in"]}],
    )
    loop.adapter.execute = MagicMock(
        side_effect=[
            ExecutionResult(success=True, output="launched", error="", duration_ms=10),
            ExecutionResult(success=True, output="clicked", error="", duration_ms=15),
        ]
    )

    case = loop.run()

    assert isinstance(case, CaseFile)
    assert case.meta.goal == "登录 GitHub"
    assert case.meta.app == "Safari"
    assert [step.action for step in case.steps] == ["launch", "tap"]
    assert case.steps[0].target == "com.apple.Safari"
    assert case.steps[1].target == "Sign in"
    assert all(step.result == "success" for step in case.steps)
    assert len(loop.history) == 2
    assert loop.history[0]["screenshot_path"] == "/tmp/s1.png"
    assert loop.history[1]["ui_tree"] == {"buttons": ["Sign in"]}


def test_planning_loop_stops_when_execution_reports_goal_achieved():
    """Execution payload can terminate the loop even if the planner would continue."""
    xml = """
    <response>
      <thought>Assertion confirms success.</thought>
      <log>Checking title</log>
      <action>
        <type>assert</type>
        <target>contains::window.title</target>
        <value>GitHub</value>
      </action>
      <should_continue>true</should_continue>
    </response>
    """
    client = StaticPromptClient(xml)
    loop = FakePlanningLoop(
        goal="登录 GitHub",
        app="Safari",
        max_cycles=3,
        llm_client=client,
        screenshots=["/tmp/s1.png"],
        ui_trees=[{"title": "GitHub"}],
    )
    loop.adapter.execute = MagicMock(
        return_value=ExecutionResult(
            success=True,
            output='{"goal_achieved": true}',
            error="",
            duration_ms=8,
        )
    )

    case = loop.run()

    assert len(case.steps) == 1
    assert case.steps[0].action == "assert"
    action, params = loop.adapter.execute.call_args.args
    assert action.name == "assert"
    assert params == {"type": "contains", "target": "window.title", "value": "GitHub"}
    assert len(client.prompts) == 1
    assert "登录 GitHub" in client.prompts[0]


def test_plan_next_action_supports_structured_planning_client():
    """Planner should accept protocol-style clients, not only raw callables."""
    xml = """
    <response>
      <thought>Type search text.</thought>
      <log>Entering query</log>
      <action>
        <type>input</type>
        <target>Search</target>
        <value>weather</value>
      </action>
      <should_continue>true</should_continue>
    </response>
    """
    client = StructuredPlanningClient(xml)
    loop = PlanningLoop(goal="搜索天气", app="Safari", llm_client=client)

    response = loop.plan_next_action("screenshot summary", {"field": "Search"})

    assert isinstance(response, PlanningResponse)
    assert response.action_type == "input"
    assert response.action_target == "Search"
    assert response.action_value == "weather"
    assert client.calls[0]["goal"] == "搜索天气"
    assert client.calls[0]["app"] == "Safari"
    assert client.calls[0]["ui_tree"] == {"field": "Search"}


def test_capture_screenshot_invokes_fsq_capture_command(tmp_path: Path, monkeypatch):
    """Screenshot capture should use the fsq-mac positional output path contract."""
    loop = PlanningLoop(goal="test", app="Safari", llm_client=lambda prompt: prompt)
    loop.adapter.cli_path = "/tmp/fake-mac"
    expected_path = tmp_path / "gda-planning-loop" / "capture.png"

    monkeypatch.setattr("src.engine.planner.tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr("src.engine.planner.uuid4", lambda: type("Uuid", (), {"hex": "capture"})())

    completed = MagicMock(returncode=0, stderr="")
    run_mock = MagicMock(return_value=completed)
    monkeypatch.setattr("src.engine.planner.subprocess.run", run_mock)

    path = loop.capture_screenshot()

    assert path == str(expected_path)
    assert run_mock.call_args.args[0] == ["/tmp/fake-mac", "capture", "screenshot", str(expected_path)]


def test_get_ui_tree_prefers_mac_ui_tree_and_parses_json(monkeypatch):
    """UI tree capture should accept direct JSON output from fsq-mac."""
    loop = PlanningLoop(goal="test", app="Safari", llm_client=lambda prompt: prompt)
    loop.adapter.cli_path = "/tmp/fake-mac"

    completed = MagicMock(returncode=0, stdout='{"window": "Safari"}', stderr="")
    run_mock = MagicMock(return_value=completed)
    monkeypatch.setattr("src.engine.planner.subprocess.run", run_mock)

    tree = loop.get_ui_tree()

    assert tree == {"window": "Safari"}
    assert run_mock.call_args.args[0] == ["/tmp/fake-mac", "ui", "tree"]
