"""
Evaluator - Analyzes run evidence and produces evaluation results.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.evidence.types import RunEvidence, StepEvidence, StepStatus, RunStatus
from .classifier import FailureClassifier, ClassificationResult, RepairStrategy


class EvaluationVerdict(Enum):
    """Overall evaluation verdict."""
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NEEDS_REVIEW = "needs_review"


class NextAction(Enum):
    """Recommended next action."""
    DONE = "done"
    RETRY_FAILED = "retry_failed"
    RESTART_AND_RETRY = "restart_and_retry"
    REPLAN = "replan"
    ABORT = "abort"
    HUMAN_REVIEW = "human_review"


@dataclass
class StepEvaluation:
    """Evaluation of a single step."""
    step_id: str
    passed: bool
    expected_outcome: str
    actual_outcome: str
    classification: Optional[ClassificationResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "step_id": self.step_id,
            "passed": self.passed,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
        }
        if self.classification:
            result["classification"] = self.classification.to_dict()
        return result


@dataclass
class EvaluationResult:
    """Complete evaluation of a run."""
    run_id: str
    verdict: EvaluationVerdict
    next_action: NextAction
    total_steps: int
    passed_steps: int
    failed_steps: int
    step_evaluations: List[StepEvaluation] = field(default_factory=list)
    failure_summary: str = ""
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict.value,
            "next_action": self.next_action.value,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "step_evaluations": [s.to_dict() for s in self.step_evaluations],
            "failure_summary": self.failure_summary,
            "confidence": self.confidence,
        }


class Evaluator:
    """Evaluates run evidence and determines next actions."""
    
    def __init__(self):
        self.classifier = FailureClassifier()
    
    def evaluate(self, evidence: RunEvidence) -> EvaluationResult:
        """
        Evaluate a completed run.
        
        Args:
            evidence: Run evidence to evaluate
            
        Returns:
            EvaluationResult with verdict and recommendations
        """
        step_evals = []
        passed = 0
        failed = 0
        classifications = []
        
        for step in evidence.steps:
            if step.status == StepStatus.SUCCESS:
                passed += 1
                eval_result = StepEvaluation(
                    step_id=step.step_id,
                    passed=True,
                    expected_outcome="success",
                    actual_outcome="success",
                )
            else:
                failed += 1
                classification = self.classifier.classify(step)
                classifications.append(classification)
                eval_result = StepEvaluation(
                    step_id=step.step_id,
                    passed=False,
                    expected_outcome="success",
                    actual_outcome=f"failed: {step.error.message if step.error else 'unknown'}",
                    classification=classification,
                )
            step_evals.append(eval_result)
        
        # Determine verdict
        if failed == 0:
            verdict = EvaluationVerdict.PASS
            next_action = NextAction.DONE
            failure_summary = ""
        elif passed > 0:
            verdict = EvaluationVerdict.PARTIAL
            next_action, failure_summary = self._determine_next_action(classifications)
        else:
            verdict = EvaluationVerdict.FAIL
            next_action, failure_summary = self._determine_next_action(classifications)
        
        # Check for human review requirements
        if any(c.requires_human for c in classifications):
            verdict = EvaluationVerdict.NEEDS_REVIEW
            if next_action != NextAction.ABORT:
                next_action = NextAction.HUMAN_REVIEW
        
        # Calculate confidence
        confidence = self._calculate_confidence(classifications)
        
        return EvaluationResult(
            run_id=evidence.run_id,
            verdict=verdict,
            next_action=next_action,
            total_steps=len(evidence.steps),
            passed_steps=passed,
            failed_steps=failed,
            step_evaluations=step_evals,
            failure_summary=failure_summary,
            confidence=confidence,
        )
    
    def _determine_next_action(self, classifications: List[ClassificationResult]) -> tuple:
        """Determine the best next action based on failure classifications."""
        if not classifications:
            return NextAction.DONE, ""
        
        # Count strategies
        strategy_counts: Dict[RepairStrategy, int] = {}
        for c in classifications:
            strategy_counts[c.recommended_strategy] = strategy_counts.get(c.recommended_strategy, 0) + 1
        
        # Priority order for strategies
        priority = [
            RepairStrategy.ABORT,
            RepairStrategy.HUMAN_REVIEW,
            RepairStrategy.RESTART_SESSION,
            RepairStrategy.REPLAN_STEP,
            RepairStrategy.RETRY,
            RepairStrategy.SKIP,
        ]
        
        for strategy in priority:
            if strategy in strategy_counts:
                action_map = {
                    RepairStrategy.ABORT: NextAction.ABORT,
                    RepairStrategy.HUMAN_REVIEW: NextAction.HUMAN_REVIEW,
                    RepairStrategy.RESTART_SESSION: NextAction.RESTART_AND_RETRY,
                    RepairStrategy.REPLAN_STEP: NextAction.REPLAN,
                    RepairStrategy.RETRY: NextAction.RETRY_FAILED,
                    RepairStrategy.SKIP: NextAction.DONE,
                }
                
                summaries = [c.details for c in classifications if c.recommended_strategy == strategy]
                return action_map.get(strategy, NextAction.HUMAN_REVIEW), "; ".join(summaries[:3])
        
        return NextAction.HUMAN_REVIEW, "Unable to determine action"
    
    def _calculate_confidence(self, classifications: List[ClassificationResult]) -> float:
        """Calculate overall confidence in the evaluation."""
        if not classifications:
            return 1.0
        return sum(c.confidence for c in classifications) / len(classifications)
    
    def should_retry(self, evidence: RunEvidence) -> bool:
        """Quick check if retry is likely to help."""
        for step in evidence.steps:
            if step.status != StepStatus.SUCCESS:
                classification = self.classifier.classify(step)
                if classification.retry_likely_to_help:
                    return True
        return False
    
    def get_failed_steps(self, evidence: RunEvidence) -> List[str]:
        """Get list of failed step IDs."""
        return [s.step_id for s in evidence.steps if s.status != StepStatus.SUCCESS]
