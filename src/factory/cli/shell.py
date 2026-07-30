"""
RaceOS Interactive Shell (REPL).

A readline-based interactive shell with:
    - Persistent command history
    - Tab completion for slash commands
    - Colored prompt with session indicator
    - Slash command routing
    - Natural language input routing
    - Graceful exit (Ctrl+C, Ctrl+D, /quit)

Usage:
    Called automatically when `raceos` is invoked without arguments.
"""

from __future__ import annotations

import readline
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from factory.cli.output.theme import THEME
from factory.cli.parser import ParseResult, parse_input
from factory.cli.session.manager import SessionManager

# History file location
HISTORY_FILE = Path("data/.raceos_history")
MAX_HISTORY = 1000

# Slash commands available in shell
SLASH_COMMANDS = [
    "/help", "/status", "/approve", "/reject", "/resume",
    "/cancel", "/budget", "/history", "/clear", "/config",
    "/quit", "/exit", "/version",
]


def run_shell(app_state) -> None:
    """
    Launch the interactive shell.

    This is the main REPL loop. Runs until user exits.
    """
    console = Console(theme=THEME)
    session = SessionManager()
    session.start()

    _setup_readline()
    _print_welcome(console)

    # Check for crashed tasks on startup
    from factory.cli.resume import check_incomplete_on_startup
    bridge = _get_bridge()
    check_incomplete_on_startup(bridge, console)

    try:
        _repl_loop(console, session, app_state)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Use /quit to exit.[/dim]")
        _repl_loop(console, session, app_state)
    finally:
        _save_history()
        session.end()


def _repl_loop(console: Console, session: SessionManager, app_state) -> None:
    """Main read-eval-print loop."""
    while True:
        try:
            # Show prompt
            prompt = _build_prompt(session)
            user_input = input(prompt)

            # Empty input → skip
            if not user_input.strip():
                continue

            # Parse input
            parsed = parse_input(user_input)

            # Route based on parse result
            _handle_parsed(parsed, console, session, app_state)

        except EOFError:
            # Ctrl+D → exit
            console.print("\n[dim]Goodbye.[/dim]")
            break
        except KeyboardInterrupt:
            # Ctrl+C → cancel current input, continue loop
            console.print()
            continue


def _handle_parsed(parsed: ParseResult, console: Console, session: SessionManager, app_state) -> None:
    """Route a parsed input to the appropriate handler."""

    if parsed.type == "quit":
        console.print("[dim]Goodbye.[/dim]")
        raise EOFError()

    elif parsed.type == "help":
        _print_help(console)

    elif parsed.type == "clear":
        console.clear()

    elif parsed.type == "version":
        import factory
        console.print(f"raceos {factory.__version__}")

    elif parsed.type == "history":
        _print_history(console)

    elif parsed.type == "status":
        from factory.cli.commands.status import run_status
        run_status(console)

    elif parsed.type == "budget":
        from factory.cli.commands.status import run_budget
        run_budget(console)

    elif parsed.type == "config":
        from factory.cli.config.manager import handle_config
        parts = parsed.args.split(maxsplit=2) if parsed.args else ["list"]
        action = parts[0] if parts else "list"
        key = parts[1] if len(parts) > 1 else None
        value = parts[2] if len(parts) > 2 else None
        handle_config(action, key, value, console)

    elif parsed.type == "approve":
        from factory.cli.resume import handle_approve
        handle_approve(parsed.args.strip(), _get_bridge(), console)

    elif parsed.type == "reject":
        from factory.cli.resume import handle_reject
        parts = parsed.args.split(maxsplit=1) if parsed.args else [""]
        task_id = parts[0]
        reason = parts[1] if len(parts) > 1 else ""
        handle_reject(task_id, _get_bridge(), console, reason)

    elif parsed.type == "resume":
        from factory.cli.resume import handle_resume
        handle_resume(parsed.args.strip(), _get_bridge(), console)

    elif parsed.type == "cancel":
        from factory.cli.resume import handle_cancel
        handle_cancel(parsed.args.strip(), _get_bridge(), console)

    elif parsed.type == "slash_unknown":
        console.print(f"[red]Unknown command: {parsed.raw}[/red]")
        console.print("[dim]Type /help for available commands.[/dim]")

    elif parsed.type == "natural":
        # Natural language → route through factory bridge
        _execute_via_bridge(parsed, console, session)

    else:
        console.print(f"[dim]Unhandled: {parsed.type}[/dim]")


# --- Prompt ---

def _build_prompt(session: SessionManager) -> str:
    """Build the shell prompt string."""
    task_count = session.pending_count
    if task_count > 0:
        return f"\033[36mraceos\033[0m [\033[33m{task_count} pending\033[0m]> "
    return "\033[36mraceos\033[0m> "


# --- Factory Bridge Connection ---

_bridge_instance = None


def _get_bridge():
    """Get or create the singleton FactoryBridge."""
    global _bridge_instance
    if _bridge_instance is None:
        from factory.cli.bridge import FactoryBridge
        _bridge_instance = FactoryBridge()
    return _bridge_instance


def _execute_via_bridge(parsed: "ParseResult", console: Console, session: SessionManager) -> None:
    """
    Execute natural language input through the AI Factory.

    Flow: intent → TaskRequest → bridge.submit() → result
    Uses agent visualization for progress display.
    """
    from factory.cli.bridge import TaskRequest
    from factory.cli.output.agent_viz import AgentViz
    from factory.cli.resume import _display_result

    bridge = _get_bridge()

    # Infer domain from intent
    domain_map = {
        "feature": "firmware",
        "debug": "firmware",
        "hardware": "hardware",
        "mobile": "mobile",
        "docs": "firmware",
        "research": "firmware",
        "telemetry": "firmware",
        "refactor": "firmware",
        "test": "firmware",
        "chat": "firmware",
        "review": "firmware",
    }
    domain = domain_map.get(parsed.intent, "firmware")

    # Build request
    request = TaskRequest(
        description=parsed.raw,
        domain=domain,
        intent=parsed.intent,
    )

    # Set up agent visualization
    viz = AgentViz(console)

    def on_event(event):
        viz.on_event(event)

    bridge.set_event_callback(on_event)

    # Submit to factory
    console.print(f"\n[dim]Intent: {parsed.intent} │ Domain: {domain}[/dim]")
    viz.start(task_id="...", description=parsed.raw[:50])

    try:
        result = bridge.submit(request)
    finally:
        viz.stop()

    # Display result
    _display_result(result, console)

    # Record in session
    session.record_command(parsed.raw)

    # Show persist suggestion if applicable
    if result.persist_suggestion:
        ps = result.persist_suggestion
        console.print(f"\n[cyan]💾 Save documentation? → {ps.get('path', '')}[/cyan]")
        console.print(f"[dim]   Run: /save {result.task_id}[/dim]")


# --- Readline Setup ---

def _setup_readline() -> None:
    """Configure readline: history + tab completion."""
    # Load history
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY_FILE.exists():
        readline.read_history_file(str(HISTORY_FILE))
    readline.set_history_length(MAX_HISTORY)

    # Tab completion for slash commands
    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")


def _completer(text: str, state: int) -> str | None:
    """Tab completion for slash commands."""
    if text.startswith("/"):
        matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
    else:
        matches = []

    if state < len(matches):
        return matches[state]
    return None


def _save_history() -> None:
    """Save readline history to file."""
    try:
        readline.write_history_file(str(HISTORY_FILE))
    except OSError:
        pass


# --- Output Helpers ---

def _print_welcome(console: Console) -> None:
    """Print welcome message on shell start."""
    import factory
    console.print(
        Panel(
            "[bold]RaceOS AI Software Factory[/bold]\n"
            f"[dim]v{factory.__version__} • Type /help for commands • /quit to exit[/dim]",
            border_style="cyan",
        )
    )


def _print_help(console: Console) -> None:
    """Print help information."""
    console.print("""
[bold]Shell Commands:[/bold]

  [cyan]/help[/cyan]              Show this help
  [cyan]/status[/cyan]            Show active tasks + pending approvals
  [cyan]/budget[/cyan]            Show cost status
  [cyan]/approve <id>[/cyan]      Approve a pending task
  [cyan]/reject <id>[/cyan]       Reject a pending task
  [cyan]/history[/cyan]           Show command history
  [cyan]/config[/cyan] [action]   Manage configuration
  [cyan]/clear[/cyan]             Clear screen
  [cyan]/version[/cyan]           Show version
  [cyan]/quit[/cyan]              Exit shell

[bold]Natural Language:[/bold]

  Type any task description and it will be routed to the appropriate agent:

  [green]implement engine load gauge[/green]     → Engineer (firmware)
  [green]fix typo in ecu_parser.h[/green]        → Engineer (debugging)
  [green]how to wire display to stm32[/green]    → Hardware (documentation)
  [green]review last changes[/green]             → Review Agent
""")


def _print_history(console: Console) -> None:
    """Print recent command history."""
    length = readline.get_current_history_length()
    start = max(1, length - 20)
    console.print("[bold]Recent History:[/bold]\n")
    for i in range(start, length + 1):
        item = readline.get_history_item(i)
        if item:
            console.print(f"  [dim]{i}[/dim] {item}")
