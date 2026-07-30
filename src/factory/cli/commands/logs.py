"""raceos logs — view factory logs."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console


LOG_FILE = Path("data/logs/raceos.log")


def run_logs(tail: int = 20, level: str = "info", task_id: str | None = None, console: Console | None = None) -> None:
    """Display recent log entries."""
    if console is None:
        console = Console()

    if not LOG_FILE.exists():
        console.print("[dim]No log file found. Logs will appear after first task execution.[/dim]")
        return

    lines = LOG_FILE.read_text().splitlines()

    # Filter by level
    level_upper = level.upper()
    if level_upper != "DEBUG":
        lines = [l for l in lines if level_upper in l.upper() or "ERROR" in l.upper() or "WARN" in l.upper()]

    # Filter by task ID
    if task_id:
        lines = [l for l in lines if task_id in l]

    # Tail
    lines = lines[-tail:]

    if not lines:
        console.print(f"[dim]No logs matching filters (level={level}, task={task_id or 'all'})[/dim]")
        return

    for line in lines:
        # Colorize by level
        if "ERROR" in line:
            console.print(f"[red]{line}[/red]")
        elif "WARN" in line:
            console.print(f"[yellow]{line}[/yellow]")
        else:
            console.print(f"[dim]{line}[/dim]")
