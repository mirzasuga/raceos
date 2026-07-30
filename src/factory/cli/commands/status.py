"""raceos status — show tasks, budget, approvals."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table


def run_status(console: Console) -> None:
    """Show active tasks, pending approvals, budget."""
    console.print("\n[bold]Factory Status[/bold]\n")

    # Read from checkpoint backend
    try:
        from factory.orchestrator.checkpoint import CheckpointBackend
        backend = CheckpointBackend()
        stats = backend.stats

        incomplete = stats.get("in_progress", 0)
        failed = stats.get("failed", 0)
        completed = stats.get("completed", 0)

        console.print(f"  📋 Pending: {incomplete} task(s)")
        console.print(f"  ✅ Completed: {completed} task(s)")
        console.print(f"  ❌ Failed: {failed} task(s)")

        # Show incomplete tasks
        if incomplete > 0:
            tasks = backend.get_incomplete()
            console.print("\n  [yellow]Incomplete tasks:[/yellow]")
            for task in tasks[:5]:
                desc = task.state.get("task", {}).get("description", "")[:40]
                console.print(f"    [magenta]{task.task_id}[/magenta] at:{task.node} — {desc}")

    except Exception:
        console.print("  [dim]Checkpoint status: unavailable[/dim]")

    console.print()
    run_budget(console)


def run_budget(console: Console) -> None:
    """Show budget status."""
    try:
        from factory.services import get_router
        router = get_router()
        status = router.get_budget_status()

        pct = status.pct_used
        color = "green" if pct < 80 else "yellow" if pct < 95 else "red"
        console.print(f"  💰 Budget: [{color}]${status.spent_today_usd:.2f} / ${status.daily_limit_usd:.2f} ({pct:.1f}%)[/{color}]")

        if status.should_downgrade:
            console.print("  [yellow]⚠️ Model downgrade active (budget > 90%)[/yellow]")
    except Exception:
        console.print("  💰 [dim]Budget: unavailable[/dim]")
    console.print()
