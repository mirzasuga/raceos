"""
RaceOS CLI — Application Entry Point.

The root Typer app that handles:
    - Global options (--verbose, --no-color, --config)
    - Subcommand registration
    - Default behavior (no args → interactive shell)
    - Version display

Usage:
    raceos                     # Interactive shell
    raceos --help              # Show help
    raceos --version           # Show version
    raceos feature "..."       # Direct command
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

import factory
from factory.cli.output.theme import THEME

# --- App Instance ---

app = typer.Typer(
    name="raceos",
    help="RaceOS AI Software Factory — build motorsport software with AI.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    add_completion=True,
)

console = Console(theme=THEME)


# --- Global State ---

class AppState:
    """Global CLI state, shared across commands."""

    verbose: bool = False
    config_path: str = "config/factory.yaml"
    no_color: bool = False
    session_id: str = ""


state = AppState()


# --- Global Options (callback) ---

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug output"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color output"),
    config: str = typer.Option("config/factory.yaml", "--config", "-c", help="Config file path"),
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit"),
):
    """
    RaceOS AI Software Factory.

    Run without arguments to enter interactive shell.
    Run with a command for single-shot execution.
    """
    state.verbose = verbose
    state.no_color = no_color
    state.config_path = config

    if no_color:
        console.no_color = True

    if version:
        console.print(f"raceos {factory.__version__}")
        raise typer.Exit()

    # No subcommand → launch interactive shell
    if ctx.invoked_subcommand is None:
        from factory.cli.shell import run_shell
        run_shell(state)


# --- Register Commands ---
# Each command is a separate file in cli/commands/
# They are registered here to keep app.py thin.

@app.command()
def doctor():
    """Check system health and dependencies."""
    from factory.cli.commands.doctor import run_doctor
    run_doctor(console)


@app.command()
def status():
    """Show active tasks, budget, and pending approvals."""
    from factory.cli.commands.status import run_status
    run_status(console)


@app.command()
def feature(
    description: str = typer.Argument(..., help="Feature description"),
    domain: str = typer.Option("firmware", "--domain", "-d"),
    file: list[str] = typer.Option([], "--file", "-f"),
    auto_approve: bool = typer.Option(False, "--auto-approve"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    priority: str = typer.Option("normal", "--priority", "-p"),
):
    """Implement a feature end-to-end via the AI Factory."""
    from factory.cli.commands.feature import run_feature
    run_feature(description, domain, file, auto_approve, dry_run, priority)


@app.command()
def firmware(
    description: str = typer.Argument(..., help="Firmware task"),
    file: list[str] = typer.Option([], "--file", "-f"),
    auto_approve: bool = typer.Option(False, "--auto-approve"),
):
    """Firmware implementation and debugging."""
    from factory.cli.commands.firmware import run_firmware
    run_firmware(description, file, auto_approve)


@app.command()
def hardware(description: str = typer.Argument(...), file: list[str] = typer.Option([], "--file", "-f")):
    """Hardware design, wiring, BOM questions."""
    from factory.cli.commands.hardware import run_hardware
    run_hardware(description, file)


@app.command()
def mobile(description: str = typer.Argument(...), file: list[str] = typer.Option([], "--file", "-f")):
    """Mobile (React Native) implementation."""
    from factory.cli.commands.domains import run_mobile
    run_mobile(description, file)


@app.command()
def docs(description: str = typer.Argument(...)):
    """Generate or update documentation."""
    from factory.cli.commands.domains import run_docs
    run_docs(description)


@app.command()
def review(description: str = typer.Argument("review latest changes")):
    """Review code changes."""
    from factory.cli.commands.domains import run_review
    run_review(description)


@app.command()
def research(description: str = typer.Argument(...)):
    """Market or user research tasks."""
    from factory.cli.commands.domains import run_research
    run_research(description)


@app.command()
def telemetry(description: str = typer.Argument(...)):
    """Data pipeline and telemetry design."""
    from factory.cli.commands.domains import run_telemetry
    run_telemetry(description)


@app.command("config")
def config_cmd(
    action: str = typer.Argument("list", help="get|set|list|reset"),
    key: Optional[str] = typer.Argument(None, help="Config key"),
    value: Optional[str] = typer.Argument(None, help="Config value (for set)"),
):
    """Manage configuration."""
    from factory.cli.config.manager import handle_config
    handle_config(action, key, value, console)


@app.command()
def install(
    all_deps: bool = typer.Option(False, "--all", "-a", help="Install all"),
    check_only: bool = typer.Option(False, "--check", help="Check only"),
):
    """Install optional dependencies."""
    from factory.cli.commands.install import run_install
    run_install(all_deps, check_only)


@app.command("self-test")
def selftest():
    """Verify the full pipeline works end-to-end."""
    from factory.cli.commands.selftest import run_selftest
    run_selftest()


@app.command()
def demo():
    """Show factory capabilities (no API key needed)."""
    from factory.cli.commands.selftest import run_demo
    run_demo()


@app.command()
def update(
    check_only: bool = typer.Option(False, "--check", help="Check only"),
    force: bool = typer.Option(False, "--force", help="Force reinstall"),
):
    """Check for updates and upgrade."""
    from factory.cli.commands.install import run_update
    run_update(check_only, force)


@app.command()
def logs(
    tail: int = typer.Option(20, "--tail", "-n", help="Number of lines"),
    level: str = typer.Option("info", "--level", "-l", help="Minimum log level"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Filter by task ID"),
):
    """View factory logs."""
    from factory.cli.commands.logs import run_logs
    run_logs(tail=tail, level=level, task_id=task, console=console)


# --- Entry Point ---

def run():
    """Entry point for `raceos` command (called by pyproject.toml scripts)."""
    app()


if __name__ == "__main__":
    run()
