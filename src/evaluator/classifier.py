"""
Failure Classifier - Categorizes failures for repair decisions.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import re

from src.evidence.types import StepEvidence, StepStatus, FailureClassification, CLICommand


class RepairStrategy(Enum):
    """Recommended repair strategies."""
    RETRY = "retry"
    RESTART_SESSION = "restart_session"
    REPLAN_STEP = "replan_step"
    SKIP = "skip"
    ABORT = "abort"
    HUMAN_REVIEW = "human_review"


@dataclass
class ClassificationResult:
    """Result of failure classification."""
    classification: FailureClassification
    confidence: float  # 0.0 to 1.0
    recommended_strategy: RepairStrategy
    details: str
    retry_likely_to_help: bool
    requires_human: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification.value,
            "confidence": self.confidence,
            "recommended_strategy": self.recommended_strategy.value,
            "details": self.details,
            "retry_likely_to_help": self.retry_likely_to_help,
            "requires_human": self.requires_human,
        }


class FailureClassifier:
    """Classifies failures based on evidence patterns."""
    
    # Pattern-based classification rules
    PATTERNS = {
        FailureClassification.PLAN_INVALID: [
            r"invalid action",
            r"unknown action",
            r"missing required",
            r"schema validation",
            r"malformed",
        ],
        FailureClassification.PRECONDITION_MISSING: [
            r"permission denied",
            r"access denied",
            r"not authorized",
            r"app not running",
            r"window not found",
            r"session not started",
        ],
        FailureClassification.CAPABILITY_UNAVAILABLE: [
            r"command not found",
            r"not installed",
            r"no such file",
            r"binary not found",
            r"cli not available",
        ],
        FailureClassification.ENVIRONMENT_FAILURE: [
            r"timeout",
            r"connection refused",
            r"session lost",
            r"session expired",
            r"network error",
            r"appium.*disconnect",
        ],
        FailureClassification.OBSERVATION_INSUFFICIENT: [
            r"element not found",
            r"locator failed",
            r"no matching element",
            r"ui tree empty",
            r"screenshot failed",
        ],
        FailureClassification.ASSERTION_FAILED: [
            r"assertion failed",
            r"expected.*but got",
            r"condition not met",
            r"verification failed",
        ],
    }
    
    # Strategy recommendations per classification
    STRATEGY_MAP = {
        FailureClassification.PLAN_INVALID: (RepairStrategy.ABORT, False, True),
        FailureClassification.PRECONDITION_MISSING: (RepairStrategy.REPLAN_STEP, False, False),
        FailureClassification.CAPABILITY_UNAVAILABLE: (RepairStrategy.ABORT, False, True),
        FailureClassification.ENVIRONMENT_FAILURE: (RepairStrategy.RESTART_SESSION, True, False),
        FailureClassification.OBSERVATION_INSUFFICIENT: (RepairStrategy.RETRY, True, False),
        FailureClassification.ASSERTION_FAILED: (RepairStrategy.HUMAN_REVIEW, False, True),
    }
    
    def classify(self, step: StepEvidence) -> Optional[ClassificationResult]:
        """
        Classify a failed step.

        Args:
            step: Failed step evidence

        Returns:
            ClassificationResult with classification and recommendations
        """
        if step.status in {StepStatus.SUCCESS, StepStatus.REPAIRED, StepStatus.SKIPPED}:
            return None

        # Use existing error classification if available
        if step.error:
            classification = step.error.classification
            confidence = 0.9
            details = step.error.message

            # Override retry_likely_to_help from fsq_retryable if available
            strategy, retry_helps, needs_human = self.STRATEGY_MAP.get(
                classification,
                (RepairStrategy.HUMAN_REVIEW, False, True)
            )
            if step.error.fsq_retryable is not None:
                retry_helps = step.error.fsq_retryable
                if retry_helps and strategy not in (RepairStrategy.RETRY, RepairStrategy.RESTART_SESSION):
                    strategy = RepairStrategy.RETRY
        else:
            # Classify from CLI output (structured or regex)
            classification, confidence, details = self._classify_from_output(step.cli_command)
            strategy, retry_helps, needs_human = self.STRATEGY_MAP.get(
                classification,
                (RepairStrategy.HUMAN_REVIEW, False, True)
            )

        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            recommended_strategy=strategy,
            details=details,
            retry_likely_to_help=retry_helps,
            requires_human=needs_human,
        )
    
    # fsq-mac v0.3.0 error code → classification mapping
    _FSQ_ERROR_CLASSIFICATION = {
        "ELEMENT_NOT_FOUND": FailureClassification.OBSERVATION_INSUFFICIENT,
        "ELEMENT_AMBIGUOUS": FailureClassification.OBSERVATION_INSUFFICIENT,
        "ELEMENT_REFERENCE_STALE": FailureClassification.OBSERVATION_INSUFFICIENT,
        "ELEMENT_UNBOUND": FailureClassification.OBSERVATION_INSUFFICIENT,
        "ELEMENT_NOT_ACTIONABLE": FailureClassification.OBSERVATION_INSUFFICIENT,
        "GEOMETRY_UNRELIABLE": FailureClassification.OBSERVATION_INSUFFICIENT,
        "BACKEND_UNAVAILABLE": FailureClassification.ENVIRONMENT_FAILURE,
        "SESSION_NOT_FOUND": FailureClassification.ENVIRONMENT_FAILURE,
        "SESSION_EXPIRED": FailureClassification.ENVIRONMENT_FAILURE,
        "SESSION_CONFLICT": FailureClassification.ENVIRONMENT_FAILURE,
        "BACKEND_RPC_TIMEOUT": FailureClassification.ENVIRONMENT_FAILURE,
        "TIMEOUT": FailureClassification.ENVIRONMENT_FAILURE,
        "WINDOW_NOT_FOUND": FailureClassification.ENVIRONMENT_FAILURE,
        "ASSERTION_FAILED": FailureClassification.ASSERTION_FAILED,
        "TYPE_VERIFICATION_FAILED": FailureClassification.ASSERTION_FAILED,
        "PERMISSION_DENIED": FailureClassification.PRECONDITION_MISSING,
        "ACTION_BLOCKED": FailureClassification.PRECONDITION_MISSING,
        "APP_NOT_FOUND": FailureClassification.PRECONDITION_MISSING,
        "INVALID_ARGUMENT": FailureClassification.PLAN_INVALID,
        "TRACE_STEP_NOT_REPLAYABLE": FailureClassification.PLAN_INVALID,
        "INTERNAL_ERROR": FailureClassification.ENVIRONMENT_FAILURE,
    }

    def _classify_from_output(self, cli: Optional[CLICommand]) -> tuple:
        """Classify based on CLI output patterns."""
        if not cli:
            return (FailureClassification.ENVIRONMENT_FAILURE, 0.5, "No CLI output available")

        # Priority 1: structured fsq-mac JSON envelope error.code
        if cli.parsed_response and isinstance(cli.parsed_response.get("error"), dict):
            error_code = cli.parsed_response["error"].get("code", "")
            if error_code in self._FSQ_ERROR_CLASSIFICATION:
                message = cli.parsed_response["error"].get("message", error_code)
                return (self._FSQ_ERROR_CLASSIFICATION[error_code], 0.95, f"fsq-mac error: {message}")

        # Priority 2: regex-based pattern matching
        text = (cli.stdout + " " + cli.stderr).lower()

        for classification, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return (classification, 0.8, f"Matched pattern: {pattern}")

        # Default classification based on exit code
        if cli.exit_code == -1:
            return (FailureClassification.ENVIRONMENT_FAILURE, 0.6, "Command timed out")
        elif cli.exit_code == 127:
            return (FailureClassification.CAPABILITY_UNAVAILABLE, 0.9, "Command not found")
        elif cli.exit_code == 1:
            return (FailureClassification.ENVIRONMENT_FAILURE, 0.5, "Generic failure")

        return (FailureClassification.ENVIRONMENT_FAILURE, 0.4, "Unknown failure type")
    
    def classify_batch(self, steps: List[StepEvidence]) -> List[ClassificationResult]:
        """Classify multiple failed steps."""
        return [result for s in steps if s.status == StepStatus.FAILURE for result in [self.classify(s)] if result is not None]
