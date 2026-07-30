"""
Session Manager.

Manages the lifecycle of a CLI session:
    - Start (create or resume)
    - Track commands
    - Track pending tasks
    - End (save state)

Also handles crash recovery: detects incomplete sessions on startup.
"""

from __future__ import annotations

import structlog

from .state import SessionState

log = structlog.get_logger()


class SessionManager:
    """
    Manages CLI session lifecycle.

    A session starts when the shell launches and ends when
    the user exits. State is persisted between commands so
    that the shell can resume after a crash.
    """

    def __init__(self):
        self._state: SessionState | None = None

    def start(self) -> None:
        """
        Start or resume a session.

        Checks for an existing active session (crash recovery).
        If found, resumes it. Otherwise creates new.
        """
        # Try to resume existing active session
        existing = SessionState.load_latest()
        if existing and existing.status == "active":
            self._state = existing
            log.info("session.resumed", session_id=existing.id)
        else:
            self._state = SessionState.create_new()
            self._state.save()
            log.info("session.created", session_id=self._state.id)

    def end(self) -> None:
        """End the current session and persist final state."""
        if self._state:
            self._state.end()
            log.info("session.ended", session_id=self._state.id)

    def record_command(self, cmd: str) -> None:
        """Record a command executed in this session."""
        if self._state:
            self._state.add_command(cmd)
            self._state.save()

    @property
    def session_id(self) -> str:
        """Current session ID."""
        return self._state.id if self._state else ""

    @property
    def pending_count(self) -> int:
        """Number of tasks awaiting approval."""
        if self._state:
            return len(self._state.pending_approvals)
        return 0

    @property
    def command_count(self) -> int:
        """Number of commands executed in this session."""
        if self._state:
            return len(self._state.commands)
        return 0

    def add_pending_approval(self, task_id: str) -> None:
        """Register a task as awaiting human approval."""
        if self._state:
            self._state.pending_approvals.append(task_id)
            self._state.save()

    def remove_pending_approval(self, task_id: str) -> None:
        """Remove a task from pending (approved or rejected)."""
        if self._state and task_id in self._state.pending_approvals:
            self._state.pending_approvals.remove(task_id)
            self._state.save()
