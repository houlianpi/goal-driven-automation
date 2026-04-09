"""
Unified Executor - Executes compiled Plan IR steps and collects evidence.
"""
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


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
        self.start_time = datetime.utcnow().isoformat()
        self.end_time: Optional[str] = None
        self.success = True
        self.step_results: List[StepResult] = []
        self.failure_reason: Optional[str] = None
    
    def add_step_result(self, result: StepResult):
        self.step_results.append(result)
        if not result.success:
            self.success = False
    
    def finalize(self, failure_reason: Optional[str] = None):
        self.end_time = datetime.utcnow().isoformat()
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
            runs_dir = Path(__file__).parent.parent.parent / "runs"
        self.runs_dir = runs_dir
        self.timeout_ms = timeout_ms
        self.mac_cli = os.environ.get("FSQ_MAC_CLI", "mac")
    
    def execute_command(self, command: str, timeout_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a single CLI command.
        
        Returns:
            Dict with stdout, stderr, return_code, duration_ms
        """
        timeout = (timeout_ms or self.timeout_ms) / 1000.0
        start = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
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
        
        if not command:
            return StepResult(
                step_id=step_id,
                success=False,
                command="",
                error="Step missing 'command' field - not compiled?",
            )
        
        # Execute with retry
        retry_policy = step.get("retry_policy", {})
        max_attempts = retry_policy.get("max", 1)
        backoff = retry_policy.get("backoff", "none")
        delay_ms = retry_policy.get("delay_ms", 1000)
        
        last_result = None
        for attempt in range(max_attempts):
            result = self.execute_command(command)
            last_result = result
            
            if result["return_code"] == 0:
                return StepResult(
                    step_id=step_id,
                    success=True,
                    command=command,
                    stdout=result["stdout"],
                    stderr=result["stderr"],
                    return_code=result["return_code"],
                    duration_ms=result["duration_ms"],
                    evidence={
                        "command_output": result["stdout"],
                        "attempt": attempt + 1,
                    },
                )
            
            # Backoff before retry
            if attempt < max_attempts - 1:
                if backoff == "linear":
                    time.sleep(delay_ms * (attempt + 1) / 1000.0)
                elif backoff == "exponential":
                    time.sleep(delay_ms * (2 ** attempt) / 1000.0)
                else:
                    time.sleep(delay_ms / 1000.0)
        
        return StepResult(
            step_id=step_id,
            success=False,
            command=command,
            stdout=last_result.get("stdout", ""),
            stderr=last_result.get("stderr", ""),
            return_code=last_result.get("return_code", -1),
            duration_ms=last_result.get("duration_ms", 0),
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
    
    def _save_evidence(self, result: PlanResult):
        """Save execution evidence to runs directory."""
        run_dir = self.runs_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save result JSON
        with open(run_dir / "result.json", "w") as f:
            json.dump(result.to_dict(), f, indent=2)


def execute_command(command: str) -> Dict[str, Any]:
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
