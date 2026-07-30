"""
OpenCode Executor Client.

High-level client that the orchestrator calls to execute tasks.
Ties together: session management, contract validation, result parsing.

Usage:
    client = OpenCodeClient()
    result = client.execute(request)
"""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import (
    ExecutionRequest,
    ExecutionResult,
    FileChange,
    TestResult,
    ToolCapability,
)
from .session import Session, SessionConfig, SessionStatus


class OpenCodeClient:
    """
    High-level client for executing tasks via OpenCode.

    The client:
    1. Translates ExecutionRequest into session config
    2. Builds the prompt (context + constraints + task)
    3. Spawns and manages the session
    4. Parses session output into ExecutionResult
    5. Cleans up resources
    """

    def __init__(
        self,
        binary: str = "opencode",
        config_path: str = "config/opencode.json",
        default_timeout: int = 300,
    ):
        self.binary = binary
        self.config_path = config_path
        self.default_timeout = default_timeout

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute a task via OpenCode.

        This is the main entry point called by the orchestrator's
        execute_node. It handles the full lifecycle:
            build prompt → spawn session → parse result → cleanup

        Args:
            request: Validated ExecutionRequest from orchestrator.

        Returns:
            ExecutionResult with modified files, test results, metrics.
        """
        # 1. Build session config from request
        session_config = self._build_session_config(request)

        # 2. Build the prompt
        prompt = self._build_prompt(request)
        system_prompt = request.system_context

        # 3. Create and run session
        session = Session(config=session_config)
        session.create(prompt=prompt, system_prompt=system_prompt)

        try:
            raw_result = session.run()
        finally:
            session.cleanup()

        # 4. Parse result into ExecutionResult
        return self._parse_result(request.task_id, raw_result, session_config)

    def _build_session_config(self, request: ExecutionRequest) -> SessionConfig:
        """Map ExecutionRequest to SessionConfig."""
        return SessionConfig(
            binary=self.binary,
            config_path=self.config_path,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            working_dir=request.working_dir,
            timeout_seconds=request.timeout_seconds or self.default_timeout,
            non_interactive=True,
            output_format="json",
            enable_file=any(
                t.value.startswith("file:") for t in request.tools
            ),
            enable_terminal=ToolCapability.TERMINAL_RUN in request.tools,
            enable_git=any(
                t.value.startswith("git:") for t in request.tools
            ),
            enable_patch=any(
                t.value.startswith("patch:") for t in request.tools
            ),
        )

    def _build_prompt(self, request: ExecutionRequest) -> str:
        """
        Compose the task prompt sent to OpenCode.

        Structure:
            ## Constraints
            - constraint 1
            - constraint 2

            ## Previous Errors (if retry)
            - error from attempt 1

            ## Task
            description

            ## Target Files
            - file1.cpp
            - file2.h

            ## Acceptance Criteria
            - [ ] criterion 1
            - [ ] criterion 2
        """
        parts: list[str] = []

        # Constraints
        if request.constraints:
            constraints = "\n".join(f"- {c}" for c in request.constraints)
            parts.append(f"## Constraints\n\n{constraints}")

        # Previous errors (retry context)
        if request.previous_errors:
            errors = "\n".join(f"- Attempt {i+1}: {e}" for i, e in enumerate(request.previous_errors))
            parts.append(f"## Previous Errors (fix these)\n\n{errors}")

        # Task description
        parts.append(f"## Task ({request.operation.value})\n\n{request.description}")

        # Target files
        if request.target_files:
            files = "\n".join(f"- `{f}`" for f in request.target_files)
            parts.append(f"## Target Files\n\n{files}")

        # Acceptance criteria
        if request.acceptance_criteria:
            criteria = "\n".join(f"- [ ] {c}" for c in request.acceptance_criteria)
            parts.append(f"## Acceptance Criteria\n\n{criteria}")

        return "\n\n---\n\n".join(parts)

    def _parse_result(
        self, task_id: str, raw: "SessionResult", config: SessionConfig
    ) -> ExecutionResult:
        """
        Parse raw session output into structured ExecutionResult.

        Handles both JSON output (preferred) and plain text fallback.
        """
        # Timeout
        if raw.status == SessionStatus.TIMEOUT:
            return ExecutionResult(
                task_id=task_id,
                status="timeout",
                error=f"Session timed out after {config.timeout_seconds}s",
                retryable=True,
                duration_seconds=raw.duration_seconds,
            )

        # Binary not found
        if raw.status == SessionStatus.FAILED and "not found" in raw.stderr:
            return ExecutionResult(
                task_id=task_id,
                status="failure",
                error=raw.stderr,
                retryable=False,
            )

        # Try JSON parsing (structured output)
        if raw.exit_code == 0 and raw.stdout.strip():
            return self._parse_json_output(task_id, raw)

        # Non-zero exit code = failure
        if raw.exit_code != 0:
            return ExecutionResult(
                task_id=task_id,
                status="failure",
                error=raw.stderr or raw.stdout[-500:],
                output=raw.stdout[-500:],
                retryable=True,
                duration_seconds=raw.duration_seconds,
            )

        # Fallback: treat any stdout as success summary
        return ExecutionResult(
            task_id=task_id,
            status="success",
            summary=raw.stdout[:500],
            output=raw.stdout,
            duration_seconds=raw.duration_seconds,
        )

    def _parse_json_output(self, task_id: str, raw: "SessionResult") -> ExecutionResult:
        """Parse structured JSON output from OpenCode."""
        try:
            data = json.loads(raw.stdout)
        except json.JSONDecodeError:
            # Not JSON — use as plain text
            return ExecutionResult(
                task_id=task_id,
                status="success",
                summary=raw.stdout[:500],
                output=raw.stdout,
                duration_seconds=raw.duration_seconds,
            )

        # Map JSON fields to ExecutionResult
        file_changes = [
            FileChange(
                path=f.get("path", ""),
                action=f.get("action", "modified"),
                lines_added=f.get("lines_added", 0),
                lines_removed=f.get("lines_removed", 0),
                patch=f.get("patch", ""),
            )
            for f in data.get("file_changes", [])
        ]

        build_result = None
        if "build" in data:
            b = data["build"]
            build_result = TestResult(
                passed=1 if b.get("success") else 0,
                failed=0 if b.get("success") else 1,
                total=1,
                output=b.get("output", "")[:500],
            )

        test_result = None
        if "tests" in data:
            t = data["tests"]
            test_result = TestResult(
                passed=t.get("passed", 0),
                failed=t.get("failed", 0),
                skipped=t.get("skipped", 0),
                total=t.get("total", 0),
                output=t.get("output", "")[:500],
                duration_seconds=t.get("duration", 0.0),
            )

        return ExecutionResult(
            task_id=task_id,
            status="success" if data.get("success", True) else "failure",
            file_changes=file_changes,
            modified_files=[f.path for f in file_changes],
            build_result=build_result,
            test_result=test_result,
            summary=data.get("summary", ""),
            output=raw.stdout[:2000],
            tokens_input=data.get("usage", {}).get("input_tokens", 0),
            tokens_output=data.get("usage", {}).get("output_tokens", 0),
            cost_usd=data.get("usage", {}).get("cost_usd", 0.0),
            model_used=data.get("model", ""),
            duration_seconds=raw.duration_seconds,
            learnings=data.get("learnings", []),
            git_branch=data.get("git_branch", ""),
            git_commit=data.get("git_commit", ""),
            retryable=not data.get("success", True),
        )
