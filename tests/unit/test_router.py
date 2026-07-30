"""
Tests for 9Router + OpenRouter integration.

Tests routing policy, fallback chains, cost tracking, retry strategy,
and the combined NineRouter orchestrator.
"""

from __future__ import annotations

import pytest

from factory.gateway.models import CompletionRequest, GatewayError, Message, Usage
from factory.gateway.retry import RetryConfig, RetryStrategy
from factory.router.cost import CostConfig, CostTracker
from factory.router.fallback import FallbackManager
from factory.router.policy import ModelInfo, RoutingPolicy, RoutingRule
from factory.router.router import NineRouter


# --- Fixtures ---


@pytest.fixture
def catalog() -> dict[str, ModelInfo]:
    return {
        "gpt-5": ModelInfo(key="gpt-5", id="openai/gpt-5", provider="openai",
                           context_window=256000, cost_per_1k_input=0.01, cost_per_1k_output=0.03,
                           latency_class="normal", strengths=["architecture"]),
        "claude-sonnet-latest": ModelInfo(key="claude-sonnet-latest", id="anthropic/claude-sonnet-4.6",
                                          provider="anthropic", context_window=200000,
                                          cost_per_1k_input=0.004, cost_per_1k_output=0.020,
                                          latency_class="normal", strengths=["coding"]),
        "claude-sonnet": ModelInfo(key="claude-sonnet", id="anthropic/claude-sonnet-4",
                                   provider="anthropic", context_window=200000,
                                   cost_per_1k_input=0.003, cost_per_1k_output=0.015,
                                   latency_class="normal", strengths=["coding", "review"]),
        "gemini-pro": ModelInfo(key="gemini-pro", id="google/gemini-2.5-pro",
                                provider="google", context_window=1048576,
                                cost_per_1k_input=0.00125, cost_per_1k_output=0.01,
                                latency_class="normal", strengths=["documentation"]),
        "deepseek-chat": ModelInfo(key="deepseek-chat", id="deepseek/deepseek-chat-v3",
                                   provider="deepseek", context_window=128000,
                                   cost_per_1k_input=0.0002, cost_per_1k_output=0.0006,
                                   latency_class="fast", strengths=["batch"]),
    }


@pytest.fixture
def policy(catalog) -> RoutingPolicy:
    rules = [
        RoutingRule(match={"task_type": "architecture"}, model="gpt-5", max_tokens=8192, temperature=0.2),
        RoutingRule(match={"task_type": "planning"}, model="gpt-5", max_tokens=8192, temperature=0.3),
        RoutingRule(match={"task_type": "coding"}, model="claude-sonnet-latest", max_tokens=8192, temperature=0.1),
        RoutingRule(match={"task_type": "review"}, model="claude-sonnet", max_tokens=4096, temperature=0.0),
        RoutingRule(match={"task_type": "documentation"}, model="gemini-pro", max_tokens=8192, temperature=0.3),
        RoutingRule(match={"task_type": "classification"}, model="deepseek-chat", max_tokens=32, temperature=0.0),
        RoutingRule(match={"task_type": "batch"}, model="deepseek-chat", max_tokens=2048, temperature=0.0),
    ]
    return RoutingPolicy(rules=rules, catalog=catalog, default_model="claude-sonnet")


@pytest.fixture
def fallback_chains() -> dict[str, list[str]]:
    return {
        "gpt-5": ["claude-sonnet-latest", "gemini-pro", "deepseek-chat"],
        "claude-sonnet-latest": ["claude-sonnet", "gpt-5", "deepseek-chat"],
        "claude-sonnet": ["claude-sonnet-latest", "deepseek-chat"],
        "gemini-pro": ["claude-sonnet", "deepseek-chat"],
        "deepseek-chat": ["claude-sonnet", "gemini-pro"],
    }


# --- Policy Tests ---


class TestRoutingPolicy:
    def test_architecture_routes_to_gpt5(self, policy):
        decision = policy.route(task_type="architecture")
        assert decision.model_key == "gpt-5"
        assert decision.model_id == "openai/gpt-5"

    def test_planning_routes_to_gpt5(self, policy):
        decision = policy.route(task_type="planning")
        assert decision.model_key == "gpt-5"

    def test_coding_routes_to_claude(self, policy):
        decision = policy.route(task_type="coding")
        assert decision.model_key == "claude-sonnet-latest"
        assert decision.model_id == "anthropic/claude-sonnet-4.6"

    def test_documentation_routes_to_gemini(self, policy):
        decision = policy.route(task_type="documentation")
        assert decision.model_key == "gemini-pro"
        assert decision.model_id == "google/gemini-2.5-pro"

    def test_batch_routes_to_deepseek(self, policy):
        decision = policy.route(task_type="batch")
        assert decision.model_key == "deepseek-chat"
        assert decision.model_id == "deepseek/deepseek-chat-v3"

    def test_classification_routes_to_deepseek(self, policy):
        decision = policy.route(task_type="classification")
        assert decision.model_key == "deepseek-chat"
        assert decision.max_tokens == 32

    def test_unknown_task_uses_default(self, policy):
        decision = policy.route(task_type="unknown_task_xyz")
        assert decision.model_key == "claude-sonnet"
        assert decision.rule_index == -1

    def test_deterministic(self, policy):
        """Same input always produces same output."""
        results = [policy.route(task_type="coding") for _ in range(10)]
        assert all(r.model_key == "claude-sonnet-latest" for r in results)

    def test_temperature_per_task(self, policy):
        arch = policy.route(task_type="architecture")
        review = policy.route(task_type="review")
        assert arch.temperature == 0.2
        assert review.temperature == 0.0


# --- Fallback Tests ---


class TestFallback:
    def test_first_fallback(self, catalog, fallback_chains):
        mgr = FallbackManager(fallback_chains, catalog)
        result = mgr.get_next("gpt-5", attempt=1, error_reason="rate limited")
        assert result is not None
        assert result.model_key == "claude-sonnet-latest"
        assert result.attempt == 1

    def test_second_fallback(self, catalog, fallback_chains):
        mgr = FallbackManager(fallback_chains, catalog)
        result = mgr.get_next("gpt-5", attempt=2)
        assert result is not None
        assert result.model_key == "gemini-pro"

    def test_third_fallback(self, catalog, fallback_chains):
        mgr = FallbackManager(fallback_chains, catalog)
        result = mgr.get_next("gpt-5", attempt=3)
        assert result is not None
        assert result.model_key == "deepseek-chat"

    def test_exhausted_returns_none(self, catalog, fallback_chains):
        mgr = FallbackManager(fallback_chains, catalog, max_attempts=3)
        result = mgr.get_next("gpt-5", attempt=4)
        assert result is None

    def test_cross_provider_fallback(self, catalog, fallback_chains):
        """Fallback chain crosses providers for resilience."""
        mgr = FallbackManager(fallback_chains, catalog)
        chain = mgr.get_full_chain("gpt-5")
        providers = [catalog[k].provider for k in chain if k in catalog]
        # Should have at least 2 different providers
        assert len(set(providers)) >= 2


# --- Retry Tests ---


class TestRetryStrategy:
    def test_retry_on_429(self):
        strategy = RetryStrategy()
        assert strategy.should_retry(attempt=1, status_code=429) is True

    def test_retry_on_500(self):
        strategy = RetryStrategy()
        assert strategy.should_retry(attempt=1, status_code=500) is True

    def test_no_retry_on_400(self):
        strategy = RetryStrategy()
        assert strategy.should_retry(attempt=1, status_code=400) is False

    def test_no_retry_on_401(self):
        strategy = RetryStrategy()
        assert strategy.should_retry(attempt=1, status_code=401) is False

    def test_no_retry_after_max_attempts(self):
        strategy = RetryStrategy(RetryConfig(max_attempts=3))
        assert strategy.should_retry(attempt=3, status_code=429) is False

    def test_exponential_backoff(self):
        strategy = RetryStrategy(RetryConfig(
            base_delay_ms=1000, multiplier=2.0, jitter=False
        ))
        assert strategy.get_delay_ms(1) == 1000
        assert strategy.get_delay_ms(2) == 2000
        assert strategy.get_delay_ms(3) == 4000

    def test_max_delay_cap(self):
        strategy = RetryStrategy(RetryConfig(
            base_delay_ms=1000, multiplier=2.0, max_delay_ms=5000, jitter=False
        ))
        # attempt 4 would be 8000, but capped at 5000
        assert strategy.get_delay_ms(4) == 5000

    def test_jitter_adds_variance(self):
        strategy = RetryStrategy(RetryConfig(
            base_delay_ms=1000, multiplier=1.0, jitter=True, jitter_factor=0.2
        ))
        delays = [strategy.get_delay_ms(1) for _ in range(20)]
        # With jitter, not all delays should be identical
        assert len(set(delays)) > 1


# --- Cost Tests ---


class TestCostTracker:
    def test_calculate_cost(self, catalog, tmp_path):
        config = CostConfig(ledger_path=str(tmp_path / "ledger.jsonl"))
        tracker = CostTracker(config, catalog)

        # Claude sonnet: 0.003/1K input + 0.015/1K output
        cost = tracker.estimate_cost("claude-sonnet", input_tokens=1000, output_tokens=500)
        expected = (1000 / 1000 * 0.003) + (500 / 1000 * 0.015)
        assert abs(cost - expected) < 0.0001

    def test_budget_status_fresh(self, catalog, tmp_path):
        config = CostConfig(daily_limit_usd=50.0, ledger_path=str(tmp_path / "ledger.jsonl"))
        tracker = CostTracker(config, catalog)
        status = tracker.get_budget_status()
        assert status.spent_today_usd == 0.0
        assert status.pct_used == 0.0
        assert not status.should_downgrade

    def test_record_and_track(self, catalog, tmp_path):
        config = CostConfig(daily_limit_usd=50.0, ledger_path=str(tmp_path / "ledger.jsonl"))
        tracker = CostTracker(config, catalog)
        tracker.record("claude-sonnet", 5000, 2000, task_id="TASK-001")
        status = tracker.get_budget_status()
        assert status.spent_today_usd > 0
        assert status.total_calls_today == 1

    def test_downgrade_map(self, catalog, tmp_path):
        config = CostConfig(ledger_path=str(tmp_path / "ledger.jsonl"))
        tracker = CostTracker(config, catalog)
        assert tracker.get_downgrade("gpt-5") == "claude-sonnet-latest"
        assert tracker.get_downgrade("claude-sonnet-latest") == "claude-sonnet"
        assert tracker.get_downgrade("deepseek-chat") is None


# --- NineRouter Integration ---


class TestNineRouter:
    def test_from_config(self, factory_root):
        """Test loading router from YAML config."""
        config_path = factory_root / "config" / "router.yaml"
        if not config_path.exists():
            pytest.skip("router.yaml not available")

        router = NineRouter.from_config(str(config_path))
        assert router.policy.rule_count > 0

    def test_route_coding(self, policy, catalog, fallback_chains, tmp_path):
        fallback = FallbackManager(fallback_chains, catalog)
        cost = CostTracker(CostConfig(ledger_path=str(tmp_path / "l.jsonl")), catalog)
        router = NineRouter(policy=policy, fallback=fallback, cost_tracker=cost)

        result = router.route(task_type="coding")
        assert result.model_id == "anthropic/claude-sonnet-4.6"
        assert result.timeout_seconds == 60.0  # Default

    def test_route_with_timeout_override(self, policy, catalog, fallback_chains, tmp_path):
        fallback = FallbackManager(fallback_chains, catalog)
        cost = CostTracker(CostConfig(ledger_path=str(tmp_path / "l.jsonl")), catalog)
        router = NineRouter(
            policy=policy, fallback=fallback, cost_tracker=cost,
            task_timeout_config={"classification": 15.0},
        )

        result = router.route(task_type="classification")
        assert result.timeout_seconds == 15.0
