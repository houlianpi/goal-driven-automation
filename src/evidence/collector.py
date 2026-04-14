"""
Evidence Collector - Captures evidence during step execution.
"""
import subprocess
import time
import json
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import (
    Artifact,
    CLICommand,
    StepEvidence,
    StepStatus,
    StepError,
    FailureClassification,
)
from src.time_utils import utc_now


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


class EvidenceCollector:
    """Collects evidence during plan execution."""
    
    def __init__(self, run_dir: Path, mac_cli: str = "mac"):
        self.run_dir = run_dir
        self.mac_cli = mac_cli
        self._setup_directories()
    
    def _setup_directories(self):
        (self.run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "ui_trees").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "logs").mkdir(parents=True, exist_ok=True)
    
    def capture_screenshot(self, step_id: str, suffix: str = "") -> Optional[Artifact]:
        filename = f"{step_id}{'-' + suffix if suffix else ''}.png"
        filepath = self.run_dir / "screenshots" / filename
        try:
            result = subprocess.run(
                [self.mac_cli, "capture", "screenshot", str(filepath)],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and filepath.exists():
                return Artifact(
                    type=f"screenshot_{suffix}" if suffix else "screenshot",
                    path=f"screenshots/{filename}",
                    metadata={"step_id": step_id},
                )
        except Exception as e:
            self._log_error(f"Screenshot capture failed: {e}")
        return None
    
    def capture_ui_tree(self, step_id: str, suffix: str = "") -> Optional[Artifact]:
        filename = f"{step_id}{'-' + suffix if suffix else ''}.json"
        filepath = self.run_dir / "ui_trees" / filename
        try:
            result = subprocess.run(
                [self.mac_cli, "capture", "ui-tree"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                filepath.write_text(result.stdout)
                return Artifact(
                    type=f"ui_tree_{suffix}" if suffix else "ui_tree",
                    path=f"ui_trees/{filename}",
                    metadata={"step_id": step_id},
                )
        except Exception as e:
            self._log_error(f"UI tree capture failed: {e}")
        return None
    
    def execute_and_collect(
        self, step_id: str, action: str, command: List[str],
        evidence_config: Optional[Dict[str, bool]] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
    ) -> StepEvidence:
        evidence_config = evidence_config or {}
        retry_policy = retry_policy or {"max_attempts": 1}
        
        started_at = utc_now()
        artifacts: List[Artifact] = []
        
        if evidence_config.get("screenshot_before"):
            if artifact := self.capture_screenshot(step_id, "before"):
                artifacts.append(artifact)
        if evidence_config.get("capture_ui_tree"):
            if artifact := self.capture_ui_tree(step_id, "before"):
                artifacts.append(artifact)
        
        max_attempts = retry_policy.get("max_attempts", retry_policy.get("max", 1))
        backoff = retry_policy.get("backoff", "none")
        delay_ms = retry_policy.get("delay_ms", 1000)
        last_result = None
        retry_count = 0
        display_command = self._render_command(command)

        for attempt in range(max_attempts):
            start_time = time.time()
            try:
                result = subprocess.run(command, shell=False, capture_output=True, text=True, timeout=60)
                duration_ms = int((time.time() - start_time) * 1000)
                last_result = CLICommand(
                    command=command, exit_code=result.returncode,
                    stdout=result.stdout, stderr=result.stderr, duration_ms=duration_ms,
                )
                if result.returncode == 0:
                    break
            except subprocess.TimeoutExpired:
                duration_ms = int((time.time() - start_time) * 1000)
                last_result = CLICommand(command=command, exit_code=-1, stderr="Timeout", duration_ms=duration_ms)
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                last_result = CLICommand(command=command, exit_code=-2, stderr=str(e), duration_ms=duration_ms)
            
            retry_count = attempt + 1
            if attempt < max_attempts - 1:
                delay = delay_ms * (attempt + 1 if backoff == "linear" else 2**attempt if backoff == "exponential" else 1)
                time.sleep(delay / 1000.0)
        
        if evidence_config.get("screenshot_after"):
            if artifact := self.capture_screenshot(step_id, "after"):
                artifacts.append(artifact)
        
        finished_at = utc_now()
        status = StepStatus.SUCCESS if last_result and last_result.exit_code == 0 else StepStatus.FAILURE
        error = self._classify_error(last_result) if status == StepStatus.FAILURE else None
        
        self._log_command(step_id, last_result)
        
        return StepEvidence(
            step_id=step_id, action=action, status=status,
            started_at=started_at, finished_at=finished_at,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
            cli_command=last_result, error=error, artifacts=artifacts, retry_count=retry_count,
        )

    def _render_command(self, command: List[str]) -> str:
        """Render argv for logs and debugging."""
        return " ".join(shlex.quote(part) for part in command)
    
    def _classify_error(self, cli_result: Optional[CLICommand]) -> Optional[StepError]:
        if not cli_result or cli_result.exit_code == 0:
            return None

        # Priority 1: structured fsq-mac JSON envelope
        parsed = self._parse_fsq_response(cli_result.stdout)
        if parsed and isinstance(parsed.get("error"), dict):
            fsq_error = parsed["error"]
            error_code = fsq_error.get("code", "")
            classification = _FSQ_ERROR_CLASSIFICATION.get(
                error_code, FailureClassification.ENVIRONMENT_FAILURE
            )
            return StepError(
                error_code, fsq_error.get("message", "")[:500], classification,
                fsq_error_code=error_code,
                fsq_retryable=fsq_error.get("retryable"),
                fsq_suggested_action=fsq_error.get("suggested_next_action"),
            )

        # Priority 2: regex-based fallback
        stderr = cli_result.stderr.lower()
        if "not found" in stderr or "no such" in stderr:
            return StepError("NotFound", cli_result.stderr[:500], FailureClassification.CAPABILITY_UNAVAILABLE)
        elif "permission" in stderr or "denied" in stderr:
            return StepError("PermissionDenied", cli_result.stderr[:500], FailureClassification.PRECONDITION_MISSING)
        elif "timeout" in stderr:
            return StepError("Timeout", cli_result.stderr[:500], FailureClassification.ENVIRONMENT_FAILURE)
        elif "element" in stderr or "locator" in stderr:
            return StepError("ElementNotFound", cli_result.stderr[:500], FailureClassification.OBSERVATION_INSUFFICIENT)
        elif "assert" in stderr:
            return StepError("AssertionFailed", cli_result.stderr[:500], FailureClassification.ASSERTION_FAILED)
        return StepError("UnknownError", cli_result.stderr[:500] or "Command failed", FailureClassification.ENVIRONMENT_FAILURE)

    def _parse_fsq_response(self, stdout: str) -> Optional[Dict]:
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
    
    def _log_command(self, step_id: str, cli_result: Optional[CLICommand]):
        log_path = self.run_dir / "logs" / "cli_commands.jsonl"
        entry = {"timestamp": utc_now().isoformat(), "step_id": step_id,
                 "command": cli_result.command if cli_result else None,
                 "exit_code": cli_result.exit_code if cli_result else None}
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def _log_error(self, message: str):
        log_path = self.run_dir / "logs" / "errors.log"
        with open(log_path, "a") as f:
            f.write(f"{utc_now().isoformat()} - {message}\n")
