# HTTP transport layer (internal to 9Router).
"""
HTTP client for LLM API calls.

This is an implementation detail of 9Router's gateway function.
It handles: HTTP transport, retry with backoff, response parsing.

No other module should use this directly. Use factory.services.call_llm() instead.

Usage (internal to services.py only):
    from factory.gateway import GatewayClient, CompletionRequest, Message

    client = GatewayClient(api_key=key, base_url=url)
    response = client.complete(CompletionRequest(...))
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
