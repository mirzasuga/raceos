"""
raceos feature — implement a feature via full pipeline.

This is the primary command for code implementation.
Routes through: classify → context → plan → approve → execute → review → validate → learn
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from factory.cli.bridge import FactoryBridge, TaskRequest
from factory.cli.output.agent_viz import AgentViz
from factory.cli.output.theme import THEME
from factory.cli.resume import _display_result


def run_feature(
    description: str = typer.Argument(..., help="What to implement"),
    domain: str = typer.Option("firmware", "--domain", "-d", help="Target domain"),
    files: list[str] = typer.Option([], "--file", "-f", help="Target files"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Skip human gate"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only"),
    priority: str = typer.Option("normal", "--priority", "-p", help="Task priority"),
):
    """Implement a feature end-to-end via the AI Factory."""
    console = Console(theme=THEME)
    bridge = FactoryBridge()

    request = TaskRequest(
        description=description,
        domain=domain,
        target_files=files,
        intent="feature",
        priority=priority,
        auto_approve=auto_approve,
        dry_run=dry_run,
    )

    # Agent visualization
    viz = AgentViz(console)
    bridge.set_event_callback(viz.on_event)

    console.print(f"\n[bold]Feature:[/bold] {description}")
    console.print(f"[dim]Domain: {domain} │ Priority: {priority} │ Dry-run: {dry_run}[/dim]\n")

    viz.start(task_id="...", description=description[:50])

    try:
        result = bridge.submit(request)
    except KeyboardInterrupt:
        viz.stop()
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return
    finally:
        viz.stop()

    _display_result(result, console)
