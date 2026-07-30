"""raceos doctor — system health check."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console


def run_doctor(console: Console) -> None:
    """Run system health checks and report status."""
    console.print("\n[bold]RaceOS Factory — System Health[/bold]\n")

    checks = [
        ("Python ≥ 3.11", _check_python()),
        ("Config directory", _check_path("config/")),
        ("factory.yaml", _check_path("config/factory.yaml")),
        ("router.yaml", _check_path("config/router.yaml")),
        ("opencode.json", _check_path("config/opencode.json")),
        ("Brain (.raceos/)", _check_path("../.raceos/")),
        ("OpenSpec", _check_path("../openspec/specs/")),
        ("API key set", _check_env("NINE_ROUTER_API_KEY")),
        ("uv available", _check_binary("uv")),
        ("node available", _check_binary("node")),
    ]

    passed = 0
    failed = 0
    for name, ok in checks:
        icon = "✅" if ok else "❌"
        color = "green" if ok else "red"
        console.print(f"  {icon} [{color}]{name}[/{color}]")
        if ok:
            passed += 1
        else:
            failed += 1

    console.print(f"\n  [bold]Result: {passed} passed, {failed} failed[/bold]")
    if failed == 0:
        console.print("  [green]System healthy.[/green]\n")
    else:
        console.print("  [yellow]Run 'raceos repair' to fix issues.[/yellow]\n")


def _check_python() -> bool:
    return sys.version_info >= (3, 11)


def _check_path(path: str) -> bool:
    return Path(path).exists()


def _check_env(var: str) -> bool:
    import os
    val = os.environ.get("NINE_ROUTER_API_KEY", "")
    return len(val) > 5


def _check_binary(name: str) -> bool:
    return shutil.which(name) is not None
