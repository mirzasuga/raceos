"""
Execution Contracts.

Pydantic schemas defining the interface between the orchestrator
and the OpenCode executor. These are the only data structures
that cross the orchestrator → executor boundary.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Operation(str, Enum):
    """Type of execution operation."""

    IMPLEMENT = "implement"       # Write new code from spec
    REFACTOR = "refactor"         # Restructure existing code
    FIX = "fix"                   # Fix a bug (test-first)
    TEST = "test"                 # Write/run tests only
    REVIEW = "review"             # Review code (read-only)
    DOCUMENT = "document"         # Add/update documentation


class ToolCapability(str, Enum):
    """Available tool capabilities for a session."""

    FILE_READ = "file:read"
    FILE_WRITE = "file:write"
    FILE_CREATE = "file:create"
    FILE_LIST = "file:list"
    TERMINAL_RUN = "terminal:run"
    GIT_STATUS = "git:status"
    GIT_DIFF = "git:diff"
    GIT_BRANCH = "git:branch"
    GIT_COMMIT = "git:commit"
    GIT_ADD = "git:add"
    GIT_LOG = "git:log"
    PATCH_APPLY = "patch:apply"
    PATCH_CREATE = "patch:create"
    PATCH_PREVIEW = "patch:preview"


class ExecutionRequest(BaseModel):
    """Request from orchestrator to executor."""

    # --- Identity ---
    task_id: str = Field(description="Unique task identifier")
    operation: Operation = Field(description="Type of operation to perform")

    # --- Task ---
    description: str = Field(description="Natural language task description")
    target_files: list[str] = Field(default_factory=list, description="Files to modify")
    acceptance_criteria: list[str] = Field(default_factory=list, description="How to verify success")

    # --- Context (injected by orchestrator) ---
    system_context: str = Field(default="", description="Composed context from Tier 1-4")
    constraints: list[str] = Field(default_factory=list, description="Rules the executor must follow")

    # --- Model (selected by 9Router) ---
    model: str = Field(default="anthropic/claude-sonnet-4.6", description="Model ID to use")
    max_tokens: int = Field(default=8192, description="Max output tokens")
    temperature: float = Field(default=0.1, description="Sampling temperature")

    # --- Execution Config ---
    working_dir: str = Field(default="..", description="Working directory for execution")
    timeout_seconds: int = Field(default=300, description="Kill session after this duration")
    tools: list[ToolCapability] = Field(
        default_factory=lambda: [
            ToolCapability.FILE_READ,
            ToolCapability.FILE_WRITE,
            ToolCapability.FILE_CREATE,
            ToolCapability.FILE_LIST,
            ToolCapability.TERMINAL_RUN,
            ToolCapability.GIT_STATUS,
            ToolCapability.GIT_DIFF,
            ToolCapability.GIT_BRANCH,
            ToolCapability.GIT_COMMIT,
            ToolCapability.GIT_ADD,
            ToolCapability.PATCH_APPLY,
            ToolCapability.PATCH_CREATE,
        ],
        description="Tools available to OpenCode for this session",
    )
    dry_run: bool = Field(default=False, description="Preview changes without writing")

    # --- Retry Context (populated on retry) ---
    previous_errors: list[str] = Field(default_factory=list, description="Errors from previous attempts")
    attempt: int = Field(default=1, description="Current attempt number")


class FileChange(BaseModel):
    """A single file modification made by the executor."""

    path: str = Field(description="Relative file path")
    action: str = Field(description="created | modified | deleted")
    lines_added: int = Field(default=0)
    lines_removed: int = Field(default=0)
    patch: str = Field(default="", description="Unified diff of the change")


class TestResult(BaseModel):
    """Test execution results."""

    passed: int = Field(default=0)
    failed: int = Field(default=0)
    skipped: int = Field(default=0)
    total: int = Field(default=0)
    output: str = Field(default="", description="Test runner stdout (truncated)")
    duration_seconds: float = Field(default=0.0)


class ExecutionResult(BaseModel):
    """Response from executor to orchestrator."""

    # --- Identity ---
    task_id: str
    status: str = Field(description="success | failure | timeout | blocked")

    # --- Artifacts ---
    file_changes: list[FileChange] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list, description="Flat list of modified paths")

    # --- Validation ---
    build_result: TestResult | None = Field(default=None, description="Build output")
    test_result: TestResult | None = Field(default=None, description="Test output")

    # --- Output ---
    summary: str = Field(default="", description="What the executor did (natural language)")
    output: str = Field(default="", description="Raw stdout from session")

    # --- Metrics ---
    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    duration_seconds: float = Field(default=0.0)
    model_used: str = Field(default="")

    # --- Errors ---
    error: str = Field(default="", description="Error message if status != success")
    retryable: bool = Field(default=False, description="Whether this failure is worth retrying")

    # --- Learnings (for Codebase Memory) ---
    learnings: list[str] = Field(default_factory=list, description="Patterns discovered during execution")
    git_branch: str = Field(default="", description="Branch where changes were committed")
    git_commit: str = Field(default="", description="Commit SHA (if committed)")
