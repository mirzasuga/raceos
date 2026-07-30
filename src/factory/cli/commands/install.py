"""
raceos install — install optional dependencies.
raceos update — check for and apply updates.

These commands manage the factory's optional tooling
and keep the package up to date.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from factory.cli.output.theme import THEME

console = Console(theme=THEME)


# --- raceos install ---

OPTIONAL_DEPS = [
    {
        "name": "opencode",
        "check": "opencode",
        "install_cmd": ["npm", "install", "-g", "opencode"],
        "description": "AI coding agent (executor)",
    },
    {
        "name": "platformio",
        "check": "pio",
        "install_cmd": [sys.executable, "-m", "pip", "install", "platformio"],
        "description": "Firmware build/test (PlatformIO)",
    },
    {
        "name": "node",
        "check": "node",
        "install_cmd": None,  # Can't auto-install — must use system package manager
        "description": "Node.js (for MCP servers via npx)",
    },
]


def run_install(
    all_deps: bool = typer.Option(False, "--all", "-a", help="Install all optional deps"),
    check_only: bool = typer.Option(False, "--check", help="Only check, don't install"),
):
    """Install optional dependencies for full factory functionality."""
    console.print("\n[bold]Optional Dependencies[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Description", style="dim")
    table.add_column("Install Command", style="dim")

    missing: list[dict] = []

    for dep in OPTIONAL_DEPS:
        installed = shutil.which(dep["check"]) is not None
        status = "[green]✅ installed[/green]" if installed else "[yellow]❌ missing[/yellow]"
        cmd_str = " ".join(dep["install_cmd"]) if dep["install_cmd"] else "(manual)"

        table.add_row(dep["name"], status, dep["description"], cmd_str if not installed else "—")

        if not installed:
            missing.append(dep)

    console.print(table)

    if not missing:
        console.print("\n[green]✅ All optional dependencies installed.[/green]\n")
        return

    if check_only:
        console.print(f"\n[yellow]{len(missing)} missing. Run 'raceos install --all' to install.[/yellow]\n")
        return

    # Install missing deps
    if not all_deps:
        console.print(f"\n[yellow]{len(missing)} missing.[/yellow]")
        console.print("Install all? [Y/n]: ", end="")
        try:
            answer = input().strip().lower()
            if answer and answer != "y":
                return
        except (EOFError, KeyboardInterrupt):
            return

    for dep in missing:
        if dep["install_cmd"] is None:
            console.print(f"  ⚠️  {dep['name']}: install manually via system package manager")
            continue

        console.print(f"  Installing {dep['name']}...", end=" ")
        try:
            result = subprocess.run(
                dep["install_cmd"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                console.print("[green]✅[/green]")
            else:
                console.print(f"[red]❌[/red] {result.stderr[:100]}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            console.print(f"[red]❌ {e}[/red]")

    console.print("\n[dim]Run 'raceos doctor' to verify.[/dim]\n")


# --- raceos update ---


def run_update(
    check_only: bool = typer.Option(False, "--check", help="Only check, don't update"),
    force: bool = typer.Option(False, "--force", help="Force update even if current"),
):
    """Check for updates and upgrade raceos-factory."""
    import factory

    current = factory.__version__
    console.print(f"\n[bold]RaceOS Factory Update[/bold]")
    console.print(f"  Current version: [cyan]{current}[/cyan]\n")

    # Check PyPI for latest
    console.print("  Checking PyPI for updates...", end=" ")
    latest = _check_pypi_version()

    if latest is None:
        console.print("[yellow]unable to check (network error)[/yellow]\n")
        return

    console.print(f"[green]{latest}[/green]")

    if latest == current and not force:
        console.print("\n[green]✅ Already on latest version.[/green]\n")
        return

    if _version_lt(current, latest):
        console.print(f"\n  [yellow]Update available: {current} → {latest}[/yellow]")
    elif force:
        console.print(f"\n  [dim]Force reinstall: {current}[/dim]")
    else:
        console.print("\n[green]✅ Already on latest version.[/green]\n")
        return

    if check_only:
        console.print("  Run 'raceos update' to install.\n")
        return

    # Perform update
    console.print("\n  Updating...", end=" ")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "raceos-factory"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            console.print("[green]✅ Updated successfully![/green]")
            console.print("  [dim]Restart your shell for changes to take effect.[/dim]\n")
        else:
            console.print(f"[red]❌ Failed[/red]")
            console.print(f"  [dim]{result.stderr[:200]}[/dim]\n")
            console.print("  Try: pipx upgrade raceos-factory\n")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        console.print(f"[red]❌ {e}[/red]\n")


def _check_pypi_version() -> str | None:
    """Query PyPI for the latest version of raceos-factory."""
    try:
        import httpx
        resp = httpx.get(
            "https://pypi.org/pypi/raceos-factory/json",
            timeout=10,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.json()["info"]["version"]
        return None
    except Exception:
        return None


def _version_lt(current: str, latest: str) -> bool:
    """Check if current version is less than latest (simple tuple comparison)."""
    try:
        c = tuple(int(x) for x in current.split("."))
        l = tuple(int(x) for x in latest.split("."))
        return c < l
    except (ValueError, AttributeError):
        return False
