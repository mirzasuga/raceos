"""
Streaming Token Display.

Renders LLM tokens as they arrive, providing a typewriter effect
in the terminal. Handles both streaming completions and chunked output.

Features:
    - Token-by-token display with cursor
    - Markdown rendering after stream completes
    - Interrupt handling (Ctrl+C stops stream)
    - Buffer management (accumulate → render)

Usage:
    streamer = StreamDisplay(console)
    streamer.start()
    for token in token_stream:
        streamer.feed(token)
    streamer.end()
"""

from __future__ import annotations

import sys
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text


class StreamDisplay:
    """
    Real-time streaming token display.

    Accumulates tokens and renders them live in the terminal.
    On completion, re-renders as formatted markdown.
    """

    def __init__(self, console: Console):
        self.console = console
        self._buffer: str = ""
        self._live: Live | None = None
        self._started: bool = False
        self._interrupted: bool = False
        self._token_count: int = 0
        self._start_time: float = 0.0

    def start(self, label: str = "") -> None:
        """Begin streaming display."""
        self._buffer = ""
        self._started = True
        self._interrupted = False
        self._token_count = 0
        self._start_time = time.time()

        if label:
            self.console.print(f"\n[dim]{label}[/dim]")

        self._live = Live(
            Text("▌", style="cyan"),
            console=self.console,
            refresh_per_second=15,
            transient=True,  # Remove live display when done
        )
        self._live.start()

    def feed(self, token: str) -> None:
        """
        Feed a single token into the stream.

        Accumulates in buffer and updates live display.
        """
        if not self._started or self._interrupted:
            return

        self._buffer += token
        self._token_count += 1

        # Update live display with buffer + cursor
        if self._live:
            display_text = self._buffer + "▌"
            # Truncate display if too long (keep last 2000 chars visible)
            if len(display_text) > 2000:
                display_text = "…" + display_text[-2000:]
            self._live.update(Text(display_text))

    def feed_chunk(self, chunk: str) -> None:
        """Feed a multi-token chunk (for non-streaming responses)."""
        for char in chunk:
            self.feed(char)
            # Small delay for visual effect on chunks
            # (real streaming won't need this)

    def interrupt(self) -> None:
        """Interrupt the stream (Ctrl+C)."""
        self._interrupted = True
        if self._live:
            self._live.stop()
        self.console.print("\n[dim]Stream interrupted.[/dim]")

    def end(self) -> str:
        """
        End streaming and render final output.

        Returns the complete accumulated buffer.
        """
        if self._live:
            self._live.stop()
            self._live = None

        self._started = False
        elapsed = time.time() - self._start_time

        if self._buffer:
            # Render final output as markdown (prettier than raw text)
            try:
                self.console.print(Markdown(self._buffer))
            except Exception:
                # Fallback to plain text if markdown parsing fails
                self.console.print(self._buffer)

            # Stats line
            self.console.print(
                f"\n[dim]({self._token_count} tokens, {elapsed:.1f}s)[/dim]"
            )

        return self._buffer

    @property
    def is_active(self) -> bool:
        """Whether streaming is currently active."""
        return self._started and not self._interrupted

    @property
    def content(self) -> str:
        """Current buffer content."""
        return self._buffer
