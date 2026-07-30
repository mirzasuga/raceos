# HTTP Transport (internal to 9Router)

> HTTP client layer — internal implementation detail of 9Router's gateway function.

## Responsibility

Send HTTP requests to LLM providers. Handle retry, backoff, timeouts.

## Does NOT

- Select models (9Router does that)
- Know which provider to use (receives URL from config)
- Store API keys (reads from environment via services.py)
- Decide retry policy (reads from config/router.yaml)
- Make routing decisions
- Track budget

## Key Files

- `client.py` — HTTP client with retry
- `models.py` — Request/Response types
- `retry.py` — Exponential backoff strategy

## Dependencies

- `httpx` (HTTP client)
- `tenacity` (retry logic)

## Usage

**Do not use directly.** All LLM calls go through `factory.services.call_llm()`.
