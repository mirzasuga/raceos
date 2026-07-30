"""
OpenCode Session Lifecycle Management.

Manages the lifecycle of an OpenCode subprocess session:
    spawn → configure → execute → collect results → terminate

A session is one-shot: one task per session, then terminated.
This prevents state leakage between tasks.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SessionStatus(Enum):
    """Session lifecycle status."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    TERMINATED = "terminated"


# --- Environment Filtering (Security: P1-2) ---

# Only these env vars are passed to OpenCode subprocess.
# Everything else (AWS keys, GITHUB_TOKEN, etc.) is stripped.
_ALLOWED_ENV_VARS = {
    # Required for LLM access
    "OPENROUTER_API_KEY",
    # Required for process execution
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "LANG",
    "LC_ALL",
    "TERM",
    # Required for Node.js (npx/npm)
    "NODE_PATH",
    "NPM_CONFIG_PREFIX",
    # Required for Python (if needed by tools)
    "PYTHONPATH",
    "VIRTUAL_ENV",
}


def _build_filtered_env() -> dict[str, str]:
    """
    Build a filtered environment dict for subprocess execution.

    Security: Only passes explicitly allowed env vars to child processes.
    This prevents accidental exposure of GITHUB_TOKEN, AWS credentials,
    database passwords, or other secrets to the AI coding agent.

    Returns:
        Dict with only allowed environment variables.
    """
    import os
    filtered = {}
    for key in _ALLOWED_ENV_VARS:
        value = os.environ.get(key)
        if value is not None:
            filtered[key] = value
    return filtered


@dataclass
class SessionConfig:
    """Configuration for an OpenCode session."""

    # Binary
    binary: str = "opencode"
    config_path: str = "config/opencode.json"

    # Model (overridden per-task by 9Router)
    model: str = "anthropic/claude-sonnet-4.6"
    max_tokens: int = 8192
    temperature: float = 0.1

    # Execution
    working_dir: str = ".."
    timeout_seconds: int = 300
    non_interactive: bool = True
    output_format: str = "json"

    # Tools to enable for this session
    enable_file: bool = True
    enable_terminal: bool = True
    enable_git: bool = True
    enable_patch: bool = True


@dataclass
class SessionResult:
    """Raw result from an OpenCode session."""

    status: SessionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_seconds: float = 0.0
    prompt_file: str = ""


@dataclass
class Session:
    """
    Manages a single OpenCode execution session.

    Lifecycle:
        1. create() — prepare prompt file and CLI args
        2. run() — spawn subprocess, wait for completion
        3. result — access SessionResult
        4. cleanup() — remove temp files

    Usage:
        session = Session(config)
        session.create(prompt="Fix the typo in ecu_parser.h")
        result = session.run()
        session.cleanup()
    """

    config: SessionConfig
    status: SessionStatus = SessionStatus.IDLE
    _process: subprocess.Popen | None = None
    _prompt_file: Path | None = None
    _result: SessionResult | None = None
    _start_time: float = 0.0

    def create(self, prompt: str, system_prompt: str = "") -> None:
        """
        Prepare session for execution.

        Writes the prompt to a temp file (avoids shell injection).
        Composes system prompt + task prompt into single file.
        """
        if self.status != SessionStatus.IDLE:
            raise RuntimeError(f"Session already in state: {self.status}")

        # Write combined prompt to temp file
        full_prompt = ""
        if system_prompt:
            full_prompt += f"{system_prompt}\n\n---\n\n"
        full_prompt += prompt

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix="factory-prompt-", delete=False
        )
        tmp.write(full_prompt)
        tmp.close()
        self._prompt_file = Path(tmp.name)
        self.status = SessionStatus.STARTING

    def build_command(self) -> list[str]:
        """
        Build the CLI command for spawning OpenCode.

        Returns:
            List of command parts ready for subprocess.run().
        """
        cmd = [self.config.binary]

        # Model selection
        cmd.extend(["--model", self.config.model])
        cmd.extend(["--max-tokens", str(self.config.max_tokens)])
        cmd.extend(["--temperature", str(self.config.temperature)])

        # Session mode
        if self.config.non_interactive:
            cmd.append("--non-interactive")

        # Output format
        cmd.extend(["--output-format", self.config.output_format])

        # Config file
        cmd.extend(["--config", self.config.config_path])

        # Prompt file
        if self._prompt_file:
            cmd.extend(["--prompt-file", str(self._prompt_file)])

        # Tool flags
        if not self.config.enable_file:
            cmd.append("--no-file")
        if not self.config.enable_terminal:
            cmd.append("--no-terminal")
        if not self.config.enable_git:
            cmd.append("--no-git")
        if not self.config.enable_patch:
            cmd.append("--no-patch")

        return cmd

    def run(self) -> SessionResult:
        """
        Execute the OpenCode session.

        Spawns subprocess, waits for completion (with timeout),
        and captures all output.

        Returns:
            SessionResult with stdout, stderr, exit code, duration.
        """
        if self.status != SessionStatus.STARTING:
            raise RuntimeError(f"Session not ready. Current state: {self.status}")

        self.status = SessionStatus.RUNNING
        self._start_time = time.time()
        cmd = self.build_command()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                cwd=self.config.working_dir,
                env=_build_filtered_env(),  # Security: only pass needed env vars
            )

            duration = time.time() - self._start_time
            self.status = SessionStatus.COMPLETED

            self._result = SessionResult(
                status=SessionStatus.COMPLETED,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_seconds=duration,
                prompt_file=str(self._prompt_file) if self._prompt_file else "",
            )

        except subprocess.TimeoutExpired as e:
            duration = time.time() - self._start_time
            self.status = SessionStatus.TIMEOUT

            self._result = SessionResult(
                status=SessionStatus.TIMEOUT,
                stdout=e.stdout or "" if hasattr(e, "stdout") else "",
                stderr=f"Session timed out after {self.config.timeout_seconds}s",
                exit_code=-1,
                duration_seconds=duration,
            )

        except FileNotFoundError:
            self.status = SessionStatus.FAILED
            self._result = SessionResult(
                status=SessionStatus.FAILED,
                stderr=(
                    f"OpenCode binary not found: '{self.config.binary}'. "
                    f"Install: npm install -g opencode"
                ),
                exit_code=-1,
            )

        except Exception as e:
            self.status = SessionStatus.FAILED
            self._result = SessionResult(
                status=SessionStatus.FAILED,
                stderr=str(e),
                exit_code=-1,
                duration_seconds=time.time() - self._start_time,
            )

        return self._result

    @property
    def result(self) -> SessionResult | None:
        """Access the session result after run()."""
        return self._result

    def cleanup(self) -> None:
        """Remove temporary files created for this session."""
        if self._prompt_file and self._prompt_file.exists():
            self._prompt_file.unlink()
            self._prompt_file = None

    def terminate(self) -> None:
        """Force-kill a running session."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self.status = SessionStatus.TERMINATED
        self.cleanup()
