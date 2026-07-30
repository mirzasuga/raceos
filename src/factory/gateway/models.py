"""
Gateway Request/Response Models.

Type definitions for communication with the OpenRouter API.
These are the data structures that cross the gateway boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass
class Message:
    """A single message in a conversation."""

    role: str               # system | user | assistant
    content: str


@dataclass
class CompletionRequest:
    """Request to the OpenRouter completions API."""

    model: str
    messages: list[Message]
    max_tokens: int = 4096
    temperature: float = 0.1
    top_p: float = 1.0
    stop: list[str] | None = None
    stream: bool = False

    # Metadata (not sent to API, used for tracking)
    task_id: str = ""
    task_type: str = ""


@dataclass
class Usage:
    """Token usage from a completion response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class CompletionResponse:
    """Response from the OpenRouter completions API."""

    content: str
    model: str                  # Actual model used (may differ from request)
    finish_reason: str = "stop"
    usage: Usage = field(default_factory=Usage)

    # Metrics
    latency_seconds: float = 0.0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time)

    # Tracking
    task_id: str = ""
    attempt: int = 1


@dataclass
class GatewayError:
    """Structured error from the gateway."""

    status_code: int
    message: str
    retryable: bool = False
    provider: str = ""
    model: str = ""
    raw_response: str = ""

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429

    @property
    def is_server_error(self) -> bool:
        return 500 <= self.status_code < 600

    @property
    def is_client_error(self) -> bool:
        return 400 <= self.status_code < 500 and self.status_code != 429
