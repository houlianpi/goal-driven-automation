"""
Mock Executor - Simulates execution for testing without fsq-mac CLI.
"""
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import json

from src.evidence.types import (
    RunEvidence, StepEvidence, StepStatus, RunStatus,
    CLICommand, StepError, FailureClassification, Artifact
)
from src.time_utils import utc_now


class MockExecutor:
    """Simulates plan execution for testing."""

    def __init__(self, runs_dir: Optional[Path] = None, failure_rate: float = 0.3):
        self.runs_dir = runs_dir or Path("data/runs")
        self.failure_rate = failure_rate
        self.mac_cli = os.environ.get("FSQ_MAC_CLI", "mac")
        self.forced_failures: Dict[str, str] = {}  # step_id -> error_type
    
    def force_failure(self, step_id: str, error_type: str = "timeout"):
        """Force a specific step to fail (for testing repair)."""
        self.forced_failures[step_id] = error_type
    
    def execute(self, plan: Dict[str, Any], run_id: Optional[str] = None) -> RunEvidence:
        """Execute a plan with simulated results."""
        run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        plan_id = plan.get("plan_id", "unknown")
        
        # Create run directory
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "screenshots").mkdir(exist_ok=True)
        (run_dir / "logs").mkdir(exist_ok=True)
        
        evidence = RunEvidence(plan_id=plan_id, run_id=run_id)
        evidence.artifacts_dir = str(run_dir)
        
        steps = plan.get("steps", [])
        
        for i, step in enumerate(steps):
            step_evidence = self._execute_step(step, run_dir, i)
            evidence.add_step(step_evidence)
            
            # Log step execution
            self._log_step(run_dir, step_evidence)
            
            # Stop on critical failure
            if step_evidence.status == StepStatus.FAILURE:
                if step.get("on_fail") == "abort":
                    break
        
        evidence.finalize()
        
        # Save evidence
        self._save_evidence(run_dir, evidence)
        
        return evidence
    
    def _execute_step(self, step: Dict[str, Any], run_dir: Path, index: int) -> StepEvidence:
        """Execute a single step with simulation."""
        step_id = step.get("step_id", f"s{index+1}")
        action = step.get("action", "unknown")
        params = step.get("params", step.get("args", {}))
        
        started_at = utc_now()
        time.sleep(0.1)  # Simulate execution time
        
        # Check for forced failure
        if step_id in self.forced_failures:
            return self._create_failure(step_id, action, self.forced_failures[step_id], started_at)
        
        # Random failure based on rate
        if random.random() < self.failure_rate:
            error_type = random.choice(["timeout", "element_not_found", "session_error"])
            return self._create_failure(step_id, action, error_type, started_at)
        
        # Success
        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        
        # Simulate CLI command with v0.3.0 JSON envelope
        command = self._build_command(action, params)
        envelope = {
            "ok": True,
            "command": f"{action}",
            "session_id": "mock-session",
            "data": {},
            "error": None,
            "meta": {"duration_ms": duration_ms},
        }
        cli = CLICommand(
            command=command,
            exit_code=0,
            stdout=json.dumps(envelope),
            stderr="",
            duration_ms=duration_ms,
            parsed_response=envelope,
        )
        
        # Create mock artifacts
        artifacts = []
        if step.get("evidence", {}).get("screenshot_after"):
            artifacts.append(Artifact(
                type="screenshot",
                path=f"screenshots/{step_id}-after.png",
                metadata={"step_id": step_id, "simulated": True},
            ))
        
        return StepEvidence(
            step_id=step_id,
            action=action,
            status=StepStatus.SUCCESS,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            cli_command=cli,
            artifacts=artifacts,
        )
    
    def _create_failure(self, step_id: str, action: str, error_type: str, started_at):
        """Create a failure evidence."""
        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        
        error_map = {
            "timeout": (FailureClassification.ENVIRONMENT_FAILURE, "Command timed out after 60s"),
            "element_not_found": (FailureClassification.OBSERVATION_INSUFFICIENT, "Element not found: locator failed"),
            "session_error": (FailureClassification.ENVIRONMENT_FAILURE, "Session disconnected"),
            "permission": (FailureClassification.PRECONDITION_MISSING, "Permission denied"),
        }
        
        classification, message = error_map.get(error_type, (FailureClassification.ENVIRONMENT_FAILURE, "Unknown error"))
        
        # Map error types to fsq-mac v0.3.0 error codes
        fsq_error_map = {
            "timeout": ("TIMEOUT", True),
            "element_not_found": ("ELEMENT_NOT_FOUND", True),
            "session_error": ("SESSION_NOT_FOUND", False),
            "permission": ("PERMISSION_DENIED", False),
        }
        fsq_code, fsq_retryable = fsq_error_map.get(error_type, ("INTERNAL_ERROR", False))

        envelope = {
            "ok": False,
            "command": action,
            "session_id": None,
            "data": None,
            "error": {"code": fsq_code, "message": message, "retryable": fsq_retryable, "details": {}, "suggested_next_action": None, "doctor_hint": None},
            "meta": {},
        }

        cli = CLICommand(
            command=["mac", action],
            exit_code=1,
            stdout=json.dumps(envelope),
            stderr=message,
            duration_ms=duration_ms,
            parsed_response=envelope,
        )
        
        error = StepError(
            type=error_type,
            message=message,
            classification=classification,
            fsq_error_code=fsq_code,
            fsq_retryable=fsq_retryable,
        )
        
        return StepEvidence(
            step_id=step_id,
            action=action,
            status=StepStatus.FAILURE,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            cli_command=cli,
            error=error,
        )
    
    def _build_command(self, action: str, params: Dict) -> List[str]:
        """Build simulated CLI command."""
        if action == "launch":
            return ["mac", "app", "launch", params.get("app", "app")]
        if action == "launch_app":
            return ["mac", "app", "launch", params.get("bundle_id", "app")]
        elif action == "shortcut":
            keys = params.get("keys", [])
            return ["mac", "input", "hotkey", *keys]
        elif action == "hotkey":
            keys = params.get("keys", [])
            return ["mac", "input", "hotkey", *keys]
        elif action == "type":
            return ["mac", "input", "text", params.get("text", "")]
        elif action in ("click", "element_click"):
            argv = ["mac", "element", "click"]
            if params.get("role"):
                argv += ["--role", params["role"]]
            if params.get("name"):
                argv += ["--name", params["name"]]
            return argv
        elif action == "assert_visible":
            argv = ["mac", "assert", "visible"]
            if params.get("role"):
                argv += ["--role", params["role"]]
            if params.get("name"):
                argv += ["--name", params["name"]]
            return argv
        elif action == "assert":
            locator = params.get("locator", params.get("condition", "element"))
            return ["mac", "assert", "visible", locator]
        return ["mac", action]
    
    def _log_step(self, run_dir: Path, step: StepEvidence):
        """Log step execution."""
        log_path = run_dir / "logs" / "execution.jsonl"
        entry = {
            "timestamp": utc_now().isoformat(),
            "step_id": step.step_id,
            "action": step.action,
            "status": step.status.value,
            "duration_ms": step.duration_ms,
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def _save_evidence(self, run_dir: Path, evidence: RunEvidence):
        """Save evidence to disk."""
        evidence_path = run_dir / "evidence.json"
        with open(evidence_path, "w") as f:
            json.dump(evidence.to_dict(), f, indent=2)
