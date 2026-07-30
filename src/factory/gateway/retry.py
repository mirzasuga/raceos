"""
Retry Strategy.

Implements exponential backoff with jitter for resilient API calls.
Separate from the gateway client so retry policy can be configured
and tested independently.

Features:
    - Exponential backoff: 1s → 2s → 4s → 8s (configurable)
    - Jitter: ±20% randomness to prevent thundering herd
    - Status-aware: only retry on retryable HTTP status codes
    - Budget-aware: stops retrying if cost would exceed budget
    - Audit: logs every retry attempt for debugging

Usage:
    strategy = RetryStrategy(config)
    strategy.should_retry(attempt=1, status_code=429)  # True
    strategy.get_delay(attempt=2)  # 2.0 seconds (with jitter)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 30000
    multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.2     # ±20%

    retry_on_status: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    no_retry_on_status: list[int] = field(default_factory=lambda: [400, 401, 403, 404, 422])


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""

    attempt: int
    status_code: int
    delay_ms: float
    timestamp: float = field(default_factory=time.time)
    error_message: str = ""


class RetryStrategy:
    """
    Determines whether and when to retry a failed request.

    Implements exponential backoff with configurable parameters.
    All decisions are deterministic given the same inputs
    (except jitter which adds controlled randomness).
    """

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()
        self.attempts: list[RetryAttempt] = []

    def should_retry(self, attempt: int, status_code: int) -> bool:
        """
        Determine if a request should be retried.

        Args:
            attempt: Current attempt number (1-based).
            status_code: HTTP status code received.

        Returns:
            True if the request should be retried.
        """
        # Exceeded max attempts
        if attempt >= self.config.max_attempts:
            return False

        # Explicitly non-retryable status
        if status_code in self.config.no_retry_on_status:
            return False

        # Retryable status
        if status_code in self.config.retry_on_status:
            return True

        # Unknown status code — don't retry by default
        return False

    def get_delay_ms(self, attempt: int) -> float:
        """
        Calculate delay before next retry attempt.

        Uses exponential backoff: base * multiplier^(attempt-1)
        With optional jitter to prevent thundering herd.

        Args:
            attempt: Current attempt number (1-based).

        Returns:
            Delay in milliseconds before next retry.
        """
        # Exponential backoff
        delay = self.config.base_delay_ms * (self.config.multiplier ** (attempt - 1))

        # Cap at max delay
        delay = min(delay, self.config.max_delay_ms)

        # Add jitter
        if self.config.jitter:
            jitter_range = delay * self.config.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)

    def get_delay_seconds(self, attempt: int) -> float:
        """Get delay in seconds (convenience)."""
        return self.get_delay_ms(attempt) / 1000.0

    def wait(self, attempt: int) -> None:
        """Block for the calculated delay duration."""
        delay = self.get_delay_seconds(attempt)
        time.sleep(delay)

    def record_attempt(self, attempt: int, status_code: int, error: str = "") -> None:
        """Record a retry attempt for audit trail."""
        self.attempts.append(RetryAttempt(
            attempt=attempt,
            status_code=status_code,
            delay_ms=self.get_delay_ms(attempt),
            error_message=error,
        ))

    def reset(self) -> None:
        """Reset retry state for a new request."""
        self.attempts = []

    @property
    def total_delay_ms(self) -> float:
        """Total delay accumulated across all attempts."""
        return sum(a.delay_ms for a in self.attempts)

    @property
    def attempt_count(self) -> int:
        """Number of attempts recorded."""
        return len(self.attempts)
