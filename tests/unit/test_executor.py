"""Unit tests for Executor."""
import pytest
from unittest.mock import patch, MagicMock
from src.evidence.types import RunEvidence, RunStatus
from src.executor.executor import Executor, StepResult, PlanResult, execute_command


class TestExecutor:
    """Test Executor class."""
    
    def test_execute_simple_command(self):
        """Test executing a simple command."""
        executor = Executor()
        result = executor.execute_command(["echo", "hello"])
        assert result["return_code"] == 0
        assert "hello" in result["stdout"]
        assert result["duration_ms"] >= 0
    
    def test_execute_failing_command(self):
        """Test executing a failing command."""
        executor = Executor()
        result = executor.execute_command(["false"])
        assert result["return_code"] != 0
    
    def test_execute_step_success(self):
        """Test executing a compiled step successfully."""
        executor = Executor()
        step = {
            "step_id": "s1",
            "command": "echo success",
            "argv": ["echo", "success"],
            "retry_policy": {"max": 1},
        }
        result = executor.execute_step(step)
        assert result.success is True
        assert "success" in result.stdout
    
    def test_execute_step_with_retry(self):
        """Test step execution with retry on failure."""
        executor = Executor()
        step = {
            "step_id": "s2",
            "command": "false",
            "argv": ["false"],
            "retry_policy": {"max": 2, "backoff": "none", "delay_ms": 10},
        }
        result = executor.execute_step(step)
        assert result.success is False
        assert "2 attempts" in result.error
    
    def test_execute_step_missing_command(self):
        """Test step without command field."""
        executor = Executor()
        step = {"step_id": "s3"}  # No command
        result = executor.execute_step(step)
        assert result.success is False
        assert "not compiled" in result.error
    
    def test_execute_plan(self):
        """Test executing entire plan."""
        executor = Executor()
        plan = {
            "plan_id": "test_plan",
            "steps": [
                {"step_id": "s1", "command": "echo step1", "argv": ["echo", "step1"]},
                {"step_id": "s2", "command": "echo step2", "argv": ["echo", "step2"]},
            ],
        }
        result = executor.execute_plan(plan)
        assert result.success is True
        assert len(result.step_results) == 2
    
    def test_execute_plan_abort_on_failure(self):
        """Test plan aborts on step failure with on_fail=abort."""
        executor = Executor()
        plan = {
            "plan_id": "test_plan",
            "steps": [
                {"step_id": "s1", "command": "echo ok", "argv": ["echo", "ok"]},
                {"step_id": "s2", "command": "false", "argv": ["false"], "on_fail": "abort"},
                {"step_id": "s3", "command": "echo never", "argv": ["echo", "never"]},
            ],
        }
        result = executor.execute_plan(plan)
        assert result.success is False
        assert len(result.step_results) == 2  # s3 not executed
        assert "aborting" in result.failure_reason.lower()
    
    def test_execute_plan_skip_on_failure(self):
        """Test plan continues with on_fail=skip."""
        executor = Executor()
        plan = {
            "plan_id": "test_plan",
            "steps": [
                {"step_id": "s1", "command": "echo ok", "argv": ["echo", "ok"]},
                {"step_id": "s2", "command": "false", "argv": ["false"], "on_fail": "skip"},
                {"step_id": "s3", "command": "echo continued", "argv": ["echo", "continued"]},
            ],
        }
        result = executor.execute_plan(plan)
        assert len(result.step_results) == 3  # All executed
        assert result.step_results[2].success is True

    def test_execute_returns_run_evidence(self):
        """Test unified execute() returns RunEvidence."""
        executor = Executor()
        plan = {
            "plan_id": "test_plan",
            "steps": [
                {"step_id": "s1", "action": "launch_app", "command": "echo ok", "argv": ["echo", "ok"]},
                {"step_id": "s2", "action": "hotkey", "command": "echo done", "argv": ["echo", "done"]},
            ],
        }

        result = executor.execute(plan, run_id="run-fixed")

        assert isinstance(result, RunEvidence)
        assert result.run_id == "run-fixed"
        assert result.plan_id == "test_plan"
        assert result.status == RunStatus.SUCCESS
        assert len(result.steps) == 2


class TestStepResult:
    """Test StepResult class."""
    
    def test_to_dict(self):
        """Test StepResult serialization."""
        result = StepResult(
            step_id="s1",
            success=True,
            command="echo test",
            stdout="test\n",
            duration_ms=10,
        )
        d = result.to_dict()
        assert d["step_id"] == "s1"
        assert d["success"] is True
        assert d["command"] == "echo test"


class TestPlanResult:
    """Test PlanResult class."""
    
    def test_add_step_result(self):
        """Test adding step results."""
        plan_result = PlanResult("p1", "r1")
        step_result = StepResult("s1", True, "echo ok")
        plan_result.add_step_result(step_result)
        assert len(plan_result.step_results) == 1
        assert plan_result.success is True
    
    def test_failure_propagation(self):
        """Test that step failure marks plan as failed."""
        plan_result = PlanResult("p1", "r1")
        plan_result.add_step_result(StepResult("s1", True, "echo ok"))
        plan_result.add_step_result(StepResult("s2", False, "false"))
        assert plan_result.success is False


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_execute_command_function(self):
        """Test execute_command helper."""
        result = execute_command(["echo", "hello"])
        assert result["return_code"] == 0

    @patch("src.executor.executor.subprocess.run")
    def test_execute_command_uses_argv_without_shell(self, mock_run):
        """Test executor uses structured argv execution."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        executor = Executor()
        executor.execute_command(["echo", "ok"])

        _, kwargs = mock_run.call_args
        assert kwargs["shell"] is False
