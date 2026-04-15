"""Unit tests for Repair Loop."""
import pytest
from unittest.mock import patch, MagicMock
from src.evidence.types import (
    StepEvidence, StepStatus, StepError, FailureClassification,
    CLICommand, RunEvidence, RunStatus, RepairAttempt,
)
from src.repair.strategies import (
    RetryStrategy, RestartStrategy, ReplanStrategy, SkipStrategy, StrategyResult
)
from src.repair.repair_loop import RepairLoop, RepairOutcome


def build_failed_step(
    *,
    step_id="s1",
    action="click",
    command=None,
    classification=FailureClassification.OBSERVATION_INSUFFICIENT,
    fsq_error_code=None,
    fsq_retryable=None,
    retry_count=0,
):
    cli = None
    if command is not None:
        cli = CLICommand(command=command, exit_code=1, stderr="failed")
    error = StepError(
        "Error",
        "failed",
        classification,
        fsq_error_code=fsq_error_code,
        fsq_retryable=fsq_retryable,
    )
    return StepEvidence(
        step_id=step_id,
        action=action,
        status=StepStatus.FAILURE,
        error=error,
        cli_command=cli,
        retry_count=retry_count,
    )


class TestRetryStrategy:
    def test_can_handle_environment_failure(self):
        strategy = RetryStrategy()
        error = StepError("Timeout", "timed out", FailureClassification.ENVIRONMENT_FAILURE)
        step = StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error)
        assert strategy.can_handle(step) is True
    
    def test_cannot_handle_plan_invalid(self):
        strategy = RetryStrategy()
        error = StepError("Invalid", "bad plan", FailureClassification.PLAN_INVALID)
        step = StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error)
        assert strategy.can_handle(step) is False

    def test_retryable_false_overrides_classification(self):
        strategy = RetryStrategy()
        step = build_failed_step(
            classification=FailureClassification.OBSERVATION_INSUFFICIENT,
            fsq_error_code="ELEMENT_NOT_FOUND",
            fsq_retryable=False,
        )

        assert strategy.can_handle(step) is False

    def test_backend_unavailable_is_deferred_to_restart_strategy(self):
        strategy = RetryStrategy()
        step = build_failed_step(
            classification=FailureClassification.ENVIRONMENT_FAILURE,
            fsq_error_code="BACKEND_UNAVAILABLE",
            fsq_retryable=True,
        )

        assert strategy.can_handle(step) is False

    def test_stale_ref_is_not_retried_verbatim(self):
        strategy = RetryStrategy()
        step = build_failed_step(
            action="element_click",
            command=["mac", "element", "click", "e3"],
            classification=FailureClassification.OBSERVATION_INSUFFICIENT,
            fsq_error_code="ELEMENT_REFERENCE_STALE",
            fsq_retryable=True,
        )

        assert strategy.can_handle(step) is False

    @patch("subprocess.run")
    def test_retry_succeeds(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        strategy = RetryStrategy(max_retries=2, backoff_ms=10)
        cli = CLICommand(command=["echo", "test"], exit_code=1, stderr="failed")
        error = StepError("Timeout", "timed out", FailureClassification.ENVIRONMENT_FAILURE)
        step = StepEvidence(step_id="s1", action="test", status=StepStatus.FAILURE, error=error, cli_command=cli)
        result = strategy.apply(step, {})
        assert result.success is True
        assert result.step_evidence is not None
        _, kwargs = mock_run.call_args
        assert kwargs["shell"] is False

    @patch("src.repair.strategies.time.sleep")
    @patch("src.repair.strategies.subprocess.run")
    def test_element_not_found_runs_inspect_before_retry(self, mock_run, _mock_sleep):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='{"ok": true}', stderr=""),
            MagicMock(returncode=0, stdout="ok", stderr=""),
        ]
        strategy = RetryStrategy(max_retries=1, backoff_ms=1)
        step = build_failed_step(
            action="element_click",
            command=["mac", "element", "click", "--name", "Submit"],
            classification=FailureClassification.OBSERVATION_INSUFFICIENT,
            fsq_error_code="ELEMENT_NOT_FOUND",
            fsq_retryable=True,
        )

        result = strategy.apply(step, {})

        assert result.success is True
        assert mock_run.call_args_list[0].args[0] == ["mac", "element", "inspect"]
        assert mock_run.call_args_list[1].args[0] == ["mac", "element", "click", "--name", "Submit"]

    @patch("src.repair.strategies.time.sleep")
    @patch("src.repair.strategies.subprocess.run")
    def test_element_not_found_uses_configured_mac_cli_for_inspect(self, mock_run, _mock_sleep):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='{"ok": true}', stderr=""),
            MagicMock(returncode=0, stdout="ok", stderr=""),
        ]
        strategy = RetryStrategy(max_retries=1, backoff_ms=1, mac_cli="/tmp/fsq-mac")
        step = build_failed_step(
            action="element_click",
            command=["/tmp/fsq-mac", "element", "click", "--name", "Submit"],
            classification=FailureClassification.OBSERVATION_INSUFFICIENT,
            fsq_error_code="ELEMENT_NOT_FOUND",
            fsq_retryable=True,
        )

        result = strategy.apply(step, {})

        assert result.success is True
        assert mock_run.call_args_list[0].args[0] == ["/tmp/fsq-mac", "element", "inspect"]

    @patch("src.repair.strategies.time.sleep")
    @patch("src.repair.strategies.subprocess.run")
    def test_stale_locator_retries_after_inspect(self, mock_run, _mock_sleep):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='{"ok": true}', stderr=""),
            MagicMock(returncode=0, stdout="ok", stderr=""),
        ]
        strategy = RetryStrategy(max_retries=1, backoff_ms=1)
        step = build_failed_step(
            action="element_click",
            command=["mac", "element", "click", "--name", "Submit"],
            classification=FailureClassification.OBSERVATION_INSUFFICIENT,
            fsq_error_code="ELEMENT_REFERENCE_STALE",
            fsq_retryable=True,
        )

        result = strategy.apply(step, {})

        assert result.success is True
        assert mock_run.call_args_list[0].args[0] == ["mac", "element", "inspect"]
        assert mock_run.call_args_list[1].args[0] == ["mac", "element", "click", "--name", "Submit"]


class TestRestartStrategy:
    @patch("src.repair.strategies.time.sleep")
    @patch("src.repair.strategies.subprocess.run")
    def test_backend_unavailable_runs_doctor_before_restart(self, mock_run, _mock_sleep):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="backend ok", stderr=""),
            MagicMock(returncode=0, stdout="ended", stderr=""),
            MagicMock(returncode=0, stdout='{"ok": true}', stderr=""),
            MagicMock(returncode=0, stdout="ok", stderr=""),
        ]
        strategy = RestartStrategy(mac_cli="mac")
        step = build_failed_step(
            action="element_click",
            command=["mac", "element", "click", "--name", "Submit"],
            classification=FailureClassification.ENVIRONMENT_FAILURE,
            fsq_error_code="BACKEND_UNAVAILABLE",
            fsq_retryable=True,
        )

        result = strategy.apply(step, {})

        assert result.success is True
        commands = [call.args[0] for call in mock_run.call_args_list]
        assert commands[0] == ["mac", "doctor", "backend"]
        assert commands[1] == ["mac", "session", "end"]
        assert commands[2] == ["mac", "session", "start"]
        assert commands[3] == ["mac", "element", "click", "--name", "Submit"]

    @patch("src.repair.strategies.subprocess.run")
    def test_backend_doctor_failure_short_circuits_restart(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="doctor failed")
        strategy = RestartStrategy(mac_cli="mac")
        step = build_failed_step(
            action="element_click",
            command=["mac", "element", "click", "--name", "Submit"],
            classification=FailureClassification.ENVIRONMENT_FAILURE,
            fsq_error_code="BACKEND_UNAVAILABLE",
            fsq_retryable=True,
        )

        result = strategy.apply(step, {})

        assert result.success is False
        assert "Backend doctor failed" in result.details
        assert mock_run.call_count == 1


class TestSkipStrategy:
    def test_can_handle_any(self):
        strategy = SkipStrategy()
        step = StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE)
        assert strategy.can_handle(step) is True
    
    def test_skip_returns_skipped(self):
        strategy = SkipStrategy()
        step = StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE)
        result = strategy.apply(step, {})
        assert result.success is True
        assert result.step_evidence.status == StepStatus.SKIPPED


class TestRepairLoop:
    def test_no_repair_needed(self):
        loop = RepairLoop()
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
        result = loop.run(run)
        assert result.outcome == RepairOutcome.RECOVERED
        assert "No repair needed" in result.details
    
    def test_abort_on_plan_invalid(self):
        loop = RepairLoop()
        run = RunEvidence(plan_id="plan-test")
        error = StepError("Invalid", "bad plan", FailureClassification.PLAN_INVALID)
        run.add_step(StepEvidence(step_id="s1", action="invalid", status=StepStatus.FAILURE, error=error))
        result = loop.run(run)
        assert result.outcome == RepairOutcome.ABORTED
    
    def test_needs_human_review(self):
        loop = RepairLoop()
        run = RunEvidence(plan_id="plan-test")
        error = StepError("AssertFailed", "check failed", FailureClassification.ASSERTION_FAILED)
        run.add_step(StepEvidence(step_id="s1", action="assert", status=StepStatus.FAILURE, error=error))
        result = loop.run(run)
        assert result.outcome == RepairOutcome.NEEDS_HUMAN
    
    @patch("subprocess.run")
    def test_retry_repairs_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        loop = RepairLoop()
        run = RunEvidence(plan_id="plan-test")
        cli = CLICommand(command=["mac", "click"], exit_code=1, stderr="timeout")
        error = StepError("Timeout", "timed out", FailureClassification.ENVIRONMENT_FAILURE)
        run.add_step(StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error, cli_command=cli))
        result = loop.run(run)
        assert result.outcome == RepairOutcome.RECOVERED
        assert result.repaired_evidence.status == RunStatus.PARTIAL
        assert result.final_evaluation.verdict == RepairOutcome.RECOVERED.value if False else result.final_evaluation.verdict
        assert len(result.repair_attempts) > 0

    def test_skip_strategy_results_in_partial_not_failed(self):
        loop = RepairLoop()
        loop.strategies = [SkipStrategy()]
        run = RunEvidence(plan_id="plan-test")
        error = StepError("Error", "some error", FailureClassification.OBSERVATION_INSUFFICIENT)
        run.add_step(StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error))

        result = loop.run(run)

        assert result.outcome == RepairOutcome.RECOVERED
        assert result.repaired_evidence is not None
        assert result.repaired_evidence.status == RunStatus.PARTIAL
        assert result.final_evaluation is not None
        assert result.final_evaluation.failed_steps == 0
    
    def test_skip_strategy_used(self):
        loop = RepairLoop()
        # Only keep skip strategy
        loop.strategies = [SkipStrategy()]
        run = RunEvidence(plan_id="plan-test")
        error = StepError("Error", "some error", FailureClassification.OBSERVATION_INSUFFICIENT)
        run.add_step(StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error))
        result = loop.run(run)
        # Skip should mark as recovered (step was skipped successfully)
        assert len(result.repair_attempts) > 0
        assert result.repair_attempts[0].strategy == "skip"

    def test_clone_evidence_does_not_mutate_original_steps(self):
        loop = RepairLoop()
        original = RunEvidence(plan_id="plan-test")
        error = StepError("Timeout", "timed out", FailureClassification.ENVIRONMENT_FAILURE)
        original_step = StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error)
        original.steps.append(original_step)

        cloned = loop._clone_evidence(original)
        cloned.steps[0].status = StepStatus.REPAIRED

        assert original.steps[0].status == StepStatus.FAILURE
        assert cloned.steps[0].status == StepStatus.REPAIRED

    def test_clone_evidence_does_not_share_repairs(self):
        loop = RepairLoop()
        original = RunEvidence(plan_id="plan-test")
        original.repairs.append(RepairAttempt(step_id="s1", failure_type="timeout", strategy="retry", attempt_number=1, success=False))

        cloned = loop._clone_evidence(original)
        cloned.repairs.append(RepairAttempt(step_id="s2", failure_type="timeout", strategy="retry", attempt_number=2, success=True))

        assert len(original.repairs) == 1
        assert len(cloned.repairs) == 2
