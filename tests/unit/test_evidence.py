"""Unit tests for Evidence Layer."""
import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.evidence.types import (
    Artifact, CLICommand, StepEvidence, StepStatus, StepError,
    FailureClassification, RunEvidence, RunStatus, Environment,
)
from src.evidence.storage import EvidenceStorage
from src.evidence.collector import EvidenceCollector


class TestStepEvidence:
    def test_successful_step(self):
        step = StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS)
        d = step.to_dict()
        assert d["status"] == "success"
        assert d["step_id"] == "s1"
    
    def test_failed_step_with_error(self):
        error = StepError("Timeout", "Command timed out", FailureClassification.ENVIRONMENT_FAILURE)
        step = StepEvidence(step_id="s2", action="click", status=StepStatus.FAILURE, error=error)
        d = step.to_dict()
        assert d["status"] == "failure"
        assert d["error"]["classification"] == "environment_failure"

    def test_artifact_serialization_preserves_duplicate_types(self):
        step = StepEvidence(
            step_id="s3",
            action="click",
            status=StepStatus.SUCCESS,
            artifacts=[
                Artifact(type="screenshot", path="screenshots/before.png"),
                Artifact(type="screenshot", path="screenshots/after.png"),
            ],
        )

        data = step.to_dict()

        assert "artifacts" in data
        assert len(data["artifacts"]) == 2
        assert data["artifacts"][0]["path"] == "screenshots/before.png"
        assert data["artifacts"][1]["path"] == "screenshots/after.png"

    def test_cli_command_serialization_includes_structured_success_fields(self):
        step = StepEvidence(
            step_id="s4",
            action="element_click",
            status=StepStatus.SUCCESS,
            cli_command=CLICommand(
                command=["mac", "element", "click", "--name", "OK"],
                exit_code=0,
                session_id="s1",
                resolved_element={"ref": "e7"},
                snapshot={"snapshot_id": "snap-1", "elements": []},
                actionability_used={"actionable": True, "checks": {}},
                upstream_duration_ms=321,
            ),
        )

        data = step.to_dict()

        assert data["cli_command"]["session_id"] == "s1"
        assert data["cli_command"]["resolved_element"] == {"ref": "e7"}
        assert data["cli_command"]["snapshot"] == {"snapshot_id": "snap-1", "elements": []}
        assert data["cli_command"]["actionability_used"] == {"actionable": True, "checks": {}}
        assert data["cli_command"]["upstream_duration_ms"] == 321


class TestRunEvidence:
    def test_create_run_evidence(self):
        run = RunEvidence(plan_id="plan-test-001")
        assert run.run_id.startswith("run-")
        assert run.evidence_id.startswith("evidence-")
        assert run.status == RunStatus.SUCCESS
    
    def test_add_failed_step(self):
        run = RunEvidence(plan_id="plan-test-002")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
        assert run.status == RunStatus.SUCCESS
        run.add_step(StepEvidence(step_id="s2", action="click", status=StepStatus.FAILURE))
        assert run.status == RunStatus.FAILURE
    
    def test_finalize(self):
        run = RunEvidence(plan_id="plan-test-003")
        run.finalize()
        assert run.finished_at is not None
        assert run.duration_ms >= 0

    def test_repaired_step_makes_run_partial(self):
        run = RunEvidence(plan_id="plan-test-004")
        run.add_step(StepEvidence(step_id="s1", action="click", status=StepStatus.REPAIRED))
        assert run.status == RunStatus.PARTIAL

    def test_skipped_step_makes_run_partial(self):
        run = RunEvidence(plan_id="plan-test-005")
        run.add_step(StepEvidence(step_id="s1", action="click", status=StepStatus.SKIPPED))
        assert run.status == RunStatus.PARTIAL


class TestEvidenceStorage:
    def test_create_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EvidenceStorage(Path(tmpdir))
            evidence = storage.create_run("plan-test-004")
            assert evidence.plan_id == "plan-test-004"
            assert evidence.environment is not None
            run_dir = Path(tmpdir) / evidence.run_id
            assert run_dir.exists()
            assert (run_dir / "screenshots").exists()
    
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EvidenceStorage(Path(tmpdir))
            evidence = storage.create_run("plan-test-005")
            evidence.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
            evidence.finalize()
            path = storage.save_evidence(evidence)
            assert path.exists()
            loaded = storage.load_evidence(evidence.run_id)
            assert loaded is not None
            assert loaded.plan_id == "plan-test-005"
    
    def test_list_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EvidenceStorage(Path(tmpdir))
            for i in range(3):
                e = storage.create_run(f"plan-{i}")
                e.finalize()
                storage.save_evidence(e)
            runs = storage.list_runs()
            assert len(runs) == 3

    def test_save_and_load_preserves_artifacts_and_assertions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.evidence.types import AssertionResult

            storage = EvidenceStorage(Path(tmpdir))
            evidence = storage.create_run("plan-test-artifacts")
            evidence.steps.append(
                StepEvidence(
                    step_id="s1",
                    action="click",
                    status=StepStatus.SUCCESS,
                    artifacts=[
                        Artifact(type="screenshot", path="screenshots/before.png"),
                        Artifact(type="screenshot", path="screenshots/after.png"),
                    ],
                )
            )
            evidence.assertions.append(
                AssertionResult(
                    assertion_id="a1",
                    step_id="s1",
                    condition="visible",
                    passed=True,
                )
            )
            evidence.finalize()

            storage.save_evidence(evidence)
            loaded = storage.load_evidence(evidence.run_id)

            assert loaded is not None
            assert len(loaded.steps) == 1
            assert len(loaded.steps[0].artifacts) == 2
            assert len(loaded.assertions) == 1

    def test_load_evidence_normalizes_legacy_naive_timestamps_to_utc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "run-legacy"
            run_dir = Path(tmpdir) / run_id
            run_dir.mkdir(parents=True)
            (run_dir / "evidence.json").write_text(json.dumps({
                "evidence_id": "evidence-legacy",
                "plan_id": "plan-legacy",
                "run_id": run_id,
                "version": "1.0.0",
                "status": "success",
                "started_at": "2026-04-09T10:00:00",
                "finished_at": "2026-04-09T10:00:01",
                "duration_ms": 1000,
                "steps": [],
            }))

            storage = EvidenceStorage(Path(tmpdir))
            loaded = storage.load_evidence(run_id)

            assert loaded is not None
            assert loaded.started_at.tzinfo == timezone.utc
            assert loaded.finished_at.tzinfo == timezone.utc

    def test_save_and_load_preserves_structured_success_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EvidenceStorage(Path(tmpdir))
            evidence = storage.create_run("plan-structured-success")
            evidence.steps.append(
                StepEvidence(
                    step_id="s1",
                    action="element_click",
                    status=StepStatus.SUCCESS,
                    cli_command=CLICommand(
                        command=["mac", "element", "click", "--name", "OK"],
                        exit_code=0,
                        session_id="s1",
                        resolved_element={"ref": "e7"},
                        snapshot={"snapshot_id": "snap-1", "elements": []},
                        actionability_used={"actionable": True, "checks": {}},
                        upstream_duration_ms=321,
                    ),
                )
            )
            evidence.finalize()

            storage.save_evidence(evidence)
            loaded = storage.load_evidence(evidence.run_id)

            assert loaded is not None
            cli = loaded.steps[0].cli_command
            assert cli is not None
            assert cli.session_id == "s1"
            assert cli.resolved_element == {"ref": "e7"}
            assert cli.snapshot == {"snapshot_id": "snap-1", "elements": []}
            assert cli.actionability_used == {"actionable": True, "checks": {}}
            assert cli.upstream_duration_ms == 321


class TestEvidenceCollector:
    def test_execute_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector(Path(tmpdir))
            step = collector.execute_and_collect("s1", "test", ["echo", "hello"])
            assert step.status == StepStatus.SUCCESS
            assert step.cli_command.exit_code == 0
            assert "hello" in step.cli_command.stdout
    
    def test_execute_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector(Path(tmpdir))
            step = collector.execute_and_collect("s2", "test", ["false"])
            assert step.status == StepStatus.FAILURE
            assert step.cli_command.exit_code != 0
    
    def test_retry_policy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector(Path(tmpdir))
            step = collector.execute_and_collect(
                "s3", "test", ["false"],
                retry_policy={"max_attempts": 2, "delay_ms": 10}
            )
            assert step.retry_count == 2
            assert step.status == StepStatus.FAILURE

    @patch("src.evidence.collector.subprocess.run")
    def test_execute_and_collect_uses_argv_without_shell(self, mock_run):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            collector = EvidenceCollector(Path(tmpdir))

            collector.execute_and_collect("s4", "test", ["echo", "ok"])

            _, kwargs = mock_run.call_args
            assert kwargs["shell"] is False
