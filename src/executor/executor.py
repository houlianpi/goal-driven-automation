"""
Unified Executor - Executes compiled Plan IR steps and collects evidence.
"""
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from src.evidence.types import CLICommand, RunEvidence, RunStatus, StepEvidence, StepError, StepStatus, FailureClassification
from src.time_utils import utc_now


class ExecutionError(Exception):
    """Raised when execution fails."""
    pass


class StepResult:
    """Result of executing a single step."""
    
    def __init__(
        self,
        step_id: str,
        success: bool,
        command: str,
        argv: Optional[List[str]] = None,
        stdout: str = "",
        stderr: str = "",
        return_code: int = 0,
        duration_ms: int = 0,
        evidence: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.step_id = step_id
        self.success = success
        self.command = command
        self.argv = argv or []
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code
        self.duration_ms = duration_ms
        self.evidence = evidence or {}
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "success": self.success,
            "command": self.command,
            "argv": self.argv,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "duration_ms": self.duration_ms,
            "evidence": self.evidence,
            "error": self.error,
        }


class PlanResult:
    """Result of executing an entire plan."""
    
    def __init__(self, plan_id: str, run_id: str):
        self.plan_id = plan_id
        self.run_id = run_id
        self.start_time = utc_now().isoformat()
        self.end_time: Optional[str] = None
        self.success = True
        self.step_results: List[StepResult] = []
        self.failure_reason: Optional[str] = None
    
    def add_step_result(self, result: StepResult):
        self.step_results.append(result)
        if not result.success:
            self.success = False
    
    def finalize(self, failure_reason: Optional[str] = None):
        self.end_time = utc_now().isoformat()
        self.failure_reason = failure_reason
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "step_results": [r.to_dict() for r in self.step_results],
        }


class Executor:
    """Executes compiled Plan IR steps."""
    
    def __init__(self, runs_dir: Optional[Path] = None, timeout_ms: int = 120000):
        """Initialize executor."""
        if runs_dir is None:
            runs_dir = Path(__file__).parent.parent.parent / "data" / "runs"
        self.runs_dir = runs_dir
        self.timeout_ms = timeout_ms
        self.mac_cli = os.environ.get("FSQ_MAC_CLI", "mac")
        self._session_bootstrapped = False

    def _resolve_command(self, command: List[str]) -> List[str]:
        """Resolve logical CLI placeholders to concrete executables."""
        if command and command[0] == "mac":
            return [self.mac_cli, *command[1:]]
        return command

    # fsq-mac v0.3.0 error code → GDA classification mapping
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

    def _parse_fsq_response(self, stdout: str) -> Optional[Dict[str, Any]]:
        """Try to parse stdout as a fsq-mac v0.3.0 JSON envelope."""
        if not stdout or not stdout.strip():
            return None
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict) and "ok" in parsed:
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _extract_success_evidence(self, parsed: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract structured success payload fields from a parsed fsq envelope."""
        if not parsed or not parsed.get("ok"):
            return {}

        data = parsed.get("data") or {}
        meta = parsed.get("meta") or {}
        extracted: Dict[str, Any] = {}

        if parsed.get("session_id") is not None:
            extracted["session_id"] = parsed["session_id"]
        if data.get("resolved_element") is not None:
            extracted["resolved_element"] = data["resolved_element"]
        if data.get("snapshot") is not None:
            extracted["snapshot"] = data["snapshot"]
        if data.get("actionability_used") is not None:
            extracted["actionability_used"] = data["actionability_used"]
        if meta.get("duration_ms") is not None:
            extracted["upstream_duration_ms"] = meta["duration_ms"]

        return extracted

    def _is_mac_command(self, command: List[str]) -> bool:
        """Return True when the argv targets fsq-mac."""
        if not command:
            return False
        return Path(command[0]).name == Path(self.mac_cli).name

    def _requires_session(self, command: List[str]) -> bool:
        """Return True when the fsq-mac command expects an active session."""
        if not self._is_mac_command(command) or len(command) < 2:
            return False
        return command[1] not in {"session", "doctor"}

    def _ensure_session_started(self) -> Optional[Dict[str, Any]]:
        """Start a session once per plan before session-bound commands."""
        if self._session_bootstrapped:
            return None

        result = self.execute_command([self.mac_cli, "session", "start"], timeout_ms=30000)
        if result["return_code"] == 0:
            self._session_bootstrapped = True
        return result
    
    def execute_command(self, command: List[str], timeout_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a single CLI command.
        
        Returns:
            Dict with stdout, stderr, return_code, duration_ms
        """
        command = self._resolve_command(command)
        timeout = (timeout_ms or self.timeout_ms) / 1000.0
        start = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((time.time() - start) * 1000)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "return_code": -1,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": -2,
                "duration_ms": duration_ms,
            }
    
    def execute_step(self, step: Dict[str, Any]) -> StepResult:
        """
        Execute a single compiled step.
        
        Args:
            step: Compiled step with 'command' field
            
        Returns:
            StepResult with execution details
        """
        step_id = step.get("step_id", "unknown")
        command = step.get("command")
        argv = self._resolve_command(step.get("argv") or [])

        if not command or not argv:
            return StepResult(
                step_id=step_id,
                success=False,
                command=command or "",
                argv=argv or [],
                error="Step missing 'command' or 'argv' field - not compiled?",
            )

        if self._requires_session(argv):
            session_result = self._ensure_session_started()
            if session_result and session_result["return_code"] != 0:
                return StepResult(
                    step_id=step_id,
                    success=False,
                    command=command,
                    argv=argv,
                    stdout=session_result.get("stdout", ""),
                    stderr=session_result.get("stderr", ""),
                    return_code=session_result.get("return_code", -1),
                    duration_ms=session_result.get("duration_ms", 0),
                    error="Failed to bootstrap fsq-mac session",
                )
        
        # Execute with retry
        retry_policy = step.get("retry_policy", {})
        max_attempts = retry_policy.get("max_attempts", retry_policy.get("max", 1))
        backoff = retry_policy.get("backoff", "none")
        delay_ms = retry_policy.get("delay_ms", 1000)
        
        last_result = None
        last_parsed = None
        for attempt in range(max_attempts):
            result = self.execute_command(argv)
            last_result = result

            # Try to parse fsq-mac JSON envelope
            parsed = self._parse_fsq_response(result["stdout"])
            last_parsed = parsed

            if len(argv) >= 3 and argv[1] == "session":
                if argv[2] == "start" and result["return_code"] == 0:
                    self._session_bootstrapped = True
                elif argv[2] == "end" and result["return_code"] == 0:
                    self._session_bootstrapped = False

            # Determine success: prefer JSON ok field, fall back to return_code
            success = parsed["ok"] if parsed and "ok" in parsed else result["return_code"] == 0

            if success:
                evidence_data = {
                    "command_output": result["stdout"],
                    "attempt": attempt + 1,
                }
                if parsed:
                    evidence_data["fsq_response"] = parsed
                    evidence_data.update(self._extract_success_evidence(parsed))
                return StepResult(
                    step_id=step_id,
                    success=True,
                    command=command,
                    argv=argv,
                    stdout=result["stdout"],
                    stderr=result["stderr"],
                    return_code=result["return_code"],
                    duration_ms=result["duration_ms"],
                    evidence=evidence_data,
                )
            
            # Backoff before retry
            if attempt < max_attempts - 1:
                if backoff == "linear":
                    time.sleep(delay_ms * (attempt + 1) / 1000.0)
                elif backoff == "exponential":
                    time.sleep(delay_ms * (2 ** attempt) / 1000.0)
                else:
                    time.sleep(delay_ms / 1000.0)
        
        evidence_data = {}
        if last_parsed:
            evidence_data["fsq_response"] = last_parsed

        return StepResult(
            step_id=step_id,
            success=False,
            command=command,
            argv=argv,
            stdout=last_result.get("stdout", ""),
            stderr=last_result.get("stderr", ""),
            return_code=last_result.get("return_code", -1),
            duration_ms=last_result.get("duration_ms", 0),
            evidence=evidence_data,
            error=f"Failed after {max_attempts} attempts",
        )
    
    def execute_plan(self, plan: Dict[str, Any]) -> PlanResult:
        """
        Execute an entire compiled plan.
        
        Args:
            plan: Compiled plan with steps
            
        Returns:
            PlanResult with all step results
        """
        plan_id = plan.get("plan_id", "unknown")
        run_id = str(uuid.uuid4())[:8]
        self._session_bootstrapped = False

        result = PlanResult(plan_id, run_id)
        
        for step in plan.get("steps", []):
            step_result = self.execute_step(step)
            result.add_step_result(step_result)
            
            # Check on_fail policy
            if not step_result.success:
                on_fail = step.get("on_fail", "abort")
                if on_fail == "abort":
                    result.finalize(f"Step {step_result.step_id} failed, aborting")
                    break
                elif on_fail == "skip":
                    continue
                elif on_fail == "human_review":
                    result.finalize(f"Step {step_result.step_id} requires human review")
                    break
        else:
            result.finalize()
        
        # Save evidence to runs directory
        self._save_evidence(result)
        
        return result

    def execute(self, plan: Dict[str, Any], run_id: Optional[str] = None) -> RunEvidence:
        """Execute a compiled plan and return unified run evidence."""
        plan_result = self.execute_plan(plan)
        evidence = RunEvidence(plan_id=plan.get("plan_id", "unknown"), run_id=run_id or plan_result.run_id)

        for step_result, step in zip(plan_result.step_results, plan.get("steps", [])):
            error = None
            fsq_response = step_result.evidence.get("fsq_response") if step_result.evidence else None

            if not step_result.success:
                fsq_error = fsq_response.get("error") if isinstance(fsq_response, dict) else None
                error = StepError(
                    type="ExecutionError",
                    message=step_result.error or step_result.stderr or "Step execution failed",
                    classification=self._classify_failure(step_result),
                    fsq_error_code=fsq_error.get("code") if isinstance(fsq_error, dict) else None,
                    fsq_retryable=fsq_error.get("retryable") if isinstance(fsq_error, dict) else None,
                    fsq_suggested_action=fsq_error.get("suggested_next_action") if isinstance(fsq_error, dict) else None,
                )

            step_evidence = StepEvidence(
                step_id=step_result.step_id,
                action=step.get("action", "unknown"),
                status=StepStatus.SUCCESS if step_result.success else StepStatus.FAILURE,
                duration_ms=step_result.duration_ms,
                cli_command=CLICommand(
                    command=step_result.argv,
                    exit_code=step_result.return_code,
                    stdout=step_result.stdout,
                    stderr=step_result.stderr,
                    duration_ms=step_result.duration_ms,
                    parsed_response=fsq_response,
                    session_id=step_result.evidence.get("session_id"),
                    resolved_element=step_result.evidence.get("resolved_element"),
                    snapshot=step_result.evidence.get("snapshot"),
                    actionability_used=step_result.evidence.get("actionability_used"),
                    upstream_duration_ms=step_result.evidence.get("upstream_duration_ms"),
                ),
                error=error,
                retry_count=max(step_result.evidence.get("attempt", 1) - 1, 0),
            )
            evidence.add_step(step_evidence)

        evidence.finalize()
        if not plan_result.success and evidence.status == RunStatus.SUCCESS:
            evidence.status = RunStatus.FAILURE
        return evidence

    def _classify_failure(self, step_result: StepResult) -> FailureClassification:
        """Map executor step failures to coarse evidence classifications."""
        # Priority 1: Use structured fsq-mac error.code if available
        fsq_response = step_result.evidence.get("fsq_response") if step_result.evidence else None
        if fsq_response and isinstance(fsq_response.get("error"), dict):
            error_code = fsq_response["error"].get("code", "")
            if error_code in self._FSQ_ERROR_CLASSIFICATION:
                return self._FSQ_ERROR_CLASSIFICATION[error_code]

        # Priority 2: Regex-based fallback
        text = f"{step_result.stderr} {step_result.error}".lower()
        if "timed out" in text or step_result.return_code == -1:
            return FailureClassification.ENVIRONMENT_FAILURE
        if "not found" in text or step_result.return_code == 127:
            return FailureClassification.CAPABILITY_UNAVAILABLE
        if "permission" in text or "denied" in text:
            return FailureClassification.PRECONDITION_MISSING
        return FailureClassification.ENVIRONMENT_FAILURE
    
    def _save_evidence(self, result: PlanResult):
        """Save execution evidence to runs directory."""
        run_dir = self.runs_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save result JSON
        with open(run_dir / "result.json", "w") as f:
            json.dump(result.to_dict(), f, indent=2)


def execute_command(command: List[str]) -> Dict[str, Any]:
    """Execute a single CLI command."""
    executor = Executor()
    return executor.execute_command(command)


def execute_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single compiled step."""
    executor = Executor()
    result = executor.execute_step(step)
    return result.to_dict()


def execute_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an entire compiled plan."""
    executor = Executor()
    result = executor.execute_plan(plan)
    return result.to_dict()
