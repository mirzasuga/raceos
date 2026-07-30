"""
Progress Indicators.

Phase-based progress display for factory task execution.
Shows each node in the pipeline with status icons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .theme import ICONS


@dataclass
class Phase:
    """A single phase in task execution."""

    name: str
    status: str = "pending"     # pending | running | done | failed | paused
    duration: float = 0.0
    cost: float = 0.0
    model: str = ""
    started_at: float = 0.0


@dataclass
class TaskProgress:
    """Tracks progress across all phases of a task."""

    task_id: str
    description: str = ""
    phases: list[Phase] = field(default_factory=list)
    total_cost: float = 0.0
    started_at: float = field(default_factory=time)

    @classmethod
    def for_full_pipeline(cls, task_id: str, description: str = "") -> "TaskProgress":
        """Create progress tracker with all standard phases."""
        return cls(
            task_id=task_id,
            description=description,
            phases=[
                Phase(name="classify"),
                Phase(name="context"),
                Phase(name="plan"),
                Phase(name="approve"),
                Phase(name="execute"),
                Phase(name="review"),
                Phase(name="validate"),
                Phase(name="learn"),
            ],
        )

    @classmethod
    def for_simple_pipeline(cls, task_id: str, description: str = "") -> "TaskProgress":
        """Create progress tracker for simple tasks (no plan/approve)."""
        return cls(
            task_id=task_id,
            description=description,
            phases=[
                Phase(name="classify"),
                Phase(name="context"),
                Phase(name="execute"),
                Phase(name="review"),
                Phase(name="validate"),
                Phase(name="learn"),
            ],
        )

    def start_phase(self, name: str) -> None:
        """Mark a phase as running."""
        for phase in self.phases:
            if phase.name == name:
                phase.status = "running"
                phase.started_at = time()
                break

    def complete_phase(self, name: str, cost: float = 0.0, model: str = "") -> None:
        """Mark a phase as completed."""
        for phase in self.phases:
            if phase.name == name:
                phase.status = "done"
                phase.duration = time() - phase.started_at if phase.started_at else 0.0
                phase.cost = cost
                phase.model = model
                self.total_cost += cost
                break

    def fail_phase(self, name: str) -> None:
        """Mark a phase as failed."""
        for phase in self.phases:
            if phase.name == name:
                phase.status = "failed"
                phase.duration = time() - phase.started_at if phase.started_at else 0.0
                break

    @property
    def elapsed(self) -> float:
        """Total elapsed time since start."""
        return time() - self.started_at

    @property
    def completed_count(self) -> int:
        """Number of completed phases."""
        return sum(1 for p in self.phases if p.status == "done")

    @property
    def progress_pct(self) -> float:
        """Completion percentage."""
        if not self.phases:
            return 0.0
        return (self.completed_count / len(self.phases)) * 100

    def render(self, console: Console) -> None:
        """Render progress panel to console."""
        lines: list[str] = []

        for phase in self.phases:
            icon = ICONS.get(phase.status, "○")
            line = f"  {icon} {phase.name:<12}"

            if phase.status == "done":
                line += f" {phase.duration:.1f}s"
                if phase.model:
                    line += f"   [blue]{phase.model}[/blue]"
                if phase.cost > 0:
                    line += f"   [green]${phase.cost:.4f}[/green]"
            elif phase.status == "running":
                line += " [yellow]...[/yellow]"

            lines.append(line)

        # Progress bar
        pct = self.progress_pct
        bar_width = 40
        filled = int(bar_width * pct / 100)
        bar = "━" * filled + "─" * (bar_width - filled)
        lines.append(f"\n  {bar}  {pct:.0f}%")
        lines.append(f"  [dim]Elapsed: {self.elapsed:.1f}s │ Cost: ${self.total_cost:.4f}[/dim]")

        content = "\n".join(lines)
        console.print(Panel(
            content,
            title=f"[bold]{self.task_id}[/bold]",
            subtitle=self.description[:50] if self.description else None,
            border_style="cyan",
        ))
