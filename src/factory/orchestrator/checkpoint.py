"""
LangGraph Checkpoint Backend.

Persists workflow state after each node execution so that
if the process crashes, the task can resume from the last
completed node instead of starting over.

Storage: SQLite (single file, no server, ACID-compliant).

Lifecycle:
    1. Task starts → create checkpoint record
    2. After each node → update checkpoint with new state
    3. Task completes → mark checkpoint as done
    4. On restart → check for incomplete checkpoints → resume

Usage:
    from factory.orchestrator.checkpoint import CheckpointBackend

    # Build graph with checkpointing
    backend = CheckpointBackend()
    graph = build_factory_graph(checkpointer=backend)

    # Resume crashed task
    incomplete = backend.get_incomplete()
    for task_id, state in incomplete:
        graph.invoke(state)  # Resumes from last checkpoint
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DB_PATH = "./data/checkpoints.db"


@dataclass
class Checkpoint:
    """A persisted workflow state snapshot."""

    task_id: str
    node: str               # Last completed node
    state: dict             # Full FactoryState at this point
    status: str             # "in_progress" | "completed" | "failed"
    created_at: float
    updated_at: float


class CheckpointBackend:
    """
    SQLite-backed checkpoint storage for LangGraph.

    After each node completes, the orchestrator calls save()
    with the current state. If the process crashes, get_incomplete()
    returns all tasks that were in-progress, ready to resume.

    Thread-safety: SQLite handles this via WAL mode.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create the checkpoints table if it doesn't exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    task_id TEXT PRIMARY KEY,
                    node TEXT NOT NULL,
                    state TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'in_progress',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON checkpoints(status)
            """)

    def save(self, task_id: str, node: str, state: dict) -> None:
        """
        Save or update a checkpoint after a node completes.

        Called by the orchestrator after each successful node execution.
        Uses UPSERT (INSERT OR REPLACE) for idempotency.

        Args:
            task_id: Unique task identifier.
            node: Name of the last completed node.
            state: Full FactoryState dict (JSON-serializable).
        """
        now = time.time()
        state_json = json.dumps(state, default=str)

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO checkpoints (task_id, node, state, status, created_at, updated_at)
                VALUES (?, ?, ?, 'in_progress', ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    node = excluded.node,
                    state = excluded.state,
                    updated_at = excluded.updated_at
            """, (task_id, node, state_json, now, now))

    def complete(self, task_id: str) -> None:
        """Mark a task as completed (no longer resumable)."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE checkpoints SET status = 'completed', updated_at = ?
                WHERE task_id = ?
            """, (time.time(), task_id))

    def fail(self, task_id: str) -> None:
        """Mark a task as failed (can be retried manually)."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE checkpoints SET status = 'failed', updated_at = ?
                WHERE task_id = ?
            """, (time.time(), task_id))

    def get(self, task_id: str) -> Checkpoint | None:
        """Retrieve a specific checkpoint."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE task_id = ?", (task_id,)
            ).fetchone()

        if row is None:
            return None

        return self._row_to_checkpoint(row)

    def get_incomplete(self) -> list[Checkpoint]:
        """
        Get all incomplete (in-progress) checkpoints.

        Called on startup to detect crashed tasks that need resuming.

        Returns:
            List of Checkpoint objects for tasks that didn't finish.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE status = 'in_progress' ORDER BY updated_at DESC"
            ).fetchall()

        return [self._row_to_checkpoint(row) for row in rows]

    def get_failed(self) -> list[Checkpoint]:
        """
        Get all failed checkpoints (dead letter queue).

        Failed tasks are retained for:
        - Post-mortem debugging (what went wrong?)
        - Manual retry with different parameters
        - Pattern detection (same task failing repeatedly?)

        Tasks stay in failed state until:
        - Human manually retries: factory retry TASK-ID
        - Human dismisses: factory dismiss TASK-ID
        - Auto-cleanup after 24h (configurable via cleanup_old)
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE status = 'failed' ORDER BY updated_at DESC"
            ).fetchall()

        return [self._row_to_checkpoint(row) for row in rows]

    def retry_failed(self, task_id: str) -> bool:
        """
        Move a failed task back to in_progress for retry.

        Called when human runs: factory retry TASK-ID
        The orchestrator will resume from the last checkpoint.

        Returns True if task was found and reset.
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE checkpoints SET status = 'in_progress', updated_at = ?
                WHERE task_id = ? AND status = 'failed'
            """, (time.time(), task_id))
            return cursor.rowcount > 0

    def dismiss_failed(self, task_id: str) -> bool:
        """
        Dismiss a failed task (human acknowledges the failure).

        Moves to 'dismissed' status. Will be cleaned up by cleanup_old().
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE checkpoints SET status = 'dismissed', updated_at = ?
                WHERE task_id = ? AND status = 'failed'
            """, (time.time(), task_id))
            return cursor.rowcount > 0

    def delete(self, task_id: str) -> None:
        """Remove a checkpoint (after successful completion or manual cleanup)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM checkpoints WHERE task_id = ?", (task_id,))

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        """
        Remove completed/failed checkpoints older than max_age_hours.

        Returns number of records removed.
        """
        cutoff = time.time() - (max_age_hours * 3600)
        with self._connect() as conn:
            cursor = conn.execute("""
                DELETE FROM checkpoints
                WHERE status IN ('completed', 'failed')
                AND updated_at < ?
            """, (cutoff,))
            return cursor.rowcount

    @property
    def stats(self) -> dict[str, int]:
        """Get checkpoint statistics."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT status, COUNT(*) FROM checkpoints GROUP BY status
            """).fetchall()

        stats = {"in_progress": 0, "completed": 0, "failed": 0}
        for status, count in rows:
            stats[status] = count
        return stats

    # --- Internal ---

    def _connect(self) -> sqlite3.Connection:
        """Create a connection with WAL mode for better concurrency."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_checkpoint(row: sqlite3.Row) -> Checkpoint:
        """Convert a database row to a Checkpoint object."""
        return Checkpoint(
            task_id=row["task_id"],
            node=row["node"],
            state=json.loads(row["state"]),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
