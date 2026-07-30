# CLI

> Typer-based CLI entry point for the RaceOS AI Software Factory.

## Responsibility

Provides the command-line interface for interacting with the factory. Exposes commands for submitting tasks, checking workflow status, approving/rejecting human-in-the-loop gates, and viewing budget consumption. Handles argument parsing, output formatting, and user interaction.

## Does NOT

- Implement business logic (delegates to Orchestrator and other modules)
- Make LLM calls
- Access files directly (uses appropriate modules)
- Run as a long-lived daemon (each invocation is a single command)

## Key Files (planned)

- `app.py` — Typer app definition and main entry point
- `commands/task.py` — `factory task` command (submit new task)
- `commands/status.py` — `factory status` command (check workflow state)
- `commands/approve.py` — `factory approve` command (approve gate)
- `commands/reject.py` — `factory reject` command (reject gate)
- `commands/budget.py` — `factory budget` command (view cost/usage)
- `formatters.py` — output formatting (table, JSON, etc.)

## Dependencies

- `typer` (CLI framework)
- `rich` (terminal output formatting)
- `factory.orchestrator` (workflow submission and status)
- `factory.config` (CLI defaults)
