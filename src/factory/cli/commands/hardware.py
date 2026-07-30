"""raceos hardware — hardware design, wiring, BOM questions."""

from __future__ import annotations
import typer
from rich.console import Console
from factory.cli.bridge import FactoryBridge, TaskRequest
from factory.cli.output.agent_viz import AgentViz
from factory.cli.output.theme import THEME
from factory.cli.resume import _display_result


def run_hardware(
    description: str = typer.Argument(..., help="Hardware question or task"),
    files: list[str] = typer.Option([], "--file", "-f"),
):
    """Hardware design, wiring diagrams, BOM, and pinout questions."""
    console = Console(theme=THEME)
    bridge = FactoryBridge()
    request = TaskRequest(description=description, domain="hardware", intent="hardware", target_files=files)
    viz = AgentViz(console)
    bridge.set_event_callback(viz.on_event)
    console.print(f"\n[bold]Hardware:[/bold] {description}\n")
    viz.start(task_id="...", description=description[:50])
    try:
        result = bridge.submit(request)
    except KeyboardInterrupt:
        viz.stop(); return
    finally:
        viz.stop()
    _display_result(result, console)
