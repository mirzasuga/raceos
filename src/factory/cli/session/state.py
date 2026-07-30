"""
Session State Model.

Persisted state for a CLI session. Survives shell restarts.
Stored as JSON in data/sessions/<session_id>.json.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


SESSIONS_DIR = Path("data/sessions")


@dataclass
class SessionState:
    """Persistent session state."""

    id: str = ""
    started_at: float = 0.0
    status: str = "active"          # active | suspended | ended
    commands: list[str] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    pending_approvals: list[str] = field(default_factory=list)

    @classmethod
    def create_new(cls) -> "SessionState":
        """Create a fresh session."""
        return cls(
            id=f"sess-{uuid.uuid4().hex[:8]}",
            started_at=time.time(),
            status="active",
        )

    @classmethod
    def load(cls, session_id: str) -> "SessionState | None":
        """Load a session from disk."""
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return cls(**data)

    @classmethod
    def load_latest(cls) -> "SessionState | None":
        """Load the most recent active session."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        sessions = sorted(SESSIONS_DIR.glob("sess-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in sessions:
            data = json.loads(path.read_text())
            if data.get("status") == "active":
                return cls(**data)
        return None

    def save(self) -> None:
        """Persist session to disk."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{self.id}.json"
        path.write_text(json.dumps(self.__dict__, default=str, indent=2))

    def add_command(self, cmd: str) -> None:
        """Record a command in history."""
        self.commands.append(cmd)
        if len(self.commands) > 500:
            self.commands = self.commands[-500:]

    def end(self) -> None:
        """Mark session as ended."""
        self.status = "ended"
        self.save()
