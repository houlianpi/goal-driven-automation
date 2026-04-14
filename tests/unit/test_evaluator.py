"""Unit tests for Evaluator and Failure Classifier."""
import pytest
from src.evidence.types import (
    StepEvidence, StepStatus, StepError, FailureClassification,
    CLICommand, RunEvidence, RunStatus,
)
from src.evaluator.classifier import FailureClassifier, RepairStrategy
from src.evaluator.evaluator import Evaluator, EvaluationVerdict, NextAction


class TestFailureClassifier:
    @pytest.fixture
    def classifier(self):
        return FailureClassifier()
    
    def test_classify_success(self, classifier):
        step = StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS)
        assert classifier.classify(step) is None

    def test_classify_repaired(self, classifier):
        step = StepEvidence(step_id="s1", action="click", status=StepStatus.REPAIRED)
        assert classifier.classify(step) is None

    def test_classify_skipped(self, classifier):
        step = StepEvidence(step_id="s1", action="click", status=StepStatus.SKIPPED)
        assert classifier.classify(step) is None
    
    def test_classify_with_error(self, classifier):
        error = StepError("Timeout", "Command timed out", FailureClassification.ENVIRONMENT_FAILURE)
        step = StepEvidence(step_id="s2", action="click", status=StepStatus.FAILURE, error=error)
        result = classifier.classify(step)
        assert result.classification == FailureClassification.ENVIRONMENT_FAILURE
        assert result.confidence == 0.9
        assert result.retry_likely_to_help is True
    
    def test_classify_element_not_found(self, classifier):
        cli = CLICommand(command=["mac", "click"], exit_code=1, stderr="Element not found")
        step = StepEvidence(step_id="s3", action="click", status=StepStatus.FAILURE, cli_command=cli)
        result = classifier.classify(step)
        assert result.classification == FailureClassification.OBSERVATION_INSUFFICIENT
        assert result.recommended_strategy == RepairStrategy.RETRY
    
    def test_classify_permission_denied(self, classifier):
        cli = CLICommand(command=["mac", "run"], exit_code=1, stderr="Permission denied")
        step = StepEvidence(step_id="s4", action="run", status=StepStatus.FAILURE, cli_command=cli)
        result = classifier.classify(step)
        assert result.classification == FailureClassification.PRECONDITION_MISSING
        assert result.recommended_strategy == RepairStrategy.REPLAN_STEP
    
    def test_classify_command_not_found(self, classifier):
        cli = CLICommand(command=["invalid"], exit_code=127, stderr="command not found")
        step = StepEvidence(step_id="s5", action="run", status=StepStatus.FAILURE, cli_command=cli)
        result = classifier.classify(step)
        assert result.classification == FailureClassification.CAPABILITY_UNAVAILABLE
        assert result.recommended_strategy == RepairStrategy.ABORT


class TestEvaluator:
    @pytest.fixture
    def evaluator(self):
        return Evaluator()
    
    def test_evaluate_all_success(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
        run.add_step(StepEvidence(step_id="s2", action="click", status=StepStatus.SUCCESS))
        result = evaluator.evaluate(run)
        assert result.verdict == EvaluationVerdict.PASS
        assert result.next_action == NextAction.DONE
        assert result.passed_steps == 2
        assert result.failed_steps == 0
    
    def test_evaluate_partial_failure(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
        error = StepError("Timeout", "timed out", FailureClassification.ENVIRONMENT_FAILURE)
        run.add_step(StepEvidence(step_id="s2", action="click", status=StepStatus.FAILURE, error=error))
        result = evaluator.evaluate(run)
        assert result.verdict == EvaluationVerdict.PARTIAL
        assert result.passed_steps == 1
        assert result.failed_steps == 1

    def test_evaluate_repaired_step_is_passed_but_partial(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
        run.add_step(StepEvidence(step_id="s2", action="click", status=StepStatus.REPAIRED))

        result = evaluator.evaluate(run)

        assert result.verdict == EvaluationVerdict.PARTIAL
        assert result.next_action == NextAction.DONE
        assert result.passed_steps == 2
        assert result.failed_steps == 0

    def test_evaluate_skipped_step_is_partial_without_retry(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
        run.add_step(StepEvidence(step_id="s2", action="click", status=StepStatus.SKIPPED))

        result = evaluator.evaluate(run)

        assert result.verdict == EvaluationVerdict.PARTIAL
        assert result.next_action == NextAction.DONE
        assert result.passed_steps == 1
        assert result.failed_steps == 0
    
    def test_evaluate_all_failure(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        error = StepError("Error", "failed", FailureClassification.ENVIRONMENT_FAILURE)
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.FAILURE, error=error))
        result = evaluator.evaluate(run)
        assert result.verdict == EvaluationVerdict.FAIL
        assert result.failed_steps == 1
    
    def test_evaluate_needs_review(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        error = StepError("AssertFailed", "assertion failed", FailureClassification.ASSERTION_FAILED)
        run.add_step(StepEvidence(step_id="s1", action="assert", status=StepStatus.FAILURE, error=error))
        result = evaluator.evaluate(run)
        assert result.verdict == EvaluationVerdict.NEEDS_REVIEW
        assert result.next_action == NextAction.HUMAN_REVIEW
    
    def test_should_retry(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        error = StepError("Timeout", "timed out", FailureClassification.ENVIRONMENT_FAILURE)
        run.add_step(StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error))
        assert evaluator.should_retry(run) is True

    def test_should_not_retry_repaired_or_skipped_steps(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="click", status=StepStatus.REPAIRED))
        run.add_step(StepEvidence(step_id="s2", action="assert", status=StepStatus.SKIPPED))
        assert evaluator.should_retry(run) is False
    
    def test_get_failed_steps(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.SUCCESS))
        run.add_step(StepEvidence(step_id="s2", action="click", status=StepStatus.FAILURE))
        run.add_step(StepEvidence(step_id="s3", action="type", status=StepStatus.FAILURE))
        failed = evaluator.get_failed_steps(run)
        assert failed == ["s2", "s3"]

    def test_get_failed_steps_excludes_repaired_and_skipped(self, evaluator):
        run = RunEvidence(plan_id="plan-test")
        run.add_step(StepEvidence(step_id="s1", action="launch", status=StepStatus.REPAIRED))
        run.add_step(StepEvidence(step_id="s2", action="click", status=StepStatus.SKIPPED))
        run.add_step(StepEvidence(step_id="s3", action="type", status=StepStatus.FAILURE))
        failed = evaluator.get_failed_steps(run)
        assert failed == ["s3"]


class TestClassifierV030:
    """Tests for fsq-mac v0.3.0 structured error code classification."""

    @pytest.fixture
    def classifier(self):
        return FailureClassifier()

    def test_classify_from_output_prefers_json_error_code(self, classifier):
        """Structured error.code takes priority over regex patterns."""
        cli = CLICommand(
            command=["mac", "element", "click"],
            exit_code=1,
            stdout="",
            stderr="Element not found",
            parsed_response={
                "ok": False,
                "error": {"code": "ELEMENT_NOT_FOUND", "message": "No match", "retryable": True},
            },
        )
        classification, confidence, details = classifier._classify_from_output(cli)
        assert classification == FailureClassification.OBSERVATION_INSUFFICIENT
        assert confidence == 0.95
        assert "fsq-mac error" in details

    def test_classify_from_output_falls_back_to_regex(self, classifier):
        """Without parsed_response, fallback to regex patterns."""
        cli = CLICommand(
            command=["mac", "element", "click"],
            exit_code=1,
            stdout="",
            stderr="Element not found",
        )
        classification, confidence, _ = classifier._classify_from_output(cli)
        assert classification == FailureClassification.OBSERVATION_INSUFFICIENT
        assert confidence == 0.8

    def test_classify_honors_fsq_retryable_true(self, classifier):
        """fsq_retryable=True overrides default retry_likely_to_help."""
        error = StepError(
            "ASSERTION_FAILED", "Failed",
            FailureClassification.ASSERTION_FAILED,
            fsq_retryable=True,
        )
        step = StepEvidence(step_id="s1", action="assert", status=StepStatus.FAILURE, error=error)
        result = classifier.classify(step)
        assert result.retry_likely_to_help is True
        assert result.recommended_strategy == RepairStrategy.RETRY

    def test_classify_honors_fsq_retryable_false(self, classifier):
        """fsq_retryable=False overrides default retry_likely_to_help."""
        error = StepError(
            "ELEMENT_NOT_FOUND", "No match",
            FailureClassification.OBSERVATION_INSUFFICIENT,
            fsq_retryable=False,
        )
        step = StepEvidence(step_id="s1", action="click", status=StepStatus.FAILURE, error=error)
        result = classifier.classify(step)
        assert result.retry_likely_to_help is False
