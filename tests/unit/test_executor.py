"""Unit tests for Executor."""
import os
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

    @patch.dict(os.environ, {"FSQ_MAC_CLI": "/tmp/fake-mac"}, clear=False)
    @patch("src.executor.executor.subprocess.run")
    def test_execute_step_rewrites_mac_argv_to_configured_cli(self, mock_run):
        """Test executor resolves logical mac argv to FSQ_MAC_CLI."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        executor = Executor()
        step = {
            "step_id": "s-cli",
            "command": "mac app launch com.apple.Safari",
            "argv": ["mac", "app", "launch", "com.apple.Safari"],
            "retry_policy": {"max": 1},
        }

        result = executor.execute_step(step)

        assert result.success is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert calls[0] == ["/tmp/fake-mac", "session", "start"]
        assert calls[1] == ["/tmp/fake-mac", "app", "launch", "com.apple.Safari"]

    @patch.dict(os.environ, {"FSQ_MAC_CLI": "/tmp/fake-mac"}, clear=False)
    @patch("src.executor.executor.subprocess.run")
    def test_execute_plan_bootstraps_session_once_for_multiple_mac_steps(self, mock_run):
        """Test session bootstrap runs once per plan for session-bound fsq-mac commands."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        executor = Executor()
        plan = {
            "plan_id": "plan-session",
            "steps": [
                {"step_id": "s1", "command": "mac app launch com.apple.Safari", "argv": ["mac", "app", "launch", "com.apple.Safari"]},
                {"step_id": "s2", "command": "mac input hotkey command+t", "argv": ["mac", "input", "hotkey", "command+t"]},
            ],
        }

        result = executor.execute_plan(plan)

        assert result.success is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert calls == [
            ["/tmp/fake-mac", "session", "start"],
            ["/tmp/fake-mac", "app", "launch", "com.apple.Safari"],
            ["/tmp/fake-mac", "input", "hotkey", "command+t"],
        ]


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


class TestV030JsonEnvelope:
    """Tests for fsq-mac v0.3.0 JSON envelope parsing."""

    @patch("src.executor.executor.subprocess.run")
    def test_parse_fsq_response_valid_envelope(self, mock_run):
        """Test that valid JSON envelope is parsed."""
        envelope = '{"ok": true, "command": "app.launch", "session_id": "s1", "data": {}, "error": null, "meta": {}}'
        mock_run.return_value = MagicMock(returncode=0, stdout=envelope, stderr="")

        executor = Executor()
        result = executor._parse_fsq_response(envelope)

        assert result is not None
        assert result["ok"] is True

    def test_parse_fsq_response_non_json(self):
        executor = Executor()
        assert executor._parse_fsq_response("not json") is None

    def test_parse_fsq_response_empty(self):
        executor = Executor()
        assert executor._parse_fsq_response("") is None

    @patch("src.executor.executor.subprocess.run")
    def test_execute_step_detects_ok_false_as_failure(self, mock_run):
        """Test that ok=false in JSON envelope marks step as failed even with exit_code=0."""
        envelope = '{"ok": false, "command": "element.click", "session_id": "s1", "data": null, "error": {"code": "ELEMENT_NOT_FOUND", "message": "No match", "retryable": true, "details": {}, "suggested_next_action": null, "doctor_hint": null}, "meta": {}}'
        mock_run.return_value = MagicMock(returncode=1, stdout=envelope, stderr="")

        executor = Executor()
        executor._session_bootstrapped = True
        step = {
            "step_id": "s1",
            "command": "mac element click --name Foo",
            "argv": ["echo", "test"],
            "retry_policy": {"max_attempts": 1},
        }

        result = executor.execute_step(step)
        assert result.success is False

    @patch("src.executor.executor.subprocess.run")
    def test_execute_returns_evidence_with_fsq_error_fields(self, mock_run):
        """Test that RunEvidence StepError includes fsq_error_code and fsq_retryable."""
        envelope = '{"ok": false, "command": "element.click", "session_id": null, "data": null, "error": {"code": "ELEMENT_NOT_FOUND", "message": "No match", "retryable": true, "details": {}, "suggested_next_action": "element inspect", "doctor_hint": null}, "meta": {}}'
        mock_run.return_value = MagicMock(returncode=1, stdout=envelope, stderr="")

        executor = Executor()
        executor._session_bootstrapped = True

        plan = {
            "plan_id": "plan-test",
            "steps": [
                {
                    "step_id": "s1",
                    "action": "element_click",
                    "command": "mac element click --name Foo",
                    "argv": ["echo", "test"],
                    "on_fail": "skip",
                },
            ],
        }

        evidence = executor.execute(plan)
        step_ev = evidence.steps[0]

        assert step_ev.error is not None
        assert step_ev.error.fsq_error_code == "ELEMENT_NOT_FOUND"
        assert step_ev.error.fsq_retryable is True
        assert step_ev.error.fsq_suggested_action == "element inspect"

    def test_classify_failure_uses_fsq_error_code(self):
        """Test _classify_failure prioritizes fsq-mac error.code."""
        executor = Executor()
        step_result = StepResult(
            step_id="s1", success=False, command="test",
            stderr="", return_code=1,
            evidence={
                "fsq_response": {
                    "ok": False,
                    "error": {"code": "ASSERTION_FAILED", "message": "Failed", "retryable": False},
                }
            },
        )
        from src.evidence.types import FailureClassification
        assert executor._classify_failure(step_result) == FailureClassification.ASSERTION_FAILED

    def test_classify_failure_falls_back_to_regex(self):
        """Test _classify_failure falls back to regex when no JSON envelope."""
        executor = Executor()
        step_result = StepResult(
            step_id="s1", success=False, command="test",
            stderr="timed out after 60s", return_code=-1,
            evidence={},
        )
        from src.evidence.types import FailureClassification
        assert executor._classify_failure(step_result) == FailureClassification.ENVIRONMENT_FAILURE
