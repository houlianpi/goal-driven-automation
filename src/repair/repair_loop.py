"""
Repair Loop - Orchestrates failure recovery.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.evidence.types import (
    RunEvidence, StepEvidence, StepStatus, RepairAttempt, RunStatus
)
from src.evaluator.evaluator import Evaluator, EvaluationResult, NextAction
from src.evaluator.classifier import RepairStrategy
from .strategies import (
    RepairStrategyBase, RetryStrategy, RestartStrategy,
    ReplanStrategy, SkipStrategy, StrategyResult
)


class RepairOutcome(Enum):
    """Outcome of repair loop."""
    RECOVERED = "recovered"
    PARTIAL = "partial"
    FAILED = "failed"
    ABORTED = "aborted"
    NEEDS_HUMAN = "needs_human"


@dataclass
class RepairResult:
    """Result of repair loop execution."""
    outcome: RepairOutcome
    original_evidence: RunEvidence
    repaired_evidence: Optional[RunEvidence] = None
    repair_attempts: List[RepairAttempt] = field(default_factory=list)
    final_evaluation: Optional[EvaluationResult] = None
    details: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "repair_attempts": [r.to_dict() for r in self.repair_attempts],
            "details": self.details,
            "final_evaluation": self.final_evaluation.to_dict() if self.final_evaluation else None,
        }


class RepairLoop:
    """Orchestrates failure recovery strategies."""
    
    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations
        self.evaluator = Evaluator()
        
        # Strategy chain ordered by priority
        self.strategies: List[RepairStrategyBase] = [
            RetryStrategy(max_retries=2),
            RestartStrategy(),
            ReplanStrategy(),
            SkipStrategy(),
        ]
    
    def run(self, evidence: RunEvidence, context: Optional[Dict[str, Any]] = None) -> RepairResult:
        """
        Run repair loop on failed evidence.
        
        Args:
            evidence: Run evidence with failures
            context: Execution context (session info, etc.)
            
        Returns:
            RepairResult with outcome and details
        """
        context = context or {}
        repair_attempts: List[RepairAttempt] = []
        
        # Initial evaluation
        evaluation = self.evaluator.evaluate(evidence)
        
        # Already successful
        if evaluation.next_action == NextAction.DONE:
            return RepairResult(
                outcome=RepairOutcome.RECOVERED,
                original_evidence=evidence,
                repaired_evidence=evidence,
                final_evaluation=evaluation,
                details="No repair needed",
            )
        
        # Check if should abort
        if evaluation.next_action == NextAction.ABORT:
            return RepairResult(
                outcome=RepairOutcome.ABORTED,
                original_evidence=evidence,
                final_evaluation=evaluation,
                details="Abort recommended, no repair attempted",
            )
        
        # Check if human review needed
        if evaluation.next_action == NextAction.HUMAN_REVIEW:
            return RepairResult(
                outcome=RepairOutcome.NEEDS_HUMAN,
                original_evidence=evidence,
                final_evaluation=evaluation,
                details="Human review required",
            )
        
        # Attempt repairs
        current_evidence = self._clone_evidence(evidence)
        
        for iteration in range(self.max_iterations):
            failed_steps = self._get_failed_steps(current_evidence)
            
            if not failed_steps:
                break
            
            # Try to repair each failed step
            repaired_any = False
            
            for step in failed_steps:
                strategy, result = self._try_repair(step, context)
                
                if strategy:
                    attempt = RepairAttempt(
                        step_id=step.step_id,
                        failure_type=step.error.classification.value if step.error else "unknown",
                        strategy=strategy.name,
                        attempt_number=iteration + 1,
                        success=result.success,
                        details=result.details,
                    )
                    repair_attempts.append(attempt)
                    current_evidence.repairs.append(attempt)
                    
                    if result.success and result.step_evidence:
                        self._update_step(current_evidence, result.step_evidence)
                        repaired_any = True
            
            if not repaired_any:
                break
        
        # Final evaluation
        final_evaluation = self.evaluator.evaluate(current_evidence)
        
        # Determine outcome
        failed_count = len(self._get_failed_steps(current_evidence))
        original_failed = len(self._get_failed_steps(evidence))
        
        if failed_count == 0:
            outcome = RepairOutcome.RECOVERED
            current_evidence.status = RunStatus.SUCCESS
        elif failed_count < original_failed:
            outcome = RepairOutcome.PARTIAL
            current_evidence.status = RunStatus.PARTIAL
        else:
            outcome = RepairOutcome.FAILED
            current_evidence.status = RunStatus.FAILURE
        
        return RepairResult(
            outcome=outcome,
            original_evidence=evidence,
            repaired_evidence=current_evidence,
            repair_attempts=repair_attempts,
            final_evaluation=final_evaluation,
            details=f"Repaired {original_failed - failed_count}/{original_failed} failures",
        )
    
    def _try_repair(
        self, step: StepEvidence, context: Dict[str, Any]
    ) -> tuple:
        """Try repair strategies in order."""
        for strategy in self.strategies:
            if strategy.can_handle(step):
                result = strategy.apply(step, context)
                if result.success:
                    return strategy, result
        return None, StrategyResult(success=False)
    
    def _get_failed_steps(self, evidence: RunEvidence) -> List[StepEvidence]:
        """Get list of failed steps."""
        return [s for s in evidence.steps if s.status == StepStatus.FAILURE]
    
    def _clone_evidence(self, evidence: RunEvidence) -> RunEvidence:
        """Create a shallow copy of evidence for modification."""
        return RunEvidence(
            evidence_id=evidence.evidence_id,
            plan_id=evidence.plan_id,
            run_id=evidence.run_id,
            status=evidence.status,
            started_at=evidence.started_at,
            finished_at=evidence.finished_at,
            duration_ms=evidence.duration_ms,
            environment=evidence.environment,
            steps=list(evidence.steps),
            assertions=list(evidence.assertions),
            repairs=list(evidence.repairs),
            artifacts_dir=evidence.artifacts_dir,
        )
    
    def _update_step(self, evidence: RunEvidence, new_step: StepEvidence):
        """Update a step in evidence with repaired version."""
        for i, step in enumerate(evidence.steps):
            if step.step_id == new_step.step_id:
                new_step.status = StepStatus.REPAIRED
                evidence.steps[i] = new_step
                break
