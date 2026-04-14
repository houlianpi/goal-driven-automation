"""Unit tests for Pipeline."""
import pytest
import tempfile
import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

from src.pipeline.goal_parser import GoalParser, GoalType
from src.pipeline.plan_generator import PlanGenerator
from src.pipeline.pipeline import Pipeline, PipelineStage
from src.executor.mock_executor import MockExecutor


class TestGoalParser:
    @pytest.fixture
    def parser(self):
        return GoalParser()
    
    def test_parse_app_launch(self, parser):
        goal = parser.parse("Open Edge")
        assert goal.goal_type == GoalType.APP_LAUNCH
        assert goal.target_app == "Microsoft Edge"
        assert "launch" in goal.actions
    
    def test_parse_composite(self, parser):
        goal = parser.parse("Open Edge and create new tab")
        assert goal.goal_type == GoalType.COMPOSITE
        assert "launch" in goal.actions
        assert "new_tab" in goal.actions
    
    def test_parse_safari(self, parser):
        goal = parser.parse("Open Safari")
        assert goal.target_app == "Safari"
    
    def test_parse_click(self, parser):
        goal = parser.parse("Click on 'Submit' button")
        assert goal.goal_type == GoalType.UI_NAVIGATION
        assert "click" in goal.actions

    def test_parse_type_with_app_context(self, parser):
        goal = parser.parse("In Safari, type 'hello world'")

        assert goal.goal_type == GoalType.DATA_ENTRY
        assert goal.target_app == "Safari"
        assert goal.constraints["text"] == "hello world"
        assert goal.constraints["app"] == "Safari"
        assert goal.constraints["requires_focused_target"] is True

    def test_parse_click_with_app_context_and_locator_metadata(self, parser):
        goal = parser.parse("Click the Submit button in Edge")

        assert goal.goal_type == GoalType.UI_NAVIGATION
        assert goal.target_app == "Microsoft Edge"
        assert goal.constraints["element"] == "Submit"
        assert goal.constraints["app"] == "Microsoft Edge"
        assert goal.constraints["locator_text"] == "Submit"
        assert goal.constraints["locator_role"] == "button"


class TestPlanGenerator:
    @pytest.fixture
    def generator(self):
        return PlanGenerator()
    
    def test_generate_launch_plan(self, generator):
        parser = GoalParser()
        goal = parser.parse("Open Edge")
        plan = generator.generate(goal)
        
        assert plan["plan_id"].startswith("plan-")
        assert plan["app"] == "Microsoft Edge"
        assert plan["goal"] == "Open Edge"
        assert len(plan["steps"]) >= 1
        assert plan["steps"][0]["action"] == "launch"

    def test_generate_composite_plan(self, generator):
        parser = GoalParser()
        goal = parser.parse("Open Edge and create new tab")
        plan = generator.generate(goal)

        actions = [s["action"] for s in plan["steps"]]
        assert "launch" in actions
        assert "shortcut" in actions

    def test_generated_plan_matches_schema_contract(self, generator):
        from src.schema.validator import SchemaValidator

        parser = GoalParser()
        goal = parser.parse("Open Edge and create new tab")
        plan = generator.generate(goal)

        is_valid, errors = SchemaValidator().validate_plan(plan)
        assert is_valid is True, errors

    def test_generate_type_plan_marks_ungrounded_context_for_review(self, generator):
        parser = GoalParser()
        goal = parser.parse("Type 'hello world'")

        plan = generator.generate(goal)
        step = plan["steps"][0]

        assert step["action"] == "type"
        assert step["params"]["text"] == "hello world"
        assert step["params"]["requires_focused_target"] is True
        assert step["metadata"]["context_confidence"] == "low"
        assert step["review_required"] is True
        assert step["on_fail"] == "human_review"

    def test_generate_click_plan_preserves_context_metadata(self, generator):
        parser = GoalParser()
        goal = parser.parse("Click the Submit button in Edge")

        plan = generator.generate(goal)
        step = plan["steps"][0]

        assert step["action"] == "click"
        assert step["params"]["selector"] == "Submit"
        assert step["params"]["locator_text"] == "Submit"
        assert step["params"]["locator_role"] == "button"
        assert step["params"]["app"] == "Microsoft Edge"
        assert step["metadata"]["context_confidence"] == "medium"
        assert step["review_required"] is False


class TestPipeline:
    def test_pipeline_module_has_single_pipeline_class_definition(self):
        import src.pipeline.pipeline as pipeline_module

        source = inspect.getsource(pipeline_module)
        assert source.count("class Pipeline:") == 1

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal registry
            registry_dir = Path(tmpdir) / "registry"
            registry_dir.mkdir()
            (registry_dir / "actions.yaml").write_text("""
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
  hotkey:
    args:
      combo: {type: string, required: true}
    compile_to: mac input hotkey {combo}
  assert_visible:
    args:
      ref: {type: string, required: false}
      role: {type: string, required: false}
      name: {type: string, required: false}
      label: {type: string, required: false}
      id: {type: string, required: false}
    compile_to: __assert_argv__
  wait:
    args:
      seconds: {type: number, required: true}
    compile_to: sleep {seconds}
""")
            
            pipeline = Pipeline(base_dir=Path(tmpdir))
            result = pipeline.run("Open Edge and create new tab", dry_run=True)
            
            assert result.final_status == "dry_run_complete"
            assert result.success is True
            assert result.goal is not None
            assert result.plan is not None
    
    def test_stages_recorded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_dir = Path(tmpdir) / "registry"
            registry_dir.mkdir()
            (registry_dir / "actions.yaml").write_text("""
version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
""")
            
            pipeline = Pipeline(base_dir=Path(tmpdir))
            result = pipeline.run("Open Edge", dry_run=True)
            
            stages = [s.stage for s in result.stages]
            assert PipelineStage.PARSE_GOAL in stages
            assert PipelineStage.GENERATE_PLAN in stages
            assert PipelineStage.COMPILE in stages

    def test_run_executes_compiled_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_dir = Path(tmpdir) / "registry"
            registry_dir.mkdir()
            (registry_dir / "actions.yaml").write_text(
                """
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
"""
            )

            pipeline = Pipeline(base_dir=Path(tmpdir))
            compiled_plan = {
                "plan_id": "plan-compiled",
                "steps": [{"step_id": "s1", "command": "echo compiled"}],
            }

            with patch.object(pipeline, "_compile", return_value=(MagicMock(success=True), compiled_plan)):
                with patch.object(pipeline, "_execute", return_value=(MagicMock(success=False), None)) as execute_mock:
                    pipeline.run("Open Edge")

            execute_mock.assert_called_once_with(compiled_plan, ANY)

    def test_pipeline_accepts_mock_executor_for_runtime_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_dir = Path(tmpdir) / "registry"
            registry_dir.mkdir()
            (registry_dir / "actions.yaml").write_text(
                """
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
    expected_evidence: [process_running]
    default_retry: {max_attempts: 1}
  assert_visible:
    args:
      ref: {type: string, required: false}
      role: {type: string, required: false}
      name: {type: string, required: false}
      label: {type: string, required: false}
      id: {type: string, required: false}
    compile_to: __assert_argv__
    expected_evidence: [assertion_result]
    default_retry: {max_attempts: 1}
  wait:
    args:
      seconds: {type: number, required: true}
    compile_to: sleep {seconds}
    default_retry: {max_attempts: 1}
"""
            )

            pipeline = Pipeline(base_dir=Path(tmpdir))
            pipeline.executor = MockExecutor(runs_dir=Path(tmpdir) / "data" / "runs", failure_rate=0.0)

            result = pipeline.run("Open Edge")

            assert result.evidence is not None
            assert result.evidence.plan_id == result.plan["plan_id"]
            assert result.final_status in {"success", "partial", "failed", "recovered"}

    def test_run_result_exposes_agent_summary_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_dir = Path(tmpdir) / "registry"
            registry_dir.mkdir()
            (registry_dir / "actions.yaml").write_text(
                """
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
    expected_evidence: [process_running]
    default_retry: {max_attempts: 1}
  assert_visible:
    args:
      ref: {type: string, required: false}
      role: {type: string, required: false}
      name: {type: string, required: false}
      label: {type: string, required: false}
      id: {type: string, required: false}
    compile_to: __assert_argv__
    expected_evidence: [assertion_result]
    default_retry: {max_attempts: 1}
  wait:
    args:
      seconds: {type: number, required: true}
    compile_to: sleep {seconds}
    default_retry: {max_attempts: 1}
"""
            )

            pipeline = Pipeline(base_dir=Path(tmpdir))
            pipeline.executor = MockExecutor(runs_dir=Path(tmpdir) / "data" / "runs", failure_rate=0.0)

            result = pipeline.run("Open Edge")
            payload = result.to_dict()

            assert payload["run_summary"]["run_id"] == result.run_id
            assert payload["run_summary"]["final_status"] == result.final_status
            assert payload["run_summary"]["artifact_dir"] == result.artifacts_dir
            assert payload["run_summary"]["passed_steps"] >= 1
            assert payload["run_summary"]["failed_steps"] == 0
