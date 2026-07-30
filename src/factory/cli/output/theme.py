"""
RaceOS CLI Theme.

Color scheme and styling constants for consistent terminal output.
Based on motorsport aesthetics: cyan primary, amber warning, red danger.
"""

from __future__ import annotations

from rich.theme import Theme

# RaceOS color palette
COLORS = {
    "primary": "cyan",
    "secondary": "blue",
    "success": "green",
    "warning": "yellow",
    "danger": "red",
    "muted": "dim",
    "accent": "magenta",
}

# Rich theme instance
THEME = Theme({
    "info": "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "muted": "dim",
    "command": "bold cyan",
    "task_id": "bold magenta",
    "cost": "green",
    "model": "blue",
    "duration": "dim cyan",
    "phase.pending": "dim",
    "phase.running": "bold yellow",
    "phase.done": "green",
    "phase.failed": "red",
    "phase.paused": "yellow",
})

# Phase status icons
ICONS = {
    "pending": "○",
    "running": "⏳",
    "done": "✅",
    "failed": "❌",
    "warning": "⚠️",
    "paused": "⏸️",
    "retrying": "🔄",
    "approved": "✅",
    "rejected": "⛔",
}

# Branding
BANNER = """[cyan]
 ╦═╗┌─┐┌─┐┌─┐╔═╗╔═╗
 ╠╦╝├─┤│  ├┤ ║ ║╚═╗
 ╩╚═┘ └└─┘└─┘╚═╝╚═╝[/cyan]
[dim]AI Software Factory[/dim]
"""
