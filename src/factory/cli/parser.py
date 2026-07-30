"""
RaceOS CLI Input Parser.

Parses user input from the interactive shell into structured ParseResult.

Handles:
    - Slash commands (/help, /status, /approve TASK-ID)
    - Natural language with intent detection
    - Empty input
    - Multi-word arguments

No LLM used for parsing. Pure regex + keyword matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParseResult:
    """Result of parsing user input."""

    type: str           # "quit" | "help" | "clear" | "status" | "natural" | etc.
    raw: str            # Original input
    args: str = ""      # Arguments after command
    intent: str = ""    # Detected intent for natural language


# --- Slash Command Map ---

_SLASH_COMMANDS = {
    "/quit": "quit",
    "/exit": "quit",
    "/q": "quit",
    "/help": "help",
    "/h": "help",
    "/?": "help",
    "/clear": "clear",
    "/cls": "clear",
    "/status": "status",
    "/s": "status",
    "/budget": "budget",
    "/history": "history",
    "/version": "version",
    "/config": "config",
    "/approve": "approve",
    "/reject": "reject",
    "/resume": "resume",
    "/cancel": "cancel",
    "/logs": "logs",
}

# --- Intent Patterns (for natural language) ---

_INTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(implement|add|create|build|make)\s+", re.I), "feature"),
    (re.compile(r"^(fix|bug|debug|why|broken)\s+", re.I), "debug"),
    (re.compile(r"^(review|check|audit|inspect)\s+", re.I), "review"),
    (re.compile(r"^(how|what|explain|describe|tell)\s+", re.I), "docs"),
    (re.compile(r"^(wire|pin|schematic|bom|hardware|pcb)\s+", re.I), "hardware"),
    (re.compile(r"^(research|interview|market|user)\s+", re.I), "research"),
    (re.compile(r"^(data|telemetry|pipeline|stream)\s+", re.I), "telemetry"),
    (re.compile(r"^(mobile|app|screen|react)\s+", re.I), "mobile"),
    (re.compile(r"^(doc|document|readme|changelog)\s+", re.I), "docs"),
    (re.compile(r"^(refactor|clean|restructure)\s+", re.I), "refactor"),
    (re.compile(r"^(test|spec|scenario|given)\s+", re.I), "test"),
]


def parse_input(raw: str) -> ParseResult:
    """
    Parse user input into a structured result.

    Priority:
    1. Empty → skip
    2. Slash command → route directly
    3. Natural language → detect intent

    Args:
        raw: Raw user input string.

    Returns:
        ParseResult with type, args, and detected intent.
    """
    stripped = raw.strip()

    # Empty
    if not stripped:
        return ParseResult(type="empty", raw=raw)

    # Slash command
    if stripped.startswith("/"):
        return _parse_slash(stripped)

    # Natural language
    return _parse_natural(stripped)


def _parse_slash(input_str: str) -> ParseResult:
    """Parse a slash command."""
    parts = input_str.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command in _SLASH_COMMANDS:
        return ParseResult(
            type=_SLASH_COMMANDS[command],
            raw=input_str,
            args=args,
        )

    # Unknown slash command
    return ParseResult(type="slash_unknown", raw=input_str, args=args)


def _parse_natural(input_str: str) -> ParseResult:
    """Parse natural language input and detect intent."""
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.match(input_str):
            return ParseResult(
                type="natural",
                raw=input_str,
                intent=intent,
            )

    # No pattern matched → general chat/feature intent
    return ParseResult(
        type="natural",
        raw=input_str,
        intent="chat",
    )
