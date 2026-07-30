"""
Documentation Output Persistence.

Detects when a task produces substantial documentation output
and suggests (or auto-saves) it to the appropriate project location.

Triggers when:
    - task_type is "documentation", "analysis", or "research"
    - Output exceeds MIN_PERSIST_TOKENS (500 tokens)
    - No code files were modified (pure documentation output)

Does NOT auto-save without human consent (respects "AI suggests,
human decides"). Provides:
    - Suggested file path based on domain + content
    - Save command for the human to execute
    - Auto-save mode (opt-in via config)

Usage:
    suggestion = suggest_persist(state)
    if suggestion:
        # Show to human via CLI
        print(f"💾 Save to: {suggestion.path}")
        print(f"   Run: factory save {task_id} --path {suggestion.path}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Minimum output size to suggest persistence (in estimated tokens)
MIN_PERSIST_TOKENS = 500

# Task types that produce persistable documentation
PERSISTABLE_TASK_TYPES = {"documentation", "analysis", "research", "hardware"}

# Domain → base directory mapping
DOMAIN_PATHS = {
    "firmware": "docs/",
    "hardware": "hardware/",
    "mobile": "docs/mobile/",
    "backend": "docs/backend/",
    "docs": "docs/",
}


@dataclass
class PersistSuggestion:
    """Suggestion to save documentation output to a file."""

    should_persist: bool
    path: str                   # Suggested relative file path
    title: str                  # Human-readable title
    content: str                # Content to save
    token_count: int            # Estimated tokens in output
    reason: str                 # Why we suggest persisting
    auto_save: bool = False     # Whether to auto-save (config-driven)


def suggest_persist(state: dict) -> PersistSuggestion | None:
    """
    Analyze task result and suggest persistence if appropriate.

    Args:
        state: Complete FactoryState after execution.

    Returns:
        PersistSuggestion if output should be saved, None otherwise.
    """
    classification = state.get("classification", {})
    execution = state.get("execution", {})
    task = state.get("task", {})

    task_type = classification.get("task_type", "")
    modified_files = execution.get("modified_files", [])
    output = execution.get("output", "")
    description = task.get("description", "")
    domain = task.get("domain", "firmware")

    # --- Check if persistence is appropriate ---

    # Only for documentation-type tasks
    if task_type not in PERSISTABLE_TASK_TYPES:
        return None

    # Only if no code was modified (pure documentation)
    if modified_files:
        return None

    # Only if output is substantial
    estimated_tokens = len(output) // 4  # ~4 chars per token
    if estimated_tokens < MIN_PERSIST_TOKENS:
        return None

    # Only if output looks like documentation (not an error message)
    if not _looks_like_documentation(output):
        return None

    # --- Generate suggestion ---

    suggested_path = _generate_path(description, domain)
    title = _extract_title(output, description)

    return PersistSuggestion(
        should_persist=True,
        path=suggested_path,
        title=title,
        content=output,
        token_count=estimated_tokens,
        reason=f"Documentation output ({estimated_tokens} tokens) detected. "
               f"Consider saving to prevent knowledge loss.",
    )


def save_output(suggestion: PersistSuggestion, repo_root: str = "..") -> Path:
    """
    Save documentation output to the suggested path.

    Called when human confirms: `factory save TASK-ID --path <path>`

    Args:
        suggestion: The persistence suggestion with content + path.
        repo_root: Repository root directory.

    Returns:
        Path to the saved file.
    """
    full_path = Path(repo_root) / suggestion.path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(suggestion.content, encoding="utf-8")
    return full_path


def _generate_path(description: str, domain: str) -> str:
    """Generate a file path from task description and domain."""
    base_dir = DOMAIN_PATHS.get(domain, "docs/")
    slug = _slugify(description)
    return f"{base_dir}{slug}.md"


def _extract_title(output: str, description: str) -> str:
    """Extract a title from the output or fall back to description."""
    # Try to find a markdown H1 in output
    for line in output.splitlines()[:10]:
        if line.startswith("# "):
            return line[2:].strip()
    # Fall back to truncated description
    return description[:80]


def _looks_like_documentation(output: str) -> bool:
    """Heuristic: does the output look like documentation?"""
    indicators = [
        output.count("#") >= 2,          # Has markdown headers
        output.count("|") >= 4,          # Has tables
        output.count("```") >= 2,        # Has code blocks
        output.count("\n") >= 10,        # Multi-line
        len(output) > 500,               # Substantial length
    ]
    return sum(indicators) >= 2  # At least 2 indicators


def _slugify(text: str) -> str:
    """Convert description to filesystem-safe slug."""
    # Take first meaningful words
    slug = text.lower().strip()
    # Remove non-alphanumeric (keep spaces for now)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    # Replace spaces with hyphens
    slug = re.sub(r"\s+", "-", slug)
    # Truncate
    slug = slug[:60].strip("-")
    return slug or "unnamed-doc"
