"""
raceos firmware — firmware implementation and debugging.

Shortcut for firmware-domain tasks. Automatically sets domain=firmware.
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from factory.cli.bridge import FactoryBridge, TaskRequest
from factory.cli.output.agent_viz import AgentViz
from factory.cli.output.theme import THEME
from factory.cli.resume import _display_result


def run_firmware(
    description: str = typer.Argument(..., help="What to do (implement/fix/debug)"),
    files: list[str] = typer.Option([], "--file", "-f", help="Target files"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Skip human gate"),
):
    """Firmware implementation, debugging, and fixes."""
    console = Console(theme=THEME)
    bridge = FactoryBridge()

    # Detect intent from description keywords
    desc_lower = description.lower()
    intent = "feature"
    if any(kw in desc_lower for kw in ("fix", "bug", "why", "debug", "broken")):
        intent = "debug"

    request = TaskRequest(
        description=description,
        domain="firmware",
        target_files=files,
        intent=intent,
        auto_approve=auto_approve,
    )

    viz = AgentViz(console)
    bridge.set_event_callback(viz.on_event)

    console.print(f"\n[bold]Firmware ({intent}):[/bold] {description}\n")
    viz.start(task_id="...", description=description[:50])

    try:
        result = bridge.submit(request)
    except KeyboardInterrupt:
        viz.stop()
        console.print("\n[yellow]Cancelled.[/yellow]")
        return
    finally:
        viz.stop()

    _display_result(result, console)
