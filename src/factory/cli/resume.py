"""
Task Resume, Retry, and Cancel.

Handles lifecycle operations on existing tasks:
    - Resume: continue a crashed/interrupted task from checkpoint
    - Retry: re-attempt a failed task with escalation
    - Cancel: stop a running or pending task

All operations go through the FactoryBridge.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from factory.cli.bridge import FactoryBridge, TaskResult


def handle_resume(task_id: str, bridge: FactoryBridge, console: Console) -> TaskResult | None:
    """
    Resume an incomplete task.

    If task_id is empty, shows list of resumable tasks and prompts.
    """
    if not task_id:
        # Show resumable tasks
        incomplete = bridge.get_incomplete_tasks()
        if not incomplete:
            console.print("[dim]No incomplete tasks to resume.[/dim]")
            return None

        table = Table(title="Resumable Tasks")
        table.add_column("ID", style="bold magenta")
        table.add_column("Description")
        table.add_column("Paused At")
        table.add_column("Status")

        for task in incomplete:
            table.add_row(
                task["task_id"],
                task["description"][:50],
                task["node"],
                task["status"],
            )
        console.print(table)
        console.print("\n[dim]Use: /resume TASK-ID[/dim]")
        return None

    # Resume specific task
    console.print(f"[cyan]Resuming {task_id}...[/cyan]")
    result = bridge.resume(task_id)
    _display_result(result, console)
    return result


def handle_retry(task_id: str, bridge: FactoryBridge, console: Console) -> TaskResult | None:
    """
    Retry a failed task with escalation.

    Increments attempt counter → 9Router may select a better model.
    """
    if not task_id:
        console.print("[red]Usage: /retry TASK-ID[/red]")
        return None

    console.print(f"[cyan]Retrying {task_id} (model may escalate)...[/cyan]")
    result = bridge.retry(task_id)
    _display_result(result, console)
    return result


def handle_cancel(task_id: str, bridge: FactoryBridge, console: Console) -> bool:
    """Cancel a running or pending task."""
    if not task_id:
        console.print("[red]Usage: /cancel TASK-ID[/red]")
        return False

    success = bridge.cancel(task_id)
    if success:
        console.print(f"[yellow]⛔ Task {task_id} cancelled.[/yellow]")
    else:
        console.print(f"[red]Could not cancel {task_id} (not found or already completed).[/red]")
    return success


def handle_approve(task_id: str, bridge: FactoryBridge, console: Console) -> bool:
    """Approve a task at human gate."""
    if not task_id:
        console.print("[red]Usage: /approve TASK-ID[/red]")
        return False

    success = bridge.approve(task_id)
    if success:
        console.print(f"[green]✅ Task {task_id} approved.[/green]")
    else:
        console.print(f"[red]Could not approve {task_id} (not found or not awaiting approval).[/red]")
    return success


def handle_reject(task_id: str, bridge: FactoryBridge, console: Console, reason: str = "") -> bool:
    """Reject a task at human gate."""
    if not task_id:
        console.print("[red]Usage: /reject TASK-ID [reason][/red]")
        return False

    success = bridge.reject(task_id, reason)
    if success:
        console.print(f"[yellow]⛔ Task {task_id} rejected.[/yellow]")
        if reason:
            console.print(f"[dim]Reason: {reason}[/dim]")
    else:
        console.print(f"[red]Could not reject {task_id}.[/red]")
    return success


def check_incomplete_on_startup(bridge: FactoryBridge, console: Console) -> None:
    """
    Check for incomplete tasks on CLI startup.

    Shows a prompt if crashed tasks are found:
        ⚠️ Found 1 incomplete task: TASK-A1B2C3
        [R]esume  [D]ismiss  [S]kip
    """
    incomplete = bridge.get_incomplete_tasks()
    if not incomplete:
        return

    console.print(f"\n[yellow]⚠️  Found {len(incomplete)} incomplete task(s):[/yellow]")
    for task in incomplete[:3]:  # Show max 3
        console.print(f"    [magenta]{task['task_id']}[/magenta]: {task['description'][:50]} (at: {task['node']})")

    console.print("\n  [R]esume  [D]ismiss  [S]kip\n")

    try:
        choice = input("  > ").strip().lower()
        if choice in ("r", "resume"):
            for task in incomplete:
                handle_resume(task["task_id"], bridge, console)
        elif choice in ("d", "dismiss"):
            for task in incomplete:
                bridge.cancel(task["task_id"])
            console.print("[dim]Dismissed all incomplete tasks.[/dim]")
        else:
            console.print("[dim]Skipped. Use /resume later.[/dim]")
    except (EOFError, KeyboardInterrupt):
        console.print("[dim]Skipped.[/dim]")


# --- Helpers ---

def _display_result(result: TaskResult, console: Console) -> None:
    """Display task result to user."""
    if result.status == "completed":
        console.print(f"\n[green]✅ {result.task_id} completed[/green] ({result.duration_seconds:.1f}s, ${result.cost_usd:.4f})")
        if result.modified_files:
            console.print(f"[dim]Modified: {', '.join(result.modified_files[:5])}[/dim]")
        if result.summary:
            console.print(f"\n{result.summary[:200]}")
        if result.suggested_follow_ups:
            console.print("\n[bold]💡 Suggested follow-ups:[/bold]")
            for fu in result.suggested_follow_ups:
                console.print(f"  • {fu.get('description', '')}")
    elif result.status == "failed":
        console.print(f"\n[red]❌ {result.task_id} failed[/red]")
        console.print(f"[red]{result.error}[/red]")
        console.print("[dim]Use /retry TASK-ID to retry with model escalation.[/dim]")
    elif result.status == "cancelled":
        console.print(f"\n[yellow]⛔ {result.task_id} cancelled[/yellow]")
