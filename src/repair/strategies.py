"""
Repair Strategies - Different approaches to fixing failures.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import subprocess
import time

from src.evidence.types import StepEvidence, StepStatus, RepairAttempt


@dataclass
class StrategyResult:
    """Result of applying a repair strategy."""
    success: bool
    step_evidence: Optional[StepEvidence] = None
    details: str = ""
    should_continue: bool = True  # Whether to try next step


class RepairStrategyBase(ABC):
    """Base class for repair strategies."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""
        pass
    
    @abstractmethod
    def can_handle(self, step: StepEvidence) -> bool:
        """Check if this strategy can handle the failure."""
        pass
    
    @abstractmethod
    def apply(self, step: StepEvidence, context: Dict[str, Any]) -> StrategyResult:
        """Apply the repair strategy."""
        pass


class RetryStrategy(RepairStrategyBase):
    """Simple retry with backoff."""
    
    name = "retry"
    
    def __init__(self, max_retries: int = 3, backoff_ms: int = 1000):
        self.max_retries = max_retries
        self.backoff_ms = backoff_ms
    
    def can_handle(self, step: StepEvidence) -> bool:
        """Retry works for transient failures."""
        if not step.error:
            return False
        # Honor fsq-mac retryable flag if available
        if step.error.fsq_retryable is True:
            return True
        from src.evidence.types import FailureClassification
        retryable = [
            FailureClassification.ENVIRONMENT_FAILURE,
            FailureClassification.OBSERVATION_INSUFFICIENT,
        ]
        return step.error.classification in retryable
    
    def apply(self, step: StepEvidence, context: Dict[str, Any]) -> StrategyResult:
        """Retry the command."""
        if not step.cli_command:
            return StrategyResult(success=False, details="No command to retry")

        for attempt in range(self.max_retries):
            time.sleep(self.backoff_ms * (attempt + 1) / 1000.0)
            
            try:
                result = subprocess.run(
                    step.cli_command.command, shell=False, capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    from src.evidence.types import CLICommand
                    new_evidence = StepEvidence(
                        step_id=step.step_id,
                        action=step.action,
                        status=StepStatus.SUCCESS,
                        cli_command=CLICommand(
                            command=step.cli_command.command,
                            exit_code=0,
                            stdout=result.stdout,
                            stderr=result.stderr,
                        ),
                        retry_count=attempt + 1,
                    )
                    return StrategyResult(
                        success=True,
                        step_evidence=new_evidence,
                        details=f"Succeeded on retry {attempt + 1}",
                    )
            except Exception as e:
                continue
        
        return StrategyResult(
            success=False,
            details=f"Failed after {self.max_retries} retries",
        )


class RestartStrategy(RepairStrategyBase):
    """Restart session and retry."""
    
    name = "restart_session"
    
    def __init__(self, mac_cli: str = "mac"):
        self.mac_cli = mac_cli
    
    def can_handle(self, step: StepEvidence) -> bool:
        """Handle session-related failures."""
        if not step.error:
            return False
        from src.evidence.types import FailureClassification
        return step.error.classification == FailureClassification.ENVIRONMENT_FAILURE
    
    def apply(self, step: StepEvidence, context: Dict[str, Any]) -> StrategyResult:
        """Restart session and retry."""
        try:
            # End existing session
            subprocess.run([self.mac_cli, "session", "end"], capture_output=True, timeout=10)
            time.sleep(1)
            
            # Start new session
            result = subprocess.run(
                [self.mac_cli, "session", "start"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return StrategyResult(
                    success=False,
                    details=f"Failed to restart session: {result.stderr}",
                )
            
            # Update context with new session
            context["session_restarted"] = True
            
            # Retry the original command
            if step.cli_command:
                result = subprocess.run(
                    step.cli_command.command, shell=False, capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    from src.evidence.types import CLICommand
                    new_evidence = StepEvidence(
                        step_id=step.step_id,
                        action=step.action,
                        status=StepStatus.SUCCESS,
                        cli_command=CLICommand(
                            command=step.cli_command.command,
                            exit_code=0,
                            stdout=result.stdout,
                            stderr=result.stderr,
                        ),
                    )
                    return StrategyResult(
                        success=True,
                        step_evidence=new_evidence,
                        details="Succeeded after session restart",
                    )
            
            return StrategyResult(
                success=False,
                details="Session restarted but command still failed",
            )
            
        except Exception as e:
            return StrategyResult(success=False, details=str(e))


class ReplanStrategy(RepairStrategyBase):
    """Replan the failed step with alternative approach."""
    
    name = "replan_step"
    
    def __init__(self):
        self.alternatives = {
            "click": ["element_click", "input_click_at"],
            "type": ["element_type", "type_text"],
            "wait": ["wait_for_element", "wait"],
        }
    
    def can_handle(self, step: StepEvidence) -> bool:
        """Handle observation failures that might need different approach."""
        if not step.error:
            return False
        from src.evidence.types import FailureClassification
        return step.error.classification in [
            FailureClassification.OBSERVATION_INSUFFICIENT,
            FailureClassification.PRECONDITION_MISSING,
        ]
    
    def apply(self, step: StepEvidence, context: Dict[str, Any]) -> StrategyResult:
        """Suggest alternative approach."""
        action = step.action
        
        if action in self.alternatives:
            alts = self.alternatives[action]
            return StrategyResult(
                success=False,
                should_continue=True,
                details=f"Suggested alternatives: {', '.join(alts)}",
            )
        
        return StrategyResult(
            success=False,
            details=f"No alternative found for action: {action}",
        )


class SkipStrategy(RepairStrategyBase):
    """Skip the failed step and continue."""
    
    name = "skip"
    
    def can_handle(self, step: StepEvidence) -> bool:
        """Can skip any step if configured."""
        return True
    
    def apply(self, step: StepEvidence, context: Dict[str, Any]) -> StrategyResult:
        """Mark step as skipped."""
        from src.evidence.types import StepEvidence
        skipped = StepEvidence(
            step_id=step.step_id,
            action=step.action,
            status=StepStatus.SKIPPED,
        )
        return StrategyResult(
            success=True,
            step_evidence=skipped,
            details="Step skipped per policy",
            should_continue=True,
        )
