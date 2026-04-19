"""Adapter for executing fsq-mac action definitions."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import shlex
import subprocess
import time
from typing import Any, Mapping

from src.actions.action_space import ActionDefinition


_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass(frozen=True)
class ExecutionResult:
    """Result of a single fsq-mac command execution."""

    success: bool
    output: str
    error: str
    duration_ms: int


class FsqAdapter:
    """Executes semantic actions through the fsq-mac CLI."""

    SUPPORTED_ACTIONS = {"launch", "tap", "input", "hotkey", "assert", "wait"}

    def __init__(self, cli_path: str | None = None, timeout_ms: int = 120000):
        self.cli_path = cli_path or os.environ.get("FSQ_MAC_CLI", "mac")
        self.timeout_ms = timeout_ms

    def execute(self, action: ActionDefinition, params: dict[str, Any]) -> ExecutionResult:
        """Render and execute one fsq-mac command."""
        started_at = time.perf_counter()

        try:
            argv = self._resolve_command(self._build_argv(action, params))
            completed = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_ms / 1000.0,
                check=False,
            )
            duration_ms = self._elapsed_ms(started_at)
            error = completed.stderr.strip()
            if completed.returncode != 0 and not error:
                error = f"Command exited with code {completed.returncode}."
            return ExecutionResult(
                success=completed.returncode == 0,
                output=completed.stdout.strip(),
                error=error,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = self._elapsed_ms(started_at)
            stdout = exc.stdout.strip() if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else ""
            message = stderr or f"Command timed out after {self.timeout_ms}ms."
            return ExecutionResult(False, stdout, message, duration_ms)
        except (OSError, ValueError) as exc:
            return ExecutionResult(False, "", str(exc), self._elapsed_ms(started_at))

    def _build_argv(self, action: ActionDefinition, params: Mapping[str, Any]) -> list[str]:
        """Render the action template into structured argv."""
        if action.name not in self.SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action '{action.name}'.")

        missing = [key for key in action.params if key not in params]
        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(f"Missing required parameters for '{action.name}': {joined}.")

        placeholders = sorted(set(_PLACEHOLDER_PATTERN.findall(action.fsq_cmd)))
        template = action.fsq_cmd
        sentinels: dict[str, str] = {}

        for index, name in enumerate(placeholders):
            if name not in params:
                raise ValueError(f"Template placeholder '{name}' was not provided.")
            sentinel = f"__GDA_PARAM_{index}__"
            sentinels[sentinel] = str(params[name])
            template = template.replace(f"{{{name}}}", sentinel)

        if _PLACEHOLDER_PATTERN.search(template):
            raise ValueError(f"Unresolved placeholders remain in template: {action.fsq_cmd}")

        argv = shlex.split(template)
        return [self._restore_token(token, sentinels) for token in argv]

    def _resolve_command(self, argv: list[str]) -> list[str]:
        """Resolve the logical mac placeholder to the configured CLI path."""
        if argv and argv[0] == "mac":
            return [self.cli_path, *argv[1:]]
        return argv

    @staticmethod
    def _restore_token(token: str, sentinels: Mapping[str, str]) -> str:
        """Replace command sentinels with original parameter values."""
        restored = token
        for sentinel, value in sentinels.items():
            restored = restored.replace(sentinel, value)
        return restored

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        """Return elapsed wall-clock time in milliseconds."""
        return int((time.perf_counter() - started_at) * 1000)
