# OpenRouter gateway client.
"""
OpenRouter gateway — thin HTTP wrapper for LLM API calls.

Handles: auth, retry, timeout, response parsing, usage tracking.
Does NOT: route, decide models, store context, orchestrate.

Usage:
    from factory.gateway import GatewayClient, CompletionRequest, Message

    client = GatewayClient()
    response = client.complete(CompletionRequest(
        model="anthropic/claude-sonnet-4.6",
        messages=[Message(role="user", content="Hello")],
    ))
"""

from .client import GatewayClient, GatewayConfigError, GatewayRequestError
from .models import CompletionRequest, CompletionResponse, GatewayError, Message, Usage
from .retry import RetryConfig, RetryStrategy

__all__ = [
    "GatewayClient",
    "GatewayConfigError",
    "GatewayRequestError",
    "CompletionRequest",
    "CompletionResponse",
    "Message",
    "Usage",
    "GatewayError",
    "RetryConfig",
    "RetryStrategy",
]
