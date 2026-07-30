"""
CLI ↔ Factory Bridge.

The ONLY connection point between the CLI layer and the AI Factory.
All commands route through this bridge. It handles:

    - Task submission (CLI intent → LangGraph invocation)
    - Progress observation (state changes → UI updates)
    - Streaming relay (LLM tokens → terminal output)
    - Resume/retry/cancel (checkpoint manipulation)
    - Session coordination (CLI session ↔ factory state)

Flow:
    CLI input → intent detection → bridge.submit() → LangGraph → agents → result
    
    bridge.submit()
        ├── Create checkpoint
        ├── Build initial state
        ├── Invoke graph (with progress callback)
        ├── Stream output to terminal
        └── Return final result

No business logic here. Just plumbing between CLI and orchestrator.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from factory.orchestrator.checkpoint import CheckpointBackend
from factory.orchestrator.graph import build_factory_graph
from factory.orchestrator.state import FactoryState


# --- Types ---


class TaskAction(Enum):
    """Actions the bridge can perform on a task."""
    SUBMIT = "submit"
    RESUME = "resume"
    RETRY = "retry"
    CANCEL = "cancel"


@dataclass
class TaskRequest:
    """Request from CLI to factory."""
    description: str
    domain: str = "firmware"
    target_files: list[str] = field(default_factory=list)
    intent: str = "feature"         # feature | debug | review | docs | hardware | ...
    priority: str = "normal"        # low | normal | high | critical
    auto_approve: bool = False      # Skip human gate
    dry_run: bool = False           # Preview only, don't execute


@dataclass
class TaskEvent:
    """Event emitted during task execution (for UI updates)."""
    type: str               # "phase_start" | "phase_end" | "token" | "approval_needed" | "error" | "complete"
    node: str = ""          # Which node triggered this event
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class TaskResult:
    """Final result returned to CLI after task completes."""
    task_id: str
    status: str             # "completed" | "failed" | "cancelled" | "awaiting_approval"
    summary: str = ""
    modified_files: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    error: str = ""
    suggested_follow_ups: list[dict] = field(default_factory=list)
    persist_suggestion: dict | None = None


# --- Bridge ---


class FactoryBridge:
    """
    Bridge between CLI and the AI Factory.

    This is the ONLY public interface from CLI to factory internals.
    No CLI code should import from factory.orchestrator directly —
    everything goes through this bridge.
    """

    def __init__(self):
        self._checkpoint = CheckpointBackend()
        self._graph = None  # Lazy-built
        self._current_task_id: str | None = None
        self._cancelled: bool = False
        self._event_callback: Callable[[TaskEvent], None] | None = None

    def set_event_callback(self, callback: Callable[[TaskEvent], None]) -> None:
        """
        Register a callback for real-time task events.

        The CLI uses this to update progress, stream tokens, and
        show approval prompts without polling.
        """
        self._event_callback = callback

    def submit(self, request: TaskRequest) -> TaskResult:
        """
        Submit a new task to the factory.

        This is the main entry point. Flow:
        1. Generate task ID
        2. Map intent → task_type for classification
        3. Build initial state
        4. Invoke LangGraph (with event emission)
        5. Return structured result

        Args:
            request: Task request from CLI.

        Returns:
            TaskResult with status, files, cost, suggestions.
        """
        task_id = f"TASK-{uuid.uuid4().hex[:6].upper()}"
        self._current_task_id = task_id
        self._cancelled = False
        start_time = time.time()

        # Map CLI intent to factory task_type
        task_type = self._intent_to_task_type(request.intent)

        # Build initial state
        initial_state: FactoryState = {
            "task": {
                "task_id": task_id,
                "description": request.description,
                "domain": request.domain,
                "target_files": request.target_files,
                "priority": request.priority,
            },
            "status": "pending",
            "history": [],
        }

        # Emit start event
        self._emit(TaskEvent(type="phase_start", node="orchestrator", data={"task_id": task_id}))

        # Save initial checkpoint
        self._checkpoint.save(task_id, "start", initial_state)

        # Invoke graph
        try:
            graph = self._get_graph()
            final_state = graph.invoke(initial_state)

            # Mark complete
            self._checkpoint.complete(task_id)

            # Build result
            return self._build_result(task_id, final_state, start_time)

        except KeyboardInterrupt:
            # User cancelled (Ctrl+C during execution)
            self._checkpoint.fail(task_id)
            self._emit(TaskEvent(type="cancelled", node="", data={"task_id": task_id}))
            return TaskResult(
                task_id=task_id,
                status="cancelled",
                summary="Task cancelled by user.",
                duration_seconds=time.time() - start_time,
            )

        except Exception as e:
            # Unexpected failure
            self._checkpoint.fail(task_id)
            self._emit(TaskEvent(type="error", node="", data={"error": str(e)}))
            return TaskResult(
                task_id=task_id,
                status="failed",
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    def resume(self, task_id: str) -> TaskResult:
        """
        Resume a previously interrupted/failed task from checkpoint.

        Loads the last saved state and re-invokes the graph
        from that point forward.
        """
        start_time = time.time()
        checkpoint = self._checkpoint.get(task_id)

        if not checkpoint:
            return TaskResult(task_id=task_id, status="failed", error="No checkpoint found")

        if checkpoint.status not in ("in_progress", "failed"):
            return TaskResult(task_id=task_id, status="failed", error=f"Task is {checkpoint.status}, cannot resume")

        # Reset to in_progress
        self._checkpoint.save(task_id, checkpoint.node, checkpoint.state)
        self._current_task_id = task_id
        self._cancelled = False

        self._emit(TaskEvent(type="phase_start", node=checkpoint.node, data={"resumed": True}))

        try:
            graph = self._get_graph()
            final_state = graph.invoke(checkpoint.state)
            self._checkpoint.complete(task_id)
            return self._build_result(task_id, final_state, start_time)

        except Exception as e:
            self._checkpoint.fail(task_id)
            return TaskResult(task_id=task_id, status="failed", error=str(e), duration_seconds=time.time() - start_time)

    def retry(self, task_id: str) -> TaskResult:
        """
        Retry a failed task from the beginning with a fresh attempt.

        Increments the retry counter in state so the factory
        can escalate models on subsequent attempts.
        """
        checkpoint = self._checkpoint.get(task_id)
        if not checkpoint or checkpoint.status != "failed":
            return TaskResult(task_id=task_id, status="failed", error="Task not retryable")

        # Increment retry counter in state
        state = checkpoint.state
        retry_state = state.get("retry", {})
        retry_state["attempt"] = retry_state.get("attempt", 0) + 1
        retry_state["max_attempts"] = retry_state.get("max_attempts", 3)
        state["retry"] = retry_state
        state["status"] = "pending"

        # Reset checkpoint to in_progress
        self._checkpoint.save(task_id, "start", state)

        self._emit(TaskEvent(type="phase_start", node="orchestrator", data={"retry_attempt": retry_state["attempt"]}))

        return self.resume(task_id)

    def cancel(self, task_id: str) -> bool:
        """
        Cancel a running or pending task.

        If task is currently executing, sets cancel flag
        (checked by nodes between steps). Otherwise marks
        checkpoint as failed.
        """
        self._cancelled = True

        if self._current_task_id == task_id:
            # Currently running — will be caught by next event check
            self._emit(TaskEvent(type="cancelled", node="", data={"task_id": task_id}))
            return True

        # Not currently running — mark checkpoint
        checkpoint = self._checkpoint.get(task_id)
        if checkpoint and checkpoint.status == "in_progress":
            self._checkpoint.fail(task_id)
            return True

        return False

    def get_incomplete_tasks(self) -> list[dict]:
        """Get all tasks that can be resumed (crashed/failed)."""
        checkpoints = self._checkpoint.get_incomplete() + self._checkpoint.get_failed()
        return [
            {
                "task_id": cp.task_id,
                "node": cp.node,
                "status": cp.status,
                "description": cp.state.get("task", {}).get("description", ""),
                "updated_at": cp.updated_at,
            }
            for cp in checkpoints
        ]

    def approve(self, task_id: str) -> bool:
        """Approve a task waiting at human gate."""
        checkpoint = self._checkpoint.get(task_id)
        if not checkpoint:
            return False
        # Update state with approval
        state = checkpoint.state
        state["human_decision"] = {"approved": True, "reason": "approved via CLI"}
        self._checkpoint.save(task_id, "human_gate", state)
        return True

    def reject(self, task_id: str, reason: str = "") -> bool:
        """Reject a task waiting at human gate."""
        checkpoint = self._checkpoint.get(task_id)
        if not checkpoint:
            return False
        state = checkpoint.state
        state["human_decision"] = {"approved": False, "reason": reason or "rejected via CLI"}
        self._checkpoint.fail(task_id)
        return True

    # --- Internal ---

    def _get_graph(self):
        """Lazy-build the LangGraph."""
        if self._graph is None:
            self._graph = build_factory_graph()
        return self._graph

    def _emit(self, event: TaskEvent) -> None:
        """Emit an event to the registered callback."""
        if self._event_callback:
            self._event_callback(event)

    def _build_result(self, task_id: str, state: dict, start_time: float) -> TaskResult:
        """Convert final LangGraph state into TaskResult for CLI."""
        execution = state.get("execution", {})
        return TaskResult(
            task_id=task_id,
            status=state.get("status", "completed"),
            summary=execution.get("output", ""),
            modified_files=execution.get("modified_files", []),
            cost_usd=execution.get("token_usage", {}).get("cost_usd", 0.0),
            duration_seconds=time.time() - start_time,
            error=state.get("error", ""),
            suggested_follow_ups=state.get("suggested_follow_ups", []),
            persist_suggestion=state.get("persist_suggestion"),
        )

    @staticmethod
    def _intent_to_task_type(intent: str) -> str:
        """Map CLI intent to factory task_type."""
        mapping = {
            "feature": "coding",
            "debug": "debugging",
            "review": "review",
            "docs": "documentation",
            "hardware": "documentation",
            "research": "research",
            "telemetry": "data_telemetry",
            "mobile": "coding",
            "refactor": "refactoring",
            "test": "coding",
            "chat": "documentation",
        }
        return mapping.get(intent, "coding")
