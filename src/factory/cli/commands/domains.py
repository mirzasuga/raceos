"""Domain command stubs — all route through FactoryBridge."""

from __future__ import annotations
import typer
from rich.console import Console
from factory.cli.bridge import FactoryBridge, TaskRequest
from factory.cli.output.agent_viz import AgentViz
from factory.cli.output.theme import THEME
from factory.cli.resume import _display_result


def _run_domain(description: str, domain: str, intent: str, files: list[str] = None):
    """Generic domain command executor."""
    console = Console(theme=THEME)
    bridge = FactoryBridge()
    request = TaskRequest(description=description, domain=domain, intent=intent, target_files=files or [])
    viz = AgentViz(console)
    bridge.set_event_callback(viz.on_event)
    console.print(f"\n[bold]{intent.title()}:[/bold] {description}\n")
    viz.start(task_id="...", description=description[:50])
    try:
        result = bridge.submit(request)
    except KeyboardInterrupt:
        viz.stop(); return
    finally:
        viz.stop()
    _display_result(result, console)


def run_mobile(description: str = typer.Argument(...), files: list[str] = typer.Option([], "--file", "-f")):
    """Mobile (React Native) implementation."""
    _run_domain(description, "mobile", "mobile", files)


def run_docs(description: str = typer.Argument(...)):
    """Generate or update documentation."""
    _run_domain(description, "firmware", "docs")


def run_review(description: str = typer.Argument("review latest changes")):
    """Review code changes."""
    _run_domain(description, "firmware", "review")


def run_research(description: str = typer.Argument(...)):
    """Market or user research tasks."""
    _run_domain(description, "firmware", "research")


def run_telemetry(description: str = typer.Argument(...)):
    """Data pipeline and telemetry design."""
    _run_domain(description, "firmware", "telemetry")
