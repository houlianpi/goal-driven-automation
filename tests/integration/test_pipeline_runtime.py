"""Integration tests for the end-to-end runtime pipeline contract."""
import tempfile
from pathlib import Path

from src.evaluator.evaluator import EvaluationVerdict
from src.executor.mock_executor import MockExecutor
from src.pipeline.pipeline import Pipeline, PipelineStage


def _write_registry(base_dir: Path) -> None:
    registry_dir = base_dir / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "actions.yaml").write_text(
        """
schema_version: "1.0"
actions:
  launch_app:
    args:
      bundle_id: {type: string, required: true}
    compile_to: mac app launch {bundle_id}
    expected_evidence: [process_running, command_output]
    default_retry: {max: 1}
  hotkey:
    args:
      combo: {type: string, required: true}
    compile_to: mac input hotkey {combo}
    expected_evidence: [command_output]
    default_retry: {max: 1}
  assert_visible:
    args:
      locator: {type: string, required: true}
      strategy: {type: string, required: false, default: accessibility_id}
    compile_to: mac assert visible {locator} --strategy {strategy}
    expected_evidence: [assertion_result]
    default_retry: {max: 1}
"""
    )


def test_pipeline_runtime_persists_and_evaluates_successful_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        _write_registry(base_dir)
        pipeline = Pipeline(base_dir=base_dir)
        pipeline.executor = MockExecutor(runs_dir=base_dir / "data" / "runs", failure_rate=0.0)

        result = pipeline.run("Open Edge and create new tab")

        assert result.success is True
        assert result.final_status == "success"
        assert result.evidence is not None
        assert result.evaluation is not None
        assert result.evaluation.verdict == EvaluationVerdict.PASS
        assert [stage.stage for stage in result.stages] == [
            PipelineStage.PARSE_GOAL,
            PipelineStage.GENERATE_PLAN,
            PipelineStage.COMPILE,
            PipelineStage.EXECUTE,
            PipelineStage.EVALUATE,
        ]

        run_dir = base_dir / "data" / "runs" / result.run_id
        assert (run_dir / "evidence.json").exists()
        assert (run_dir / "input_plan.json").exists()
        assert (run_dir / "pipeline_result.json").exists()

        loaded = pipeline.evidence_storage.load_evidence(result.run_id)
        assert loaded is not None
        assert loaded.plan_id == result.plan["plan_id"]
        assert loaded.status.value == "success"
        assert len(loaded.steps) == len(result.evidence.steps)
        assert result.to_dict()["run_summary"]["run_id"] == result.run_id
        assert result.to_dict()["run_summary"]["final_status"] == result.final_status
        assert result.to_dict()["run_summary"]["passed_steps"] == result.evaluation.passed_steps


def test_pipeline_runtime_reaches_partial_without_failures_after_repair():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        _write_registry(base_dir)
        pipeline = Pipeline(base_dir=base_dir)
        executor = MockExecutor(runs_dir=base_dir / "data" / "runs", failure_rate=0.0)
        executor.force_failure("s2", "element_not_found")
        pipeline.executor = executor

        result = pipeline.run("Open Edge and create new tab")

        assert result.success is True
        assert result.final_status == "recovered"
        assert result.evaluation is not None
        assert result.evaluation.verdict == EvaluationVerdict.PARTIAL
        assert result.repair_result is not None
        assert any(stage.stage == PipelineStage.REPAIR for stage in result.stages)
        assert result.evidence is not None
        assert result.evidence.status.value == "partial"
        assert all(step.status.value != "failure" for step in result.evidence.steps)
