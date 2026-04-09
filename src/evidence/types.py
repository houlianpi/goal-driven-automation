"""
Evidence Types - Data classes for evidence artifacts.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from src.time_utils import utc_now


class StepStatus(Enum):
    """Step execution status."""
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    REPAIRED = "repaired"


class RunStatus(Enum):
    """Overall run status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    ABORTED = "aborted"


class FailureClassification(Enum):
    """Error classification types."""
    PLAN_INVALID = "plan_invalid"
    PRECONDITION_MISSING = "precondition_missing"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    ENVIRONMENT_FAILURE = "environment_failure"
    OBSERVATION_INSUFFICIENT = "observation_insufficient"
    ASSERTION_FAILED = "assertion_failed"


@dataclass
class Artifact:
    """A captured artifact (screenshot, UI tree, etc.)."""
    type: str  # screenshot, ui_tree, log
    path: str  # Relative path within run directory
    captured_at: datetime = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "path": self.path,
            "captured_at": self.captured_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class CLICommand:
    """Executed CLI command details."""
    command: List[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
        }


@dataclass
class StepError:
    """Error information for a failed step."""
    type: str
    message: str
    classification: FailureClassification
    stacktrace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "message": self.message,
            "classification": self.classification.value,
            "stacktrace": self.stacktrace,
        }


@dataclass
class StepEvidence:
    """Evidence for a single step execution."""
    step_id: str
    action: str
    status: StepStatus
    started_at: datetime = field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    cli_command: Optional[CLICommand] = None
    error: Optional[StepError] = None
    artifacts: List[Artifact] = field(default_factory=list)
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "step_id": self.step_id,
            "action": self.action,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
        }
        if self.cli_command:
            result["cli_command"] = self.cli_command.to_dict()
        if self.error:
            result["error"] = self.error.to_dict()
        if self.artifacts:
            result["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return result


@dataclass
class AssertionResult:
    """Result of an assertion."""
    assertion_id: str
    step_id: str
    condition: str
    passed: bool
    actual_value: Optional[str] = None
    expected_value: Optional[str] = None
    review_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "step_id": self.step_id,
            "condition": self.condition,
            "passed": self.passed,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "review_required": self.review_required,
        }


AssertionResultLegacy = AssertionResult


@dataclass
class RepairAttempt:
    """Record of a repair attempt."""
    step_id: str
    failure_type: str
    strategy: str  # retry, restart_session, replan_step, skip, human_review
    attempt_number: int
    success: bool
    details: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "failure_type": self.failure_type,
            "strategy": self.strategy,
            "attempt_number": self.attempt_number,
            "success": self.success,
            "details": self.details,
        }


@dataclass
class Environment:
    """Execution environment details."""
    os: str
    os_version: str
    hostname: str
    executor_version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "os": self.os,
            "os_version": self.os_version,
            "hostname": self.hostname,
            "executor_version": self.executor_version,
        }


@dataclass
class RunEvidence:
    """Complete evidence for a plan execution run."""
    evidence_id: str = field(default_factory=lambda: f"evidence-{uuid.uuid4().hex[:12]}")
    plan_id: str = ""
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    version: str = "1.0.0"
    status: RunStatus = RunStatus.SUCCESS
    started_at: datetime = field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    environment: Optional[Environment] = None
    steps: List[StepEvidence] = field(default_factory=list)
    assertions: List[AssertionResult] = field(default_factory=list)
    repairs: List[RepairAttempt] = field(default_factory=list)
    artifacts_dir: str = ""
    
    def add_step(self, step: StepEvidence):
        """Add a step evidence."""
        self.steps.append(step)
        if step.status == StepStatus.FAILURE:
            self.status = RunStatus.FAILURE
        elif step.status in {StepStatus.REPAIRED, StepStatus.SKIPPED} and self.status == RunStatus.SUCCESS:
            self.status = RunStatus.PARTIAL
    
    def finalize(self):
        """Finalize the run evidence."""
        self.finished_at = utc_now()
        if self.started_at:
            self.duration_ms = int((self.finished_at - self.started_at).total_seconds() * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "evidence_id": self.evidence_id,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "version": self.version,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "steps": [s.to_dict() for s in self.steps],
        }
        if self.environment:
            result["environment"] = self.environment.to_dict()
        if self.assertions:
            result["assertions"] = [a.to_dict() for a in self.assertions]
        if self.repairs:
            result["repairs"] = [r.to_dict() for r in self.repairs]
        if self.artifacts_dir:
            result["artifacts"] = {
                "screenshots_dir": f"{self.artifacts_dir}/screenshots/",
                "ui_trees_dir": f"{self.artifacts_dir}/ui_trees/",
                "logs_dir": f"{self.artifacts_dir}/logs/",
            }
        return result

    def clone(self) -> "RunEvidence":
        """Create a detached deep copy for repair and mutation flows."""
        return deepcopy(self)
