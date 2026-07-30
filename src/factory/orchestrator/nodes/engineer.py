"""
Engineer Node — Code Implementation via OpenCode.

The primary execution node. Spawns an OpenCode session that:
    1. Receives context (Tier 1-4) as system prompt
    2. Receives task description + constraints + acceptance criteria
    3. Edits files, runs build, runs tests
    4. Returns modified files + test results

This is the node that actually PRODUCES artifacts (code changes).

READS from state:
    - task.description, task.domain, task.target_files
    - classification.task_type
    - context (full bundle for system prompt)
    - routing (model to use)
    - plan.task_breakdown (if planning happened)
    - retry.attempt, retry.errors (if retrying)

WRITES to state:
    - execution: { modified_files, output, token_usage, learnings }
    - status: "executing"
    - current_node: "engineer"
    - history: append "engineer"

DEPENDENCIES (injected):
    - executor_client: OpenCodeClient
    - adapter_factory: get_adapter function
"""

from __future__ import annotations

import structlog

from factory.executor.adapters import get_adapter
from factory.executor.client import OpenCodeClient
from factory.executor.contracts import ExecutionRequest, Operation, ToolCapability
from factory.orchestrator.state import FactoryState

log = structlog.get_logger()


def engineer_node(
    state: FactoryState,
    executor_client: OpenCodeClient | None = None,
    adapter_factory=None,
) -> dict:
    """
    Execute code implementation via OpenCode subprocess.

    Strategy:
    1. Build system prompt from context bundle
    2. Build task prompt from description + constraints + acceptance criteria
    3. Include retry errors if this is a retry attempt
    4. Spawn OpenCode session with configured model
    5. Parse results (modified files, test results, learnings)

    Args:
        state: Current workflow state.
        executor_client: OpenCodeClient (injected for testing).
        adapter_factory: Function to get domain adapter (injected for testing).

    Returns:
        Partial state update with execution results.
    """
    task = state.get("task", {})
    context = state.get("context", {})
    routing = state.get("routing", {})
    classification = state.get("classification", {})
    plan = state.get("plan", {})
    retry = state.get("retry", {})

    description = task.get("description", "")
    domain = task.get("domain", "firmware")
    target_files = plan.get("refined_target_files") or task.get("target_files", [])
    attempt = retry.get("attempt", 1)
    previous_errors = retry.get("errors", [])

    log.info("engineer.executing", domain=domain, attempt=attempt, description=description[:60])

    # --- Get domain adapter ---
    if adapter_factory is None:
        adapter_factory = get_adapter

    try:
        adapter = adapter_factory(domain)
    except ValueError:
        adapter = adapter_factory("firmware")  # Fallback

    # --- Build system context ---
    system_context = _compose_system_prompt(context)

    # --- Build acceptance criteria ---
    acceptance = _extract_acceptance(plan, classification)

    # --- Build execution request ---
    request = ExecutionRequest(
        task_id=task.get("task_id", "UNKNOWN"),
        operation=_infer_operation(classification.get("task_type", "coding")),
        description=description,
        target_files=target_files,
        acceptance_criteria=acceptance,
        system_context=system_context,
        constraints=adapter.constraints,
        model=routing.get("model_id", "default"),
        max_tokens=routing.get("max_tokens", 8192),
        temperature=routing.get("temperature", 0.1),
        working_dir=adapter.working_dir,
        timeout_seconds=300,
        tools=_get_tools_for_operation(classification.get("task_type", "coding")),
        dry_run=False,
        previous_errors=previous_errors,
        attempt=attempt,
    )

    # --- Execute ---
    if executor_client is None:
        executor_client = OpenCodeClient()

    try:
        result = executor_client.execute(request)
    except Exception as e:
        log.error("engineer.execution_failed", error=str(e))
        return {
            "execution": {
                "modified_files": [],
                "output": "",
                "token_usage": {},
                "learnings": [],
            },
            "status": "failed",
            "error": f"Execution error: {e}",
            "current_node": "engineer",
            "history": state.get("history", []) + ["engineer"],
        }

    # --- Process result ---
    log.info(
        "engineer.completed",
        status=result.status,
        files=len(result.modified_files),
        tokens_in=result.tokens_input,
        tokens_out=result.tokens_output,
    )

    # Update retry state if this was a retry
    updated_retry = retry.copy() if retry else {}
    if result.status != "success" and attempt < updated_retry.get("max_attempts", 3):
        updated_retry["attempt"] = attempt + 1
        updated_retry.setdefault("errors", []).append(result.error or "execution failed")

    return {
        "execution": {
            "modified_files": result.modified_files,
            "output": result.summary or result.output[:500],
            "token_usage": {
                "input": result.tokens_input,
                "output": result.tokens_output,
                "cost_usd": result.cost_usd,
                "model": result.model_used,
                "latency": result.duration_seconds,
            },
            "learnings": result.learnings,
        },
        "retry": updated_retry if updated_retry else retry,
        "status": "executing" if result.status == "success" else "failed",
        "error": result.error if result.status != "success" else None,
        "current_node": "engineer",
        "history": state.get("history", []) + ["engineer"],
    }


# --- Helpers ---


def _compose_system_prompt(context: dict) -> str:
    """Compose system prompt from context tiers."""
    parts: list[str] = []

    tier1 = context.get("tier1_content", "")
    if tier1:
        parts.append(f"## Principles & Constraints\n\n{tier1}")

    tier2 = context.get("tier2_content", "")
    if tier2:
        parts.append(f"## Domain Specification\n\n{tier2}")

    tier3 = context.get("tier3_content", "")
    if tier3:
        parts.append(f"## Target Files\n\n{tier3}")

    tier4 = context.get("tier4_content", "")
    if tier4:
        parts.append(f"## Codebase Patterns\n\n{tier4}")

    return "\n\n---\n\n".join(parts)


def _extract_acceptance(plan: dict, classification: dict) -> list[str]:
    """Extract acceptance criteria from plan or generate defaults."""
    # From plan (if planning happened)
    task_breakdown = plan.get("task_breakdown", [])
    if task_breakdown:
        criteria = []
        for task_item in task_breakdown:
            criteria.extend(task_item.get("acceptance_criteria", []))
        if criteria:
            return criteria

    # Default criteria based on task type
    task_type = classification.get("task_type", "coding")
    defaults = {
        "coding": ["All new logic has unit tests", "Build passes", "Tests pass", "No magic numbers"],
        "debugging": ["Root cause identified", "Fix verified by test", "No regression"],
        "refactoring": ["Behavior unchanged", "Tests still pass", "Build passes"],
        "documentation": ["Output is accurate and complete"],
    }
    return defaults.get(task_type, ["Build passes", "Tests pass"])


def _infer_operation(task_type: str) -> Operation:
    """Map task type to execution operation."""
    mapping = {
        "coding": Operation.IMPLEMENT,
        "debugging": Operation.FIX,
        "refactoring": Operation.REFACTOR,
        "documentation": Operation.DOCUMENT,
        "review": Operation.REVIEW,
    }
    return mapping.get(task_type, Operation.IMPLEMENT)


def _get_tools_for_operation(task_type: str) -> list[ToolCapability]:
    """Determine which tools OpenCode should have access to."""
    base_tools = [
        ToolCapability.FILE_READ,
        ToolCapability.FILE_WRITE,
        ToolCapability.FILE_CREATE,
        ToolCapability.FILE_LIST,
        ToolCapability.TERMINAL_RUN,
        ToolCapability.GIT_STATUS,
        ToolCapability.GIT_DIFF,
        ToolCapability.GIT_BRANCH,
        ToolCapability.GIT_ADD,
        ToolCapability.GIT_COMMIT,
        ToolCapability.PATCH_APPLY,
        ToolCapability.PATCH_CREATE,
    ]

    # Documentation doesn't need git/patch
    if task_type == "documentation":
        return [ToolCapability.FILE_READ, ToolCapability.FILE_LIST]

    # Review is read-only
    if task_type == "review":
        return [ToolCapability.FILE_READ, ToolCapability.GIT_DIFF, ToolCapability.GIT_STATUS]

    return base_tools
