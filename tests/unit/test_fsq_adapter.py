"""Unit tests for the fsq-mac adapter."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from src.actions.action_space import ACTION_SPACE, ActionDefinition
from src.actions.fsq_adapter import FsqAdapter


class TestFsqAdapter:
    """Tests for fsq-mac action execution."""

    @patch("src.actions.fsq_adapter.subprocess.run")
    def test_execute_successfully_renders_and_runs_command(self, mock_run):
        """Tap action should render placeholders into argv."""
        mock_run.return_value = MagicMock(returncode=0, stdout="clicked\n", stderr="")
        adapter = FsqAdapter(cli_path="/tmp/fake-mac")

        result = adapter.execute(ACTION_SPACE[1], {"target": "Sign in"})

        assert result.success is True
        assert result.output == "clicked"
        assert result.error == ""
        assert mock_run.call_args.args[0] == ["/tmp/fake-mac", "element", "click", "Sign in"]

    @patch("src.actions.fsq_adapter.subprocess.run")
    def test_execute_failure_returns_stderr(self, mock_run):
        """Non-zero exit should propagate stderr into ExecutionResult."""
        mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="Element not found\n")
        adapter = FsqAdapter()

        result = adapter.execute(ACTION_SPACE[1], {"target": "Missing button"})

        assert result.success is False
        assert result.error == "Element not found"

    def test_execute_returns_validation_error_for_missing_param(self):
        """Missing template parameters should not raise out of execute()."""
        adapter = FsqAdapter()

        result = adapter.execute(ACTION_SPACE[2], {"target": "Search"})

        assert result.success is False
        assert "Missing required parameters" in result.error

    @patch("src.actions.fsq_adapter.subprocess.run")
    def test_execute_returns_timeout_error(self, mock_run):
        """Timeouts should be converted to structured failure results."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["mac"], timeout=0.05)
        adapter = FsqAdapter(timeout_ms=50)

        result = adapter.execute(ACTION_SPACE[0], {"target": "com.apple.Safari"})

        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_execute_rejects_unsupported_action(self):
        """Only the architecture-defined action set is allowed."""
        adapter = FsqAdapter()
        action = ActionDefinition(
            name="scroll",
            description="Unsupported",
            params={"target": "direction"},
            fsq_cmd="mac input scroll {target}",
        )

        result = adapter.execute(action, {"target": "down"})

        assert result.success is False
        assert "Unsupported action" in result.error
