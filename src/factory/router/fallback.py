"""
Fallback Chain Manager.

When a primary model fails (provider outage, rate limit exhausted),
the fallback manager provides the next model to try.

Each model has a pre-configured fallback chain:
    GPT-5 → Claude → Gemini → DeepSeek
    Claude → Claude-older → GPT-5 → DeepSeek
    etc.

Fallback chains use different providers to survive provider-level outages.

Usage:
    fallback = FallbackManager(chains, catalog)
    next_model = fallback.get_next("gpt-5", attempt=1)
    next_model = fallback.get_next("gpt-5", attempt=2)
"""

from __future__ import annotations

from dataclasses import dataclass

from .policy import ModelInfo


@dataclass
class FallbackDecision:
    """Result of a fallback decision."""

    model_key: str              # Fallback model catalog key
    model_id: str               # Full model ID
    attempt: int                # Which fallback this is (1, 2, 3)
    reason: str                 # Why we're falling back
    original_model: str         # What we originally tried


class FallbackManager:
    """
    Manages fallback chains for model failures.

    When a model fails, provides the next model in the chain.
    Chains are configured to use different providers for resilience.

    Exhausted chains return None (escalate to human).
    """

    def __init__(
        self,
        chains: dict[str, list[str]],
        catalog: dict[str, ModelInfo],
        max_attempts: int = 3,
    ):
        """
        Args:
            chains: model_key → [fallback_key_1, fallback_key_2, ...]
            catalog: model_key → ModelInfo for ID resolution
            max_attempts: Maximum fallback attempts before giving up
        """
        self.chains = chains
        self.catalog = catalog
        self.max_attempts = max_attempts

    def get_next(
        self,
        failed_model: str,
        attempt: int,
        error_reason: str = "",
    ) -> FallbackDecision | None:
        """
        Get the next fallback model after a failure.

        Args:
            failed_model: Model key that failed.
            attempt: Which fallback attempt this is (1-based).
            error_reason: Why the previous model failed.

        Returns:
            FallbackDecision with next model, or None if chain exhausted.
        """
        chain = self.chains.get(failed_model, [])

        if attempt > self.max_attempts or attempt > len(chain):
            return None  # Chain exhausted

        # Get the fallback at this position (0-indexed from attempt)
        fallback_key = chain[attempt - 1]
        model_info = self.catalog.get(fallback_key)

        if not model_info:
            return None  # Fallback model not in catalog

        return FallbackDecision(
            model_key=fallback_key,
            model_id=model_info.id,
            attempt=attempt,
            reason=f"Fallback #{attempt} for '{failed_model}': {error_reason}",
            original_model=failed_model,
        )

    def get_full_chain(self, model_key: str) -> list[str]:
        """
        Get the complete fallback chain for a model (including self).

        Returns: [primary, fallback_1, fallback_2, fallback_3]
        """
        chain = self.chains.get(model_key, [])
        return [model_key] + chain[:self.max_attempts]

    def has_fallback(self, model_key: str) -> bool:
        """Check if a model has any fallback configured."""
        return model_key in self.chains and len(self.chains[model_key]) > 0

    def get_cheapest_in_chain(self, model_key: str) -> str | None:
        """
        Get the cheapest model in a fallback chain.
        Useful for budget-constrained routing.
        """
        chain = self.get_full_chain(model_key)
        cheapest: str | None = None
        cheapest_cost = float("inf")

        for key in chain:
            info = self.catalog.get(key)
            if info:
                total_cost = info.cost_per_1k_input + info.cost_per_1k_output
                if total_cost < cheapest_cost:
                    cheapest_cost = total_cost
                    cheapest = key

        return cheapest
