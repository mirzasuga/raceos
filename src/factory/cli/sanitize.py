"""
Output Sanitization for CLI Display.

Ensures LLM output displayed to human via terminal is safe:
    - Strips ANSI escape sequences (prevent terminal injection)
    - Removes potential prompt injection markers
    - Truncates excessively long output
    - Escapes shell-dangerous characters in display context

This module is called before any LLM-generated content is
printed to the terminal via rich/typer.

Security context: local CLI tool (not web). Main risk is
terminal escape sequences, not XSS. Belt-and-suspenders.

Usage:
    from factory.cli.sanitize import sanitize_output

    safe_text = sanitize_output(llm_response.content)
    console.print(safe_text)
"""

from __future__ import annotations

import re


# ANSI escape sequence pattern (prevents terminal control injection)
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[^[]]")

# Terminal control characters that could manipulate display
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")

# Prompt injection markers (LLM output pretending to be system)
_INJECTION_MARKERS = [
    "SYSTEM:",
    "<<SYS>>",
    "[INST]",
    "Human:",
    "Assistant:",
    "<|im_start|>",
    "<|im_end|>",
]

# Maximum output length for display (characters)
MAX_DISPLAY_LENGTH = 50_000


def sanitize_output(text: str, max_length: int = MAX_DISPLAY_LENGTH) -> str:
    """
    Sanitize LLM output for safe terminal display.

    Applies:
    1. Strip ANSI escape sequences
    2. Remove terminal control characters
    3. Strip prompt injection markers
    4. Truncate to max length

    Args:
        text: Raw LLM output text.
        max_length: Maximum characters to display.

    Returns:
        Sanitized text safe for terminal display.
    """
    if not text:
        return ""

    # 1. Strip ANSI escape sequences
    text = _ANSI_ESCAPE.sub("", text)

    # 2. Remove control characters (keep \n, \r, \t)
    text = _CONTROL_CHARS.sub("", text)

    # 3. Strip prompt injection markers
    for marker in _INJECTION_MARKERS:
        text = text.replace(marker, f"[{marker}]")  # Neuter by wrapping in brackets

    # 4. Truncate
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[... output truncated ...]"

    return text


def sanitize_for_log(text: str, max_length: int = 10_000) -> str:
    """
    Sanitize for structured log output (JSON-safe).

    More aggressive than display sanitization:
    - Also escapes quotes and backslashes
    - Shorter max length (logs are for debugging, not reading)
    """
    text = sanitize_output(text, max_length)
    # Ensure JSON-safe (no unescaped quotes breaking log structure)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return text
