"""
9Router — Intelligent Model Router.

The central routing component that combines:
    - Policy: task_type → model selection (deterministic)
    - Fallback: failed model → next model in chain
    - Cost: budget enforcement + degradation
    - Timeout: per-model/task timeout configuration

9Router is the ONLY component that decides which model to use.
OpenRouter (gateway) is a dumb pipe that executes the decision.

Key design:
    - Deterministic: same input → same output (no LLM for routing)
    - Budget-aware: degrades gracefully approaching limit
    - Resilient: automatic fallback on provider failures
    - Auditable: every decision is logged with reason

Usage:
    router = NineRouter.from_config("config/router.yaml")
    decision = router.route(task_type="coding", complexity="high")
    # decision.model_id = "anthropic/claude-sonnet-4.6"
    # decision.max_tokens = 8192
    # decision.timeout = 60

    # On failure:
    fallback = router.get_fallback("claude-sonnet-latest", attempt=1)
    # fallback.model_id = "anthropic/claude-sonnet-4"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .cost import BudgetStatus, CostConfig, CostTracker
from .fallback import FallbackDecision, FallbackManager
from .policy import ModelInfo, RoutingDecision, RoutingPolicy, RoutingRule


@dataclass
class RouteResult:
    """Complete routing result combining policy + cost + timeout."""

    # Model selection
    model_key: str
    model_id: str
    max_tokens: int
    temperature: float

    # Timeout
    timeout_seconds: float

    # Metadata
    reason: str
    was_downgraded: bool = False
    original_model: str = ""

    # Budget snapshot
    budget_pct_used: float = 0.0
    estimated_cost_usd: float = 0.0


class NineRouter:
    """
    9Router — Intelligent Model Routing Engine.

    Combines routing policy, fallback chains, cost tracking,
    and timeout configuration into a single route() call.

    The orchestrator calls route() and gets back everything
    needed to make a gateway call: model, tokens, temp, timeout.
    """

    def __init__(
        self,
        policy: RoutingPolicy,
        fallback: FallbackManager,
        cost_tracker: CostTracker,
        timeout_config: dict[str, float] | None = None,
        task_timeout_config: dict[str, float] | None = None,
    ):
        self.policy = policy
        self.fallback = fallback
        self.cost_tracker = cost_tracker
        self.timeout_config = timeout_config or {}
        self.task_timeout_config = task_timeout_config or {}

    def route(self, **metadata) -> RouteResult:
        """
        Route a task to the optimal model.

        Applies (in order):
        1. Policy rules → select primary model
        2. Budget check → downgrade if over threshold
        3. Timeout resolution → per-model or per-task

        Args:
            task_type: str — type of task
            complexity: str — low/medium/high/critical (optional)
            domain: str — firmware/mobile/backend (optional)
            quality_req: str — draft/production/safety (optional)

        Returns:
            RouteResult with model, tokens, temp, timeout, budget info.
        """
        # 1. Apply routing policy
        decision = self.policy.route(**metadata)

        # 2. Check budget
        budget = self.cost_tracker.get_budget_status()
        was_downgraded = False
        original_model = ""

        if budget.should_downgrade and metadata.get("quality_req") != "safety":
            # Downgrade to cheaper model
            downgraded = self.cost_tracker.get_downgrade(decision.model_key)
            if downgraded:
                original_model = decision.model_key
                info = self.policy.get_model_info(downgraded)
                decision = RoutingDecision(
                    model_key=downgraded,
                    model_id=info.id if info else downgraded,
                    max_tokens=decision.max_tokens,
                    temperature=decision.temperature,
                    reason=f"Budget downgrade: {decision.model_key} → {downgraded} ({budget.pct_used:.0f}% used)",
                )
                was_downgraded = True

        # 3. Resolve timeout
        task_type = metadata.get("task_type", "")
        timeout = self._resolve_timeout(decision.model_key, task_type)

        # 4. Estimate cost for this call
        estimated_input = decision.max_tokens  # Rough estimate
        estimated_cost = self.cost_tracker.estimate_cost(
            decision.model_key, estimated_input, decision.max_tokens // 2
        )

        return RouteResult(
            model_key=decision.model_key,
            model_id=decision.model_id,
            max_tokens=decision.max_tokens,
            temperature=decision.temperature,
            timeout_seconds=timeout,
            reason=decision.reason,
            was_downgraded=was_downgraded,
            original_model=original_model,
            budget_pct_used=budget.pct_used,
            estimated_cost_usd=estimated_cost,
        )

    def get_fallback(
        self, failed_model: str, attempt: int, error: str = ""
    ) -> FallbackDecision | None:
        """
        Get fallback model after a failure.

        Called by the orchestrator when a gateway call fails.

        Args:
            failed_model: Model key that failed.
            attempt: Which fallback attempt (1, 2, 3).
            error: Error message for logging.

        Returns:
            FallbackDecision with next model, or None if exhausted.
        """
        return self.fallback.get_next(failed_model, attempt, error)

    def record_usage(
        self,
        model_key: str,
        input_tokens: int,
        output_tokens: int,
        task_id: str = "",
        task_type: str = "",
    ) -> None:
        """Record token usage for cost tracking (call after successful completion)."""
        self.cost_tracker.record(
            model_key=model_key,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            task_id=task_id,
            task_type=task_type,
        )

    def get_budget_status(self) -> BudgetStatus:
        """Get current budget snapshot."""
        return self.cost_tracker.get_budget_status()

    def _resolve_timeout(self, model_key: str, task_type: str) -> float:
        """
        Resolve timeout: task-type override > model default > global default.

        Priority:
        1. Task-type specific timeout (e.g., classification: 15s)
        2. Model-specific timeout (e.g., deepseek-chat: 30s)
        3. Global default (60s)
        """
        # Task-type override (highest priority)
        if task_type in self.task_timeout_config:
            return self.task_timeout_config[task_type]

        # Model-specific timeout
        if model_key in self.timeout_config:
            return self.timeout_config[model_key]

        # Global default
        return 60.0

    # --- Factory Method ---

    @classmethod
    def from_config(cls, config_path: str = "config/router.yaml") -> "NineRouter":
        """
        Build a NineRouter from YAML configuration.

        Parses config/router.yaml and constructs all sub-components:
        policy, fallback, cost tracker, timeouts.

        Args:
            config_path: Path to router.yaml.

        Returns:
            Fully configured NineRouter instance.
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Router config not found: {config_path}")

        with open(config_file) as f:
            config = yaml.safe_load(f)

        # Build catalog
        catalog: dict[str, ModelInfo] = {}
        for key, model_data in config.get("catalog", {}).items():
            catalog[key] = ModelInfo(
                key=key,
                id=model_data["id"],
                provider=model_data["provider"],
                context_window=model_data["context_window"],
                cost_per_1k_input=model_data["cost_per_1k_input"],
                cost_per_1k_output=model_data["cost_per_1k_output"],
                latency_class=model_data.get("latency_class", "normal"),
                strengths=model_data.get("strengths", []),
            )

        # Build routing rules
        rules: list[RoutingRule] = []
        policy_config = config.get("policy", {})
        for rule_data in policy_config.get("rules", []):
            rules.append(RoutingRule(
                match=rule_data["match"],
                model=rule_data["model"],
                max_tokens=rule_data.get("max_tokens", 4096),
                temperature=rule_data.get("temperature", 0.1),
                reason=rule_data.get("reason", ""),
            ))

        default = policy_config.get("default", {})
        policy = RoutingPolicy(
            rules=rules,
            catalog=catalog,
            default_model=default.get("model", "claude-sonnet"),
            default_max_tokens=default.get("max_tokens", 4096),
            default_temperature=default.get("temperature", 0.1),
        )

        # Build fallback chains
        fallback_config = config.get("fallback", {})
        chains = fallback_config.get("chains", {})
        max_fallback = fallback_config.get("max_fallback_attempts", 3)
        fallback_mgr = FallbackManager(chains, catalog, max_fallback)

        # Build cost tracker
        cost_config_data = config.get("cost", {}).get("budget", {})
        cost_config = CostConfig(
            daily_limit_usd=cost_config_data.get("daily_limit_usd", 50.0),
            per_task_limit_usd=cost_config_data.get("per_task_limit_usd", 5.0),
            per_session_limit_usd=cost_config_data.get("per_session_limit_usd", 20.0),
            alert_threshold_pct=cost_config_data.get("alert_threshold_pct", 80.0),
        )

        # Build downgrade map from degradation config
        degradation = config.get("cost", {}).get("degradation", [])
        for rule in degradation:
            if rule.get("action") == "downgrade" and "downgrade_map" in rule:
                cost_config.downgrade_map = rule["downgrade_map"]
                break

        cost_tracker = CostTracker(cost_config, catalog)

        # Build timeout configs
        timeout_data = config.get("timeout", {})
        model_timeouts = {k: float(v) for k, v in timeout_data.get("per_model", {}).items()}
        task_timeouts = {k: float(v) for k, v in timeout_data.get("per_task_type", {}).items()}

        return cls(
            policy=policy,
            fallback=fallback_mgr,
            cost_tracker=cost_tracker,
            timeout_config=model_timeouts,
            task_timeout_config=task_timeouts,
        )
