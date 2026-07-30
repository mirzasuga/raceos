# Gateway

> Thin HTTP wrapper for OpenRouter API with auth, retry, and metrics.

## Responsibility

Provides a minimal HTTP client for communicating with OpenRouter. Handles authentication (API key injection), automatic retries with backoff, request/response metrics collection, and exposes an OpenAI-compatible API interface. This is a pure transport layer.

## Does NOT

- Route or decide which model to use (that is Router's job)
- Interpret task metadata or context
- Make any intelligent decisions about requests
- Cache responses or manage conversation state

## Key Files (planned)

- `client.py` — async HTTP client with retry logic
- `auth.py` — API key management and header injection
- `metrics.py` — request latency, token usage, cost tracking
- `types.py` — request/response dataclasses (OpenAI-compatible)

## Dependencies

- `httpx` (async HTTP)
- `factory.config` (API keys, retry settings)
