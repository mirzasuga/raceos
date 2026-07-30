# RaceOS CLI.
"""
Command-line interface for the AI Software Factory.

Entry point: `raceos` command (registered in pyproject.toml).

Architecture:
    app.py      → Typer root + global options
    shell.py    → Interactive REPL
    parser.py   → Input parsing + intent detection
    session/    → Session lifecycle + state
    output/     → Streaming + progress + theme
    config/     → Configuration management
    commands/   → Individual command handlers
"""
