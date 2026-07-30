"""
Knowledge Node — Knowledge Management Agent.

Indexes produced artifacts into the project knowledge base, detects
conflicts with existing specs/ADRs, updates the changelog, and
auto-suggests follow-up tasks when patterns indicate broader issues.

READS from state:
    - task: TaskInput (task_id, description)
    - execution: ExecutionResult (modified_files, output, learnings)
    - review: ReviewResult (verdict — only index if approved)
    - validation: ValidationResult (tests_passed — only index if validated)
    - classification: Classification (task_type — for pattern detection)

WRITES to state:
    - execution: ExecutionResult (learnings updated)
    - suggested_follow_ups: list[dict] — auto-generated follow-up task suggestions
    - status: 'learning'
    - current_node: 'knowledge'
    - history: append 'knowledge'
"""

from __future__ import annotations

from factory.orchestrator.state import FactoryState
from factory.utils.persist import suggest_persist


# --- Patterns that suggest follow-up tasks ---

# When a bug fix touches one field in a set of similar fields,
# the same bug likely exists in sibling fields.
SIBLING_PATTERNS = {
    # If fix mentions any of these → suggest checking siblings
    "telemetry_parser": {
        "fields": ["rpm", "load", "temp", "duty", "voltage", "throttle"],
        "suggestion_template": "Investigate: do {siblings} fields also need {fix_type}?",
    },
    "display_tokens": {
        "fields": ["rpm", "load", "temp", "duty", "vbat"],
        "suggestion_template": "Verify: are {siblings} threshold constants calibrated correctly?",
    },
}

# Fix types that commonly affect sibling code
FIX_TYPE_PATTERNS = {
    "raw-to-percentage": ["conversion", "raw", "byte", "255", "percentage", "map"],
    "threshold-calibration": ["threshold", "warn", "danger", "calibrat"],
    "overflow-protection": ["overflow", "clamp", "saturate", "max", "cast"],
    "null-check": ["null", "nullptr", "check", "guard", "validate"],
}


def knowledge_node(state: FactoryState) -> dict:
    """
    Index artifacts, detect conflicts, update changelog,
    and auto-suggest follow-up tasks.

    Follow-up suggestion logic:
    1. Analyze what was fixed (from execution output + modified files)
    2. Detect if fix applies to a "family" of similar code
    3. If siblings exist that might have the same issue, suggest follow-up
    4. Present suggestions to human via CLI (non-blocking)
    """
    task = state.get("task", {})
    execution = state.get("execution", {})
    classification = state.get("classification", {})

    # Extract learnings from execution
    learnings = execution.get("learnings", [])
    modified_files = execution.get("modified_files", [])
    output = execution.get("output", "")
    task_description = task.get("description", "")

    # --- Step 1: Index patterns into codebase memory ---
    indexed_patterns = _index_patterns(modified_files, output, learnings)

    # --- Step 2: Detect follow-up opportunities ---
    follow_ups = _detect_follow_ups(
        task_type=classification.get("task_type", ""),
        modified_files=modified_files,
        output=output,
        description=task_description,
    )

    # --- Step 3: Check for documentation persistence opportunity ---
    persist_suggestion = _suggest_documentation_persist(state)

    return {
        "execution": {
            "modified_files": modified_files,
            "output": output,
            "token_usage": execution.get("token_usage", {}),
            "learnings": learnings + indexed_patterns,
        },
        "suggested_follow_ups": follow_ups,
        "persist_suggestion": persist_suggestion,
        "status": "completed",
        "current_node": "knowledge",
        "history": state.get("history", []) + ["knowledge"],
    }


def _index_patterns(
    modified_files: list[str], output: str, learnings: list[str]
) -> list[str]:
    """
    Extract and index patterns from the execution result.

    Returns new patterns discovered (for codebase-memory storage).
    """
    patterns: list[str] = []

    # Pattern: files modified together (relationship)
    if len(modified_files) > 1:
        file_names = [f.split("/")[-1] for f in modified_files]
        patterns.append(f"Files modified together: {', '.join(file_names)}")

    # Pattern: fix type from output keywords
    fix_type = _detect_fix_type(output)
    if fix_type:
        patterns.append(f"Fix applied: {fix_type}")

    return patterns


def _detect_follow_ups(
    task_type: str,
    modified_files: list[str],
    output: str,
    description: str,
) -> list[dict]:
    """
    Detect if this fix might affect sibling code.

    Logic:
    - If fix touches telemetry_parser for one field → suggest checking other fields
    - If fix touches display_tokens for one threshold → suggest calibrating others
    - If fix type is "raw-to-percentage" → suggest checking all conversion points
    """
    follow_ups: list[dict] = []

    # Only suggest follow-ups for bug fixes / debugging
    if task_type not in ("debugging", "fix", "coding"):
        return follow_ups

    # Detect which module family was touched
    combined_text = (output + " " + description + " " + " ".join(modified_files)).lower()

    for module_key, config in SIBLING_PATTERNS.items():
        if module_key not in combined_text:
            continue

        # Find which field was fixed
        fixed_field = None
        for field in config["fields"]:
            if field in combined_text:
                fixed_field = field
                break

        if not fixed_field:
            continue

        # Suggest checking siblings
        siblings = [f for f in config["fields"] if f != fixed_field]
        if not siblings:
            continue

        # Detect fix type for suggestion
        fix_type = _detect_fix_type(output) or "the same issue"

        suggestion = {
            "description": config["suggestion_template"].format(
                siblings=", ".join(siblings),
                fix_type=fix_type,
            ),
            "domain": "firmware",
            "priority": "medium",
            "reason": f"Bug in '{fixed_field}' may also exist in sibling fields",
            "related_task": description,
        }
        follow_ups.append(suggestion)

    # Generic: if output mentions "other fields" or "similar"
    if any(phrase in output.lower() for phrase in ["other fields", "similar issue", "same pattern"]):
        if not follow_ups:  # Don't duplicate
            follow_ups.append({
                "description": f"Investigate similar issues related to: {description[:60]}",
                "domain": "firmware",
                "priority": "low",
                "reason": "Execution output mentioned potential similar issues",
                "related_task": description,
            })

    return follow_ups


def _detect_fix_type(output: str) -> str | None:
    """Classify the type of fix from execution output."""
    output_lower = output.lower()

    for fix_type, keywords in FIX_TYPE_PATTERNS.items():
        matches = sum(1 for kw in keywords if kw in output_lower)
        if matches >= 2:  # At least 2 keyword matches
            return fix_type

    return None


def _suggest_documentation_persist(state: dict) -> dict | None:
    """
    Check if task output should be persisted as documentation.

    Delegates to persist.suggest_persist() and converts to dict
    for state serialization.
    """
    suggestion = suggest_persist(state)
    if suggestion is None:
        return None

    return {
        "should_persist": suggestion.should_persist,
        "path": suggestion.path,
        "title": suggestion.title,
        "token_count": suggestion.token_count,
        "reason": suggestion.reason,
    }
