# 9Router intelligent model selection.
"""
9Router — deterministic intelligent model routing.

Combines:
    - Policy: task_type → model (rule-based, no LLM)
    - Fallback: failed model → next in chain (cross-provider)
    - Cost: budget enforcement + graceful degradation
    - Timeout: per-model + per-task timeout resolution

Usage:
    from factory.router import NineRouter

    router = NineRouter.from_config("config/router.yaml")
    result = router.route(task_type="coding", complexity="high")
    # result.model_id = "anthropic/claude-sonnet-4.6"
    # result.timeout_seconds = 60
"""

from .cost import BudgetStatus, CostConfig, CostTracker
from .fallback import FallbackDecision, FallbackManager
from .policy import ModelInfo, RoutingDecision, RoutingPolicy, RoutingRule
from .router import NineRouter, RouteResult

__all__ = [
    "NineRouter",
    "RouteResult",
    "RoutingPolicy",
    "RoutingRule",
    "RoutingDecision",
    "ModelInfo",
    "FallbackManager",
    "FallbackDecision",
    "CostTracker",
    "CostConfig",
    "BudgetStatus",
]
