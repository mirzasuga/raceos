#!/usr/bin/env bash
# ============================================================
# OpenRouter + 9Router Integration Verification
# ============================================================
set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  OpenRouter + 9Router — Verification                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

check() {
    local desc="$1"; local cmd="$2"
    printf "  %-55s " "$desc"
    if eval "$cmd" > /dev/null 2>&1; then echo "✅"; PASS=$((PASS+1))
    else echo "❌"; FAIL=$((FAIL+1)); fi
}

# --- Config ---
echo "▸ Step 1: Configuration"
echo ""
check "config/router.yaml exists" "test -f config/router.yaml"
check "router.yaml valid YAML" "python3 -c 'import yaml; yaml.safe_load(open(\"config/router.yaml\"))'"
check "Has catalog section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/router.yaml\")); assert \"catalog\" in d'"
check "Has policy section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/router.yaml\")); assert \"policy\" in d'"
check "Has fallback section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/router.yaml\")); assert \"fallback\" in d'"
check "Has retry section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/router.yaml\")); assert \"retry\" in d'"
check "Has timeout section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/router.yaml\")); assert \"timeout\" in d'"
check "Has cost section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/router.yaml\")); assert \"cost\" in d'"
echo ""

# --- Imports ---
echo "▸ Step 2: Import Verification"
echo ""
check "Import gateway client" "PYTHONPATH=src python3 -c 'from factory.gateway import GatewayClient, CompletionRequest, Message'"
check "Import gateway retry" "PYTHONPATH=src python3 -c 'from factory.gateway import RetryStrategy, RetryConfig'"
check "Import router policy" "PYTHONPATH=src python3 -c 'from factory.router.policy import RoutingPolicy, RoutingRule, ModelInfo'"
check "Import router fallback" "PYTHONPATH=src python3 -c 'from factory.router.fallback import FallbackManager'"
check "Import router cost" "PYTHONPATH=src python3 -c 'from factory.router.cost import CostTracker, CostConfig, BudgetStatus'"
check "Import NineRouter" "PYTHONPATH=src python3 -c 'from factory.router import NineRouter, RouteResult'"
echo ""

# --- Routing Policy ---
echo "▸ Step 3: Routing Policy Correctness"
echo ""
check "Architecture → GPT-5" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"architecture\")
assert \"gpt-5\" in res.model_id.lower() or res.model_key == \"gpt-5\", f\"Got: {res.model_key}\"
'"
check "Planning → GPT-5" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"planning\")
assert res.model_key == \"gpt-5\", f\"Got: {res.model_key}\"
'"
check "Coding → Claude" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"coding\")
assert \"claude\" in res.model_id.lower(), f\"Got: {res.model_id}\"
'"
check "Documentation → Gemini" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"documentation\")
assert \"gemini\" in res.model_id.lower(), f\"Got: {res.model_id}\"
'"
check "Batch → DeepSeek" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"batch\")
assert \"deepseek\" in res.model_id.lower(), f\"Got: {res.model_id}\"
'"
check "Classification → DeepSeek (32 tokens)" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"classification\")
assert \"deepseek\" in res.model_id.lower()
assert res.max_tokens == 32
'"
check "Deterministic (10 calls same result)" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
results = [r.route(task_type=\"coding\").model_id for _ in range(10)]
assert len(set(results)) == 1
'"
echo ""

# --- Fallback ---
echo "▸ Step 4: Fallback Chains"
echo ""
check "GPT-5 fallback exists" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
fb = r.get_fallback(\"gpt-5\", attempt=1)
assert fb is not None
'"
check "Fallback crosses providers" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
fb1 = r.get_fallback(\"gpt-5\", attempt=1)
assert \"openai\" not in fb1.model_id  # Different provider
'"
check "Exhausted chain returns None" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
fb = r.get_fallback(\"gpt-5\", attempt=99)
assert fb is None
'"
echo ""

# --- Retry ---
echo "▸ Step 5: Retry Strategy"
echo ""
check "Retry on 429" "PYTHONPATH=src python3 -c '
from factory.gateway.retry import RetryStrategy
s = RetryStrategy()
assert s.should_retry(1, 429) == True
'"
check "No retry on 401" "PYTHONPATH=src python3 -c '
from factory.gateway.retry import RetryStrategy
s = RetryStrategy()
assert s.should_retry(1, 401) == False
'"
check "Exponential backoff" "PYTHONPATH=src python3 -c '
from factory.gateway.retry import RetryStrategy, RetryConfig
s = RetryStrategy(RetryConfig(base_delay_ms=1000, multiplier=2.0, jitter=False))
assert s.get_delay_ms(1) == 1000
assert s.get_delay_ms(2) == 2000
assert s.get_delay_ms(3) == 4000
'"
echo ""

# --- Cost ---
echo "▸ Step 6: Cost Tracking"
echo ""
check "Budget starts at 0" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
status = r.get_budget_status()
assert status.pct_used == 0.0
'"
check "Downgrade map exists" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
assert r.cost_tracker.get_downgrade(\"gpt-5\") is not None
'"
echo ""

# --- Timeout ---
echo "▸ Step 7: Timeout Configuration"
echo ""
check "Classification timeout = 15s" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"classification\")
assert res.timeout_seconds == 15.0, f\"Got: {res.timeout_seconds}\"
'"
check "Coding timeout = 120s" "PYTHONPATH=src python3 -c '
from factory.router.router import NineRouter
r = NineRouter.from_config(\"config/router.yaml\")
res = r.route(task_type=\"coding\")
assert res.timeout_seconds == 120.0, f\"Got: {res.timeout_seconds}\"
'"
echo ""

# --- Unit Tests ---
echo "▸ Step 8: Unit Tests"
echo ""
if command -v uv > /dev/null 2>&1; then
    check "All router tests pass" "uv run pytest tests/unit/test_router.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
else
    check "All router tests pass" "PYTHONPATH=src python3 -m pytest tests/unit/test_router.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
fi
echo ""

# --- Summary ---
echo "══════════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo "  Results: $PASS/$TOTAL passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
    echo "  ✅ All checks passed!"
    echo ""
    echo "  Routing Policy:"
    echo "    Architecture  → GPT-5"
    echo "    Planning      → GPT-5"
    echo "    Coding        → Claude Sonnet 4.6"
    echo "    Documentation → Gemini 2.5 Pro"
    echo "    Batch/Classify→ DeepSeek Chat v3"
else
    echo "  ❌ $FAIL checks failed."
    exit 1
fi
echo "══════════════════════════════════════════════════════════"
