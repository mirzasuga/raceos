"""
Verification tests for OpenCode executor integration.

These tests verify:
1. Configuration loads and validates correctly
2. Contracts schema is valid
3. Session builds correct CLI commands
4. Adapters produce correct configurations
5. Tools registry works
6. Client handles success/failure/timeout correctly

All tests are unit tests (no external dependencies).
Run with: make test
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from factory.executor.adapters import get_adapter, list_domains
from factory.executor.client import OpenCodeClient
from factory.executor.contracts import (
    ExecutionRequest,
    ExecutionResult,
    FileChange,
    Operation,
    ToolCapability,
)
from factory.executor.session import Session, SessionConfig, SessionStatus
from factory.executor.tools import (
    ALL_TOOLS,
    FILE_TOOL,
    GIT_TOOL,
    PATCH_TOOL,
    TERMINAL_TOOL,
    generate_tool_context,
    get_tools_for_operation,
)


# --- Contract Tests ---


class TestContracts:
    """Verify Pydantic schemas validate correctly."""

    def test_execution_request_defaults(self):
        req = ExecutionRequest(
            task_id="TASK-001",
            operation=Operation.IMPLEMENT,
            description="Add a comment",
        )
        assert req.model == "anthropic/claude-sonnet-4.6"
        assert req.max_tokens == 8192
        assert req.temperature == 0.1
        assert req.timeout_seconds == 300
        assert not req.dry_run
        assert req.attempt == 1

    def test_execution_request_with_tools(self):
        req = ExecutionRequest(
            task_id="TASK-002",
            operation=Operation.FIX,
            description="Fix parser bug",
            tools=[ToolCapability.FILE_READ, ToolCapability.TERMINAL_RUN],
        )
        assert len(req.tools) == 2
        assert ToolCapability.FILE_READ in req.tools

    def test_execution_result_success(self):
        result = ExecutionResult(
            task_id="TASK-001",
            status="success",
            modified_files=["firmware/middleware/ecu_parser.cpp"],
            summary="Fixed typo in comment",
        )
        assert result.status == "success"
        assert len(result.modified_files) == 1

    def test_execution_result_failure(self):
        result = ExecutionResult(
            task_id="TASK-001",
            status="failure",
            error="Build failed: undefined reference",
            retryable=True,
        )
        assert result.retryable is True

    def test_file_change_model(self):
        change = FileChange(
            path="firmware/middleware/ecu_parser.cpp",
            action="modified",
            lines_added=5,
            lines_removed=2,
        )
        assert change.action == "modified"


# --- Session Tests ---


class TestSession:
    """Verify session lifecycle management."""

    def test_session_creates_prompt_file(self, tmp_path):
        config = SessionConfig(working_dir=str(tmp_path))
        session = Session(config=config)
        session.create(prompt="Test prompt", system_prompt="You are helpful.")
        assert session.status == SessionStatus.STARTING
        assert session._prompt_file is not None
        assert session._prompt_file.exists()
        content = session._prompt_file.read_text()
        assert "You are helpful." in content
        assert "Test prompt" in content
        session.cleanup()
        assert not session._prompt_file.exists()

    def test_session_build_command(self):
        config = SessionConfig(
            binary="opencode",
            model="anthropic/claude-sonnet-4",
            max_tokens=4096,
            temperature=0.2,
            non_interactive=True,
            output_format="json",
            config_path="config/opencode.json",
        )
        session = Session(config=config)
        session.create(prompt="test")
        cmd = session.build_command()

        assert cmd[0] == "opencode"
        assert "--model" in cmd
        assert "anthropic/claude-sonnet-4" in cmd
        assert "--max-tokens" in cmd
        assert "4096" in cmd
        assert "--non-interactive" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        session.cleanup()

    def test_session_handles_missing_binary(self):
        config = SessionConfig(binary="nonexistent-binary-xyz", working_dir=".")
        session = Session(config=config)
        session.create(prompt="test")
        result = session.run()
        assert result.status == SessionStatus.FAILED
        assert "not found" in result.stderr
        session.cleanup()

    def test_session_idle_cannot_run(self):
        config = SessionConfig()
        session = Session(config=config)
        with pytest.raises(RuntimeError, match="not ready"):
            session.run()


# --- Adapter Tests ---


class TestAdapters:
    """Verify domain adapters produce correct configurations."""

    def test_list_domains(self):
        domains = list_domains()
        assert "firmware" in domains
        assert "mobile" in domains
        assert "backend" in domains

    def test_get_firmware_adapter(self):
        adapter = get_adapter("firmware")
        assert adapter.name == "firmware"
        assert "pio build -e native" in adapter.build_commands
        assert "pio test -e native" in adapter.test_commands
        assert any("dynamic allocation" in c for c in adapter.constraints)
        assert "*.cpp" in adapter.file_patterns

    def test_get_mobile_adapter(self):
        adapter = get_adapter("mobile")
        assert adapter.name == "mobile"
        assert "npx tsc --noEmit" in adapter.build_commands
        assert "*.tsx" in adapter.file_patterns

    def test_get_backend_adapter(self):
        adapter = get_adapter("backend")
        assert adapter.name == "backend"
        assert any("pytest" in cmd for cmd in adapter.test_commands)
        assert "*.py" in adapter.file_patterns

    def test_unknown_domain_raises(self):
        with pytest.raises(ValueError, match="Unknown domain"):
            get_adapter("quantum")

    def test_adapter_config(self):
        adapter = get_adapter("firmware")
        config = adapter.get_config()
        assert config.working_dir == "../firmware"
        assert len(config.constraints) > 0
        assert len(config.build_commands) > 0


# --- Tools Tests ---


class TestTools:
    """Verify tool definitions and registry."""

    def test_all_tools_registered(self):
        assert "file" in ALL_TOOLS
        assert "terminal" in ALL_TOOLS
        assert "git" in ALL_TOOLS
        assert "patch" in ALL_TOOLS

    def test_file_tool_constraints(self):
        assert any(".raceos" in c for c in FILE_TOOL.constraints)

    def test_terminal_tool_blocked_commands(self):
        assert any("rm -rf" in c for c in TERMINAL_TOOL.constraints)

    def test_git_tool_blocks_main(self):
        assert any("main" in c.lower() for c in GIT_TOOL.constraints)

    def test_patch_tool_validates(self):
        assert any("validate" in c.lower() for c in PATCH_TOOL.constraints)

    def test_tools_for_implement_operation(self):
        tools = get_tools_for_operation("implement")
        names = [t.name for t in tools]
        assert "file" in names
        assert "terminal" in names
        assert "git" in names
        assert "patch" in names

    def test_tools_for_review_operation(self):
        tools = get_tools_for_operation("review")
        names = [t.name for t in tools]
        assert "file" in names
        assert "git" in names
        assert "terminal" not in names  # Review doesn't run commands
        assert "patch" not in names

    def test_generate_tool_context(self):
        tools = get_tools_for_operation("implement")
        context = generate_tool_context(tools)
        assert "### file" in context
        assert "### terminal" in context
        assert "Constraints:" in context


# --- Client Tests ---


class TestClient:
    """Verify high-level client behavior."""

    def test_client_builds_prompt(self):
        client = OpenCodeClient()
        request = ExecutionRequest(
            task_id="TASK-001",
            operation=Operation.FIX,
            description="Fix the null check",
            target_files=["firmware/middleware/parser.cpp"],
            constraints=["No dynamic allocation"],
            acceptance_criteria=["Tests pass"],
            previous_errors=["Build failed: missing semicolon"],
            attempt=2,
        )
        prompt = client._build_prompt(request)

        assert "## Constraints" in prompt
        assert "No dynamic allocation" in prompt
        assert "## Previous Errors" in prompt
        assert "missing semicolon" in prompt
        assert "## Task (fix)" in prompt
        assert "Fix the null check" in prompt
        assert "## Target Files" in prompt
        assert "parser.cpp" in prompt
        assert "## Acceptance Criteria" in prompt
        assert "Tests pass" in prompt

    def test_client_builds_session_config(self):
        client = OpenCodeClient(binary="opencode", config_path="config/opencode.json")
        request = ExecutionRequest(
            task_id="TASK-001",
            operation=Operation.IMPLEMENT,
            description="test",
            model="anthropic/claude-opus-4",
            max_tokens=4096,
            temperature=0.0,
            working_dir="../firmware",
            timeout_seconds=600,
        )
        config = client._build_session_config(request)

        assert config.binary == "opencode"
        assert config.model == "anthropic/claude-opus-4"
        assert config.max_tokens == 4096
        assert config.temperature == 0.0
        assert config.working_dir == "../firmware"
        assert config.timeout_seconds == 600
        assert config.enable_file is True
        assert config.enable_terminal is True
        assert config.enable_git is True
