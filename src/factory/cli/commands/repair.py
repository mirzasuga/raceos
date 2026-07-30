"""raceos repair — auto-fix common issues found by doctor."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from rich.console import Console
from factory.cli.output.theme import THEME

console = Console(theme=THEME)


def run_repair():
    """Diagnose and fix common issues."""
    console.print("\n[bold]RaceOS Factory — Repair[/bold]\n")

    fixed = 0
    skipped = 0

    # 1. Missing .env
    if not Path(".env").exists() and Path(".env.example").exists():
        console.print("  🔧 Creating .env from .env.example...")
        shutil.copy(".env.example", ".env")
        console.print("     [green]✅ Created .env[/green]")
        console.print("     [yellow]→ Edit .env and add your NINE_ROUTER_API_KEY[/yellow]")
        fixed += 1
    elif not os.environ.get("NINE_ROUTER_API_KEY") and Path(".env").exists():
        content = Path(".env").read_text()
        if "your-9router-api-key-here" in content:
            console.print("  ⚠️  .env exists but API key is placeholder")
            console.print("     [yellow]→ Edit .env: replace 'your-9router-api-key-here' with real key[/yellow]")
            skipped += 1
        else:
            console.print("  ✅ .env has API key configured")

    # 2. Missing data directory
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        console.print("  🔧 Created data/ directory")
        fixed += 1

    # 3. Stale checkpoint lock
    lock_file = Path("data/checkpoints.db-wal")
    if lock_file.exists() and lock_file.stat().st_size == 0:
        lock_file.unlink()
        console.print("  🔧 Removed stale checkpoint lock")
        fixed += 1

    # 4. Missing uv (suggest install)
    if not shutil.which("uv"):
        console.print("  ⚠️  uv not installed (optional, for development)")
        console.print("     [dim]Install: curl -LsSf https://astral.sh/uv/install.sh | sh[/dim]")
        skipped += 1

    # 5. Check 9Router connectivity
    try:
        import httpx
        resp = httpx.get("http://localhost:20128/v1/models", timeout=3)
        if resp.status_code == 200:
            console.print("  ✅ 9Router reachable at localhost:20128")
        else:
            console.print("  ⚠️  9Router responded with status {resp.status_code}")
            skipped += 1
    except Exception:
        console.print("  ⚠️  9Router not reachable at localhost:20128")
        console.print("     [dim]Start 9Router or update config/router.yaml gateway.base_url[/dim]")
        skipped += 1

    # Summary
    console.print(f"\n  [bold]Fixed: {fixed} | Needs manual: {skipped}[/bold]")
    if skipped == 0 and fixed == 0:
        console.print("  [green]✅ Nothing to repair.[/green]")
    console.print()
