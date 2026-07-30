"""
9Router HTTP Transport.

HTTP client for 9Router LLM gateway. Handles:
    - Authentication (API key from env)
    - Request serialization
    - Response parsing
    - Retry with exponential backoff
    - Timeout enforcement
    - Usage metric collection

This client knows NOTHING about routing or model selection.
It receives a model ID and makes the call. 9Router decides which model.

Usage:
    client = GatewayClient()
    response = client.complete(request)
    client.close()
"""

from __future__ import annotations

import os
import time

import httpx

from .models import (
    CompletionRequest,
    CompletionResponse,
    GatewayError,
    Message,
    Usage,
)
from .retry import RetryConfig, RetryStrategy


class GatewayConfigError(Exception):
    """Raised when gateway configuration is invalid."""
    pass


class GatewayRequestError(Exception):
    """Raised when a gateway request fails after all retries."""

    def __init__(self, error: GatewayError):
        self.error = error
        super().__init__(f"[{error.status_code}] {error.message}")


class GatewayClient:
    """
    HTTP client for 9Router gateway.

    Responsibilities:
    - Send completion requests via 9Router
    - Handle authentication via API key
    - Enforce timeouts per request
    - Retry on transient failures (429, 5xx)
    - Parse responses into structured types
    - Track token usage and cost per call

    Does NOT:
    - Decide which model to use (that's 9Router)
    - Store context or memory
    - Orchestrate workflows
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://localhost:20128/v1",
        default_timeout: float = 60.0,
        retry_config: RetryConfig | None = None,
        app_name: str = "RaceOS Factory",
    ):
        self.api_key = api_key or os.environ.get("NINE_ROUTER_API_KEY", "")
        if not self.api_key:
            raise GatewayConfigError(
                "NINE_ROUTER_API_KEY is required. Set it in .env file."
            )

        self.base_url = base_url.rstrip("/")
        self.default_timeout = default_timeout
        self.retry_strategy = RetryStrategy(retry_config or RetryConfig())
        self.app_name = app_name

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": app_name,
            },
            timeout=httpx.Timeout(
                connect=10.0,
                read=default_timeout,
                write=30.0,
                pool=10.0,
            ),
        )

    def complete(
        self,
        request: CompletionRequest,
        timeout: float | None = None,
    ) -> CompletionResponse:
        """
        Send a completion request via 9Router.

        Retries on transient failures with exponential backoff.
        Raises GatewayRequestError after all retries exhausted.

        Args:
            request: Completion request with model, messages, params.
            timeout: Override timeout for this specific request.

        Returns:
            CompletionResponse with content, usage, and metrics.

        Raises:
            GatewayRequestError: After all retries exhausted.
            GatewayConfigError: If API key is missing.
        """
        self.retry_strategy.reset()
        last_error: GatewayError | None = None

        for attempt in range(1, self.retry_strategy.config.max_attempts + 1):
            try:
                return self._execute_request(request, attempt, timeout)

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error = GatewayError(
                    status_code=status_code,
                    message=self._extract_error_message(e.response),
                    retryable=self.retry_strategy.should_retry(attempt, status_code),
                    provider=self._extract_provider(request.model),
                    model=request.model,
                    raw_response=e.response.text[:500],
                )
                last_error = error
                self.retry_strategy.record_attempt(attempt, status_code, error.message)

                if not error.retryable:
                    raise GatewayRequestError(error) from e

                # Wait before retry
                if attempt < self.retry_strategy.config.max_attempts:
                    self.retry_strategy.wait(attempt)

            except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                last_error = GatewayError(
                    status_code=504,
                    message=f"Timeout: {e}",
                    retryable=True,
                    model=request.model,
                )
                self.retry_strategy.record_attempt(attempt, 504, str(e))

                if attempt < self.retry_strategy.config.max_attempts:
                    self.retry_strategy.wait(attempt)

            except httpx.ConnectError as e:
                last_error = GatewayError(
                    status_code=0,
                    message=f"Connection failed: {e}",
                    retryable=True,
                    model=request.model,
                )
                self.retry_strategy.record_attempt(attempt, 0, str(e))

                if attempt < self.retry_strategy.config.max_attempts:
                    self.retry_strategy.wait(attempt)

        # All retries exhausted
        raise GatewayRequestError(last_error or GatewayError(
            status_code=0, message="All retries exhausted", retryable=False
        ))

    def _execute_request(
        self,
        request: CompletionRequest,
        attempt: int,
        timeout: float | None,
    ) -> CompletionResponse:
        """Execute a single HTTP request (no retry logic)."""
        start = time.time()

        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.stop:
            payload["stop"] = request.stop

        # Prompt caching: mark first system message as cacheable prefix
        # LLM providers cache stable system prompts at 50% discount
        if payload["messages"] and payload["messages"][0]["role"] == "system":
            payload["messages"][0]["cache_control"] = {"type": "ephemeral"}

        # Override timeout if specified
        req_timeout = timeout or self.default_timeout
        response = self._client.post(
            "/chat/completions",
            json=payload,
            timeout=req_timeout,
        )
        response.raise_for_status()

        data = response.json()
        elapsed = time.time() - start

        # Parse usage
        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        # Extract content
        choices = data.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
        finish_reason = choices[0].get("finish_reason", "stop") if choices else "error"

        return CompletionResponse(
            content=content,
            model=data.get("model", request.model),
            finish_reason=finish_reason,
            usage=usage,
            latency_seconds=elapsed,
            task_id=request.task_id,
            attempt=attempt,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract error message from API error response."""
        try:
            data = response.json()
            error = data.get("error", {})
            if isinstance(error, dict):
                return error.get("message", response.text[:200])
            return str(error)
        except Exception:
            return response.text[:200]

    @staticmethod
    def _extract_provider(model_id: str) -> str:
        """Extract provider name from model ID."""
        if "/" in model_id:
            return model_id.split("/")[0]
        return "unknown"
