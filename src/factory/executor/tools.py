"""
MCP Tool Definitions.

Defines the tool capabilities available to OpenCode sessions.
Each tool has:
    - Name and description
    - Parameters schema
    - Safety constraints
    - Permission requirements

These definitions are used to:
    1. Configure which tools a session can access
    2. Validate tool calls against security policy
    3. Generate tool documentation for the model's context
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolPermission(Enum):
    """Permission level for tool operations."""

    READ = "read"           # Read-only access
    WRITE = "write"         # Can modify
    CREATE = "create"       # Can create new
    DELETE = "delete"       # Can remove (restricted)
    EXECUTE = "execute"     # Can run commands


@dataclass
class ToolDefinition:
    """Schema for an MCP tool available to OpenCode."""

    name: str
    description: str
    permissions: list[ToolPermission]
    parameters: dict = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


# --- File Tool ---

FILE_TOOL = ToolDefinition(
    name="file",
    description=(
        "Read, write, create, and list files in the project repository. "
        "All paths are relative to the repository root. "
        "Cannot access .raceos/, .ai/, .env, or config/."
    ),
    permissions=[
        ToolPermission.READ,
        ToolPermission.WRITE,
        ToolPermission.CREATE,
    ],
    parameters={
        "read": {"path": "string — relative file path"},
        "write": {"path": "string", "content": "string — full file content"},
        "create": {"path": "string", "content": "string — initial content"},
        "list": {"path": "string — directory path", "depth": "int — max recursion depth"},
    },
    constraints=[
        "Paths must be relative (no leading /)",
        "Cannot access: .raceos/**, .ai/**, .env, config/**",
        "Cannot access: **/.git/**, node_modules/**",
        "Maximum file size: 5000 lines",
        "Maximum 20 file operations per session",
    ],
    examples=[
        'file.read("firmware/middleware/ecu_parser.h")',
        'file.write("firmware/middleware/ecu_parser.cpp", content)',
        'file.create("firmware/tests/test_new_feature.cpp", test_content)',
        'file.list("firmware/middleware/", depth=1)',
    ],
)


# --- Terminal Tool ---

TERMINAL_TOOL = ToolDefinition(
    name="terminal",
    description=(
        "Execute shell commands for building, testing, and inspecting. "
        "Commands are validated against an allowlist before execution. "
        "Cannot run destructive, network, or privilege-escalation commands."
    ),
    permissions=[ToolPermission.EXECUTE],
    parameters={
        "run": {
            "command": "string — shell command to execute",
            "working_dir": "string — optional override (default: repo root)",
            "timeout": "int — seconds before kill (default: 120)",
        },
    },
    constraints=[
        "Command must match allowlist (pio, pytest, npm, make, grep, find, ls, cat, etc.)",
        "Blocked: rm -rf, sudo, curl, wget, ssh, chmod 777, kill, shutdown",
        "Maximum output: 500 lines (truncated if exceeded)",
        "Maximum timeout: 120 seconds per command",
        "Working directory must be within repository tree",
    ],
    examples=[
        'terminal.run("pio build -e native")',
        'terminal.run("pio test -e native")',
        'terminal.run("pytest tests/ -v --tb=short")',
        'terminal.run("grep -rn TODO firmware/middleware/")',
    ],
)


# --- Git Tool ---

GIT_TOOL = ToolDefinition(
    name="git",
    description=(
        "Perform version control operations. "
        "Can create branches, stage files, and commit changes. "
        "Cannot push, force-push, or modify history destructively."
    ),
    permissions=[
        ToolPermission.READ,
        ToolPermission.WRITE,
        ToolPermission.CREATE,
    ],
    parameters={
        "status": {},
        "diff": {"path": "string — optional file path for targeted diff"},
        "log": {"count": "int — number of commits (default: 10)"},
        "branch": {"name": "string — branch name (auto-prefixed with factory/)"},
        "checkout": {"branch": "string — branch to switch to"},
        "add": {"paths": "list[string] — files to stage"},
        "commit": {"message": "string — commit message (auto-prefixed with [factory])"},
        "stash": {"action": "string — push | pop | list"},
    },
    constraints=[
        "Branch names auto-prefixed with 'factory/'",
        "Cannot commit to main/master branch",
        "Cannot push (human reviews and pushes)",
        "Cannot force-push or reset --hard",
        "Cannot delete branches (branch -D blocked)",
        "Commit messages auto-prefixed with '[factory]'",
        "Maximum diff output: 1000 lines",
    ],
    examples=[
        'git.status()',
        'git.branch("fix-ecu-parser-typo")',
        'git.add(["firmware/middleware/ecu_parser.cpp"])',
        'git.commit("fix typo in parser header comment")',
        'git.diff("firmware/middleware/ecu_parser.cpp")',
    ],
)


# --- Patch Tool ---

PATCH_TOOL = ToolDefinition(
    name="patch",
    description=(
        "Create and apply unified diff patches. "
        "Patches are atomic, reviewable, and reversible. "
        "Preferred over full file rewrites for targeted changes."
    ),
    permissions=[
        ToolPermission.READ,
        ToolPermission.WRITE,
        ToolPermission.CREATE,
    ],
    parameters={
        "create": {
            "file": "string — file to diff against",
            "changes": "string — description of changes to make",
        },
        "apply": {
            "patch": "string — unified diff content",
            "file": "string — target file path",
            "dry_run": "bool — preview without applying (default: false)",
        },
        "preview": {
            "patch": "string — unified diff to preview",
            "file": "string — target file",
        },
    },
    constraints=[
        "Maximum patch size: 50KB",
        "Patch is validated before applying (must apply cleanly)",
        "Backup created before apply (recoverable)",
        "Only allowed file extensions: .cpp, .h, .c, .py, .ts, .tsx, .md, .yaml, .json, .toml",
        "Cannot patch binary files",
        "Cannot patch files in blocked paths (.raceos/, .ai/, .env)",
    ],
    examples=[
        'patch.create("firmware/middleware/ecu_parser.h", "add const to return type")',
        'patch.apply(unified_diff, "firmware/middleware/ecu_parser.cpp")',
        'patch.preview(unified_diff, "firmware/middleware/ecu_parser.cpp")',
    ],
)


# --- Tool Registry ---

ALL_TOOLS: dict[str, ToolDefinition] = {
    "file": FILE_TOOL,
    "terminal": TERMINAL_TOOL,
    "git": GIT_TOOL,
    "patch": PATCH_TOOL,
}


def get_tools_for_operation(operation: str) -> list[ToolDefinition]:
    """
    Return appropriate tools for an operation type.

    Different operations need different tool sets:
        implement → all tools
        review → file (read-only), git (diff)
        test → terminal only
        document → file only
    """
    operation_tools = {
        "implement": ["file", "terminal", "git", "patch"],
        "refactor": ["file", "terminal", "git", "patch"],
        "fix": ["file", "terminal", "git", "patch"],
        "test": ["file", "terminal"],
        "review": ["file", "git"],
        "document": ["file", "git"],
    }
    tool_names = operation_tools.get(operation, ["file", "terminal", "git", "patch"])
    return [ALL_TOOLS[name] for name in tool_names if name in ALL_TOOLS]


def generate_tool_context(tools: list[ToolDefinition]) -> str:
    """
    Generate a text description of available tools for the model's context.

    This is injected into the system prompt so the model knows what tools
    it can call and what constraints apply.
    """
    parts: list[str] = []
    for tool in tools:
        constraints = "\n".join(f"    - {c}" for c in tool.constraints)
        parts.append(
            f"### {tool.name}\n"
            f"{tool.description}\n"
            f"  Constraints:\n{constraints}"
        )
    return "\n\n".join(parts)
