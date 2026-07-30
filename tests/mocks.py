"""
Mock LLM Gateway.

A fake GatewayClient that returns canned responses without making real API calls.
Used by all integration tests to simulate LLM behavior deterministically.

Features:
- Configurable responses per model/prompt pattern
- Tracks all calls for assertion
- Simulates failures (timeout, 429, 500)
- Simulates token usage
- Zero network calls
"""

from __future__ import annotations

from dataclasses import dataclass, field
from factory.gateway.models import CompletionRequest, CompletionResponse, Usage


@dataclass
class MockCall:
    """Record of a call made to the mock gateway."""
    model: str
    messages: list[dict]
    max_tokens: int
    temperature: float
    response: str


class MockGatewayClient:
    """
    Fake gateway that returns canned responses.

    Usage:
        mock = MockGatewayClient()
        mock.add_response("classify", '{"task_type":"coding","complexity":"medium"}')
        mock.add_response("default", "Hello, I am an AI assistant.")

        # Inject into nodes:
        result = orchestrator_node(state, gateway=mock)
    """

    def __init__(self):
        self._responses: dict[str, str] = {}
        self._pattern_responses: list[tuple[str, str]] = []
        self._calls: list[MockCall] = []
        self._fail_next: str | None = None
        self._fail_count: int = 0
        self._default_response: str = "Mock LLM response."

    def add_response(self, key: str, response: str) -> None:
        """Add a response for a specific key (matched against prompt content)."""
        self._responses[key] = response

    def add_pattern_response(self, pattern: str, response: str) -> None:
        """Add response triggered when prompt contains pattern."""
        self._pattern_responses.append((pattern, response))

    def set_default_response(self, response: str) -> None:
        """Set fallback response when no pattern matches."""
        self._default_response = response

    def fail_next(self, error: str = "timeout", count: int = 1) -> None:
        """Make the next N calls fail with specified error."""
        self._fail_next = error
        self._fail_count = count

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Fake completion — returns canned response based on prompt content."""
        # Check if we should fail
        if self._fail_count > 0:
            self._fail_count -= 1
            error = self._fail_next
            if error == "timeout":
                from factory.gateway.client import GatewayRequestError
                from factory.gateway.models import GatewayError
                raise GatewayRequestError(GatewayError(status_code=504, message="Mock timeout", retryable=True))
            elif error == "429":
                from factory.gateway.client import GatewayRequestError
                from factory.gateway.models import GatewayError
                raise GatewayRequestError(GatewayError(status_code=429, message="Mock rate limit", retryable=True))
            elif error == "500":
                from factory.gateway.client import GatewayRequestError
                from factory.gateway.models import GatewayError
                raise GatewayRequestError(GatewayError(status_code=500, message="Mock server error", retryable=True))
            elif error == "401":
                from factory.gateway.client import GatewayRequestError
                from factory.gateway.models import GatewayError
                raise GatewayRequestError(GatewayError(status_code=401, message="Mock unauthorized", retryable=False))

        # Find matching response
        prompt_text = " ".join(m.content for m in request.messages)
        response_text = self._find_response(prompt_text)

        # Record call
        self._calls.append(MockCall(
            model=request.model,
            messages=[{"role": m.role, "content": m.content[:100]} for m in request.messages],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            response=response_text[:100],
        ))

        return CompletionResponse(
            content=response_text,
            model=request.model,
            finish_reason="stop",
            usage=Usage(
                prompt_tokens=len(prompt_text) // 4,
                completion_tokens=len(response_text) // 4,
                total_tokens=(len(prompt_text) + len(response_text)) // 4,
            ),
            latency_seconds=0.1,
        )

    def close(self) -> None:
        """No-op (no real connection)."""
        pass

    def _find_response(self, prompt: str) -> str:
        """Find response matching prompt content."""
        prompt_lower = prompt.lower()

        # Check pattern responses
        for pattern, response in self._pattern_responses:
            if pattern.lower() in prompt_lower:
                return response

        # Check keyed responses
        for key, response in self._responses.items():
            if key.lower() in prompt_lower:
                return response

        return self._default_response

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def calls(self) -> list[MockCall]:
        return self._calls

    @property
    def last_call(self) -> MockCall | None:
        return self._calls[-1] if self._calls else None

    def reset(self) -> None:
        """Clear all recorded calls."""
        self._calls = []
        self._fail_count = 0
        self._fail_next = None


class MockRouter:
    """
    Fake 9Router that returns predetermined routing decisions.

    Doesn't read config files. Returns fixed model selections.
    """

    def __init__(self, default_model: str = "mock/test-model"):
        self._default_model = default_model
        self._usage_records: list[dict] = []

    def route(self, **kwargs):
        """Return a fixed routing decision."""
        from factory.router.policy import RoutingDecision
        return RoutingDecision(
            model_key="mock-model",
            model_id=self._default_model,
            max_tokens=4096,
            temperature=0.1,
            reason="mock routing",
        )

    def record_usage(self, **kwargs) -> None:
        """Record usage (no-op for testing)."""
        self._usage_records.append(kwargs)

    def get_budget_status(self):
        """Return healthy budget."""
        from factory.router.cost import BudgetStatus
        return BudgetStatus(
            spent_today_usd=0.0,
            daily_limit_usd=50.0,
            remaining_usd=50.0,
            pct_used=0.0,
            should_alert=False,
            should_downgrade=False,
            should_queue=False,
            critical_only=False,
        )

    @classmethod
    def from_config(cls, path: str = "") -> "MockRouter":
        return cls()
