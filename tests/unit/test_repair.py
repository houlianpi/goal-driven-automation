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
        assert result.outcome in [RepairOutcome.RECOVERED, RepairOutcome.PARTIAL]
        assert len(result.repair_attempts) > 0
    
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
