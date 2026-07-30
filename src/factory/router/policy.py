"""
Routing Policy Engine.

Deterministic rule-based routing: task_type → model selection.
No LLM involved. Rules evaluated top-to-bottom, first match wins.

Policy assignments (from config/router.yaml):
    Architecture → GPT-5
    Planning → GPT-5
    Coding → Claude
    Documentation → Gemini
    Cheap batch → DeepSeek

Usage:
    policy = RoutingPolicy(rules)
    decision = policy.route(task_type="coding", complexity="high")
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RoutingRule:
    """A single routing rule: condition → model selection."""

    match: dict[str, str]       # Conditions to match (task_type, complexity, etc.)
    model: str                  # Catalog key (e.g., "claude-sonnet-latest")
    max_tokens: int = 4096
    temperature: float = 0.1
    reason: str = ""            # Why this model was chosen


@dataclass
class RoutingDecision:
    """Result of policy evaluation."""

    model_key: str              # Catalog key (e.g., "claude-sonnet-latest")
    model_id: str               # Full model ID (e.g., "anthropic/claude-sonnet-4.6")
    max_tokens: int
    temperature: float
    reason: str
    rule_index: int = -1        # Which rule matched (-1 = default)


@dataclass
class ModelInfo:
    """Model metadata from catalog."""

    key: str                    # Short key (e.g., "claude-sonnet")
    id: str                     # Full ID (e.g., "anthropic/claude-sonnet-4")
    provider: str
    context_window: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    latency_class: str
    strengths: list[str] = field(default_factory=list)


class RoutingPolicy:
    """
    Deterministic routing policy engine.

    Evaluates rules top-to-bottom against task metadata.
    First matching rule determines the model.
    If no rule matches, uses default.

    This is 9Router's brain — no LLM needed.
    """

    def __init__(
        self,
        rules: list[RoutingRule],
        catalog: dict[str, ModelInfo],
        default_model: str = "claude-sonnet",
        default_max_tokens: int = 4096,
        default_temperature: float = 0.1,
    ):
        self.rules = rules
        self.catalog = catalog
        self.default_model = default_model
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature

    def route(self, **metadata) -> RoutingDecision:
        """
        Route a task to a model based on metadata.

        Metadata keys can include:
            - task_type: str (coding, architecture, planning, etc.)
            - complexity: str (low, medium, high, critical)
            - domain: str (firmware, mobile, backend)
            - quality_req: str (draft, production, safety)

        Returns:
            RoutingDecision with selected model and parameters.
        """
        for i, rule in enumerate(self.rules):
            if self._matches(rule, metadata):
                model_info = self.catalog.get(rule.model)
                model_id = model_info.id if model_info else rule.model

                return RoutingDecision(
                    model_key=rule.model,
                    model_id=model_id,
                    max_tokens=rule.max_tokens,
                    temperature=rule.temperature,
                    reason=rule.reason,
                    rule_index=i,
                )

        # No rule matched — use default
        default_info = self.catalog.get(self.default_model)
        return RoutingDecision(
            model_key=self.default_model,
            model_id=default_info.id if default_info else self.default_model,
            max_tokens=self.default_max_tokens,
            temperature=self.default_temperature,
            reason="No routing rule matched; using default",
            rule_index=-1,
        )

    def _matches(self, rule: RoutingRule, metadata: dict) -> bool:
        """
        Check if all conditions in a rule match the metadata.

        All conditions must match (AND logic).
        Missing metadata keys don't match.
        """
        for key, expected in rule.match.items():
            actual = metadata.get(key)
            if actual is None:
                return False

            # Support list matching (e.g., complexity: ["medium", "high"])
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            else:
                if actual != expected:
                    return False

        return True

    def get_model_info(self, model_key: str) -> ModelInfo | None:
        """Look up model metadata by catalog key."""
        return self.catalog.get(model_key)

    @property
    def rule_count(self) -> int:
        """Number of routing rules configured."""
        return len(self.rules)
