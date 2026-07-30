"""
Agent Activity Visualization.

Real-time display of which agents are active, what they're doing,
and how the task flows through the pipeline.

Shows:
    - Current active agent (highlighted)
    - Agent chain (completed → active → pending)
    - Per-agent status, duration, cost
    - Live updating during execution

Usage:
    viz = AgentViz(console)
    viz.on_event(TaskEvent(type="phase_start", node="orchestrator"))
    viz.on_event(TaskEvent(type="phase_end", node="orchestrator"))
    viz.render()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .theme import ICONS


# Agent display names and descriptions
AGENT_INFO = {
    "orchestrator": ("🎯 Orchestrator", "Classify + route"),
    "context": ("📚 Context", "Load Brain + specs"),
    "planner": ("📋 Planner", "Generate spec"),
    "human_gate": ("👤 Human", "Await approval"),
    "research": ("🔍 Research", "Gather evidence"),
    "product": ("📦 Product", "Define scope"),
    "architect": ("🏗️ Architect", "Design system"),
    "hardware": ("🔌 Hardware", "Hardware design"),
    "engineer": ("⚙️ Engineer", "Write code"),
    "data_telemetry": ("📊 Telemetry", "Data pipeline"),
    "reviewer": ("👁️ Reviewer", "Check code"),
    "validator": ("✓ Validator", "Run tests"),
    "knowledge": ("🧠 Knowledge", "Learn + index"),
}


@dataclass
class AgentState:
    """State of a single agent in the visualization."""
    name: str
    display_name: str
    description: str
    status: str = "pending"     # pending | active | done | failed | skipped
    started_at: float = 0.0
    duration: float = 0.0
    cost: float = 0.0
    model: str = ""
    message: str = ""           # What it's currently doing


class AgentViz:
    """
    Real-time agent activity visualization.

    Maintains state of all agents and renders a live-updating
    panel showing the pipeline flow.
    """

    def __init__(self, console: Console):
        self.console = console
        self.agents: list[AgentState] = []
        self._live: Live | None = None
        self._task_id: str = ""
        self._task_desc: str = ""
        self._start_time: float = 0.0
        self._total_cost: float = 0.0

    def start(self, task_id: str, description: str = "") -> None:
        """Initialize visualization for a new task."""
        self._task_id = task_id
        self._task_desc = description
        self._start_time = time.time()
        self._total_cost = 0.0
        self.agents = []

        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.start()

    def on_event(self, event) -> None:
        """
        Handle a TaskEvent and update visualization.

        Event types:
            phase_start → mark agent as active
            phase_end → mark agent as done
            token → update active agent's message
            error → mark agent as failed
            approval_needed → mark human_gate as active
        """
        if event.type == "phase_start":
            self._activate_agent(event.node, event.data)

        elif event.type == "phase_end":
            self._complete_agent(event.node, event.data)

        elif event.type == "token":
            self._update_message(event.data.get("content", ""))

        elif event.type == "error":
            self._fail_agent(event.node, event.data.get("error", ""))

        elif event.type == "approval_needed":
            self._activate_agent("human_gate", {"message": "Awaiting your approval..."})

        elif event.type == "cancelled":
            self._cancel_current()

        # Update live display
        if self._live:
            self._live.update(self._render())

    def stop(self) -> None:
        """Stop the live visualization."""
        if self._live:
            self._live.stop()
            self._live = None

    # --- Internal State Management ---

    def _activate_agent(self, node: str, data: dict) -> None:
        """Mark an agent as active."""
        info = AGENT_INFO.get(node, (f"⚡ {node}", ""))
        agent = AgentState(
            name=node,
            display_name=info[0],
            description=info[1],
            status="active",
            started_at=time.time(),
            model=data.get("model", ""),
            message=data.get("message", "working..."),
        )
        # Replace existing or append
        existing = next((a for a in self.agents if a.name == node), None)
        if existing:
            existing.status = "active"
            existing.started_at = time.time()
            existing.message = data.get("message", "working...")
        else:
            self.agents.append(agent)

    def _complete_agent(self, node: str, data: dict) -> None:
        """Mark an agent as completed."""
        for agent in self.agents:
            if agent.name == node:
                agent.status = "done"
                agent.duration = time.time() - agent.started_at
                agent.cost = data.get("cost", 0.0)
                agent.model = data.get("model", agent.model)
                agent.message = data.get("summary", "done")
                self._total_cost += agent.cost
                break

    def _fail_agent(self, node: str, error: str) -> None:
        """Mark an agent as failed."""
        for agent in self.agents:
            if agent.name == node:
                agent.status = "failed"
                agent.duration = time.time() - agent.started_at
                agent.message = error[:60]
                break

    def _update_message(self, content: str) -> None:
        """Update the active agent's current message."""
        for agent in self.agents:
            if agent.status == "active":
                agent.message = content[:50]
                break

    def _cancel_current(self) -> None:
        """Mark all active agents as failed (cancelled)."""
        for agent in self.agents:
            if agent.status == "active":
                agent.status = "failed"
                agent.message = "cancelled"

    # --- Rendering ---

    def _render(self) -> Panel:
        """Render the current visualization state."""
        lines: list[str] = []

        for agent in self.agents:
            icon = self._status_icon(agent.status)
            name = agent.display_name

            if agent.status == "active":
                elapsed = time.time() - agent.started_at
                line = f"  {icon} [bold yellow]{name}[/bold yellow]  [dim]{agent.message}[/dim]  [{elapsed:.1f}s]"
            elif agent.status == "done":
                cost_str = f"${agent.cost:.4f}" if agent.cost > 0 else ""
                model_str = f"[blue]{agent.model}[/blue]" if agent.model else ""
                line = f"  {icon} [green]{name}[/green]  {agent.duration:.1f}s  {model_str}  [green]{cost_str}[/green]"
            elif agent.status == "failed":
                line = f"  {icon} [red]{name}[/red]  [dim]{agent.message}[/dim]"
            else:
                line = f"  {icon} [dim]{name}[/dim]"

            lines.append(line)

        # Progress bar
        total = len(self.agents) or 1
        done = sum(1 for a in self.agents if a.status == "done")
        pct = (done / total) * 100 if total > 0 else 0
        bar_width = 40
        filled = int(bar_width * pct / 100)
        bar = "━" * filled + "─" * (bar_width - filled)
        lines.append(f"\n  {bar}  {pct:.0f}%")

        # Footer
        elapsed = time.time() - self._start_time if self._start_time else 0
        lines.append(f"  [dim]Elapsed: {elapsed:.1f}s │ Cost: ${self._total_cost:.4f}[/dim]")

        content = "\n".join(lines)
        return Panel(
            content,
            title=f"[bold cyan]{self._task_id}[/bold cyan]",
            subtitle=self._task_desc[:60] if self._task_desc else None,
            border_style="cyan",
            padding=(1, 2),
        )

    @staticmethod
    def _status_icon(status: str) -> str:
        return ICONS.get(status, "○")
