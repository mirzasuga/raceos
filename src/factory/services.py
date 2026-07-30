"""
Service Container — 9Router as Sole Gateway.

Architecture (simplified):
    CLI → LangGraph → OpenCode → 9Router → LLMs

9Router is the ONLY owner of:
    - API keys
    - Gateway (HTTP transport)
    - Model routing
    - Retry + fallback
    - Timeout
    - Cost/budget

No other module may:
    - Know model names
    - Know provider URLs
    - Know API keys
    - Create HTTP clients to LLM providers
    - Decide retry/fallback
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog
import yaml

log = structlog.get_logger()

# --- Singleton ---
_router = None


def get_router():
    """
    Get the singleton 9Router instance.

    9Router owns ALL of:
    - Model selection (routing policy)
    - HTTP transport (gateway)
    - API key management
    - Retry with backoff
    - Fallback chains
    - Timeout policy
    - Budget enforcement
    """
    global _router
    if _router is None:
        from factory.router.router import NineRouter
        _router = NineRouter.from_config("config/router.yaml")
    return _router


def call_llm(task_type: str, prompt: str, **routing_kwargs) -> str | None:
    """
    The SINGLE entry point for all LLM calls.

    Flow: call_llm() → 9Router selects model → 9Router sends HTTP → LLM responds

    No other module calls LLM providers directly.

    Args:
        task_type: What kind of task (9Router uses this to select model)
        prompt: The full prompt
        **routing_kwargs: Extra routing params (complexity, domain, etc.)

    Returns:
        LLM response text, or None on failure.
    """
    try:
        router = get_router()

        # 9Router decides everything: model, tokens, temperature, timeout
        route = router.route(task_type=task_type, **routing_kwargs)

        # 9Router also owns the HTTP call (via its internal gateway)
        from factory.gateway.models import CompletionRequest, Message
        from factory.gateway.client import GatewayClient

        # Get gateway config from router config (9Router owns this)
        gw = _get_gateway()
        response = gw.complete(CompletionRequest(
            model=route.model_id,
            messages=[Message(role="user", content=prompt)],
            max_tokens=route.max_tokens,
            temperature=route.temperature,
        ))

        # 9Router records cost (sole budget owner)
        router.record_usage(
            model_key=route.model_key,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            task_type=task_type,
        )

        return response.content

    except Exception as e:
        log.warning("services.call_llm_failed", task_type=task_type, error=str(e))
        return None


# --- Internal (gateway is an implementation detail of 9Router) ---

_gateway = None


def _get_gateway():
    """Internal: get HTTP client. This is 9Router's transport layer."""
    global _gateway
    if _gateway is None:
        from factory.gateway.client import GatewayClient

        config_path = Path("config/router.yaml")
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
            gw = config.get("gateway", {})
            base_url = gw.get("base_url", "http://localhost:20128/v1")
            api_key_env = gw.get("api_key_env", "NINE_ROUTER_API_KEY")
        else:
            base_url = "http://localhost:20128/v1"
            api_key_env = "NINE_ROUTER_API_KEY"

        api_key = os.environ.get(api_key_env, "")

        _gateway = GatewayClient(api_key=api_key or "not-set", base_url=base_url)

    return _gateway


def reset():
    """Reset singletons (testing only)."""
    global _router, _gateway
    if _gateway:
        try:
            _gateway.close()
        except Exception:
            pass
    _router = None
    _gateway = None
