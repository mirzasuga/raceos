# SRP Violations Audit & Refactoring Plan

> **Auditor:** Principal Software Architect
> **Date:** 2026-07-30
> **Scope:** Complete codebase SRP review from CLI to LLM invocation

---

## Violations Found: 7 Categories, 14 Instances

---

### Violation 1: Model Names Hardcoded Outside router/

**Locations:**
- `executor/session.py:87` — `model: str = "anthropic/claude-sonnet-4.6"`
- `executor/contracts.py:62` — `model: str = Field(default="anthropic/claude-sonnet-4.6")`
- `spec_engine/generator.py:37` — `model: str = "anthropic/claude-sonnet-4.6"`
- `orchestrator/nodes/engineer.py:105` — fallback `"anthropic/claude-sonnet-4.6"`
- `orchestrator/nodes/orchestrator.py:287,303` — fallback model IDs
- `gateway/__init__.py:13` — docstring example

**Why it violates SRP:** 9Router is the ONLY owner of model selection. If models change (pricing, deprecation, rename), you must hunt across 6+ files.

**Why dangerous:** Model deprecation silently breaks nodes that have stale hardcoded IDs.

**Owner:** `router/` exclusively.

**Refactor:** Replace all hardcoded model IDs with a sentinel `"default"` that means "ask 9Router." Nodes should NEVER know specific model names.

---

### Violation 2: NineRouter.from_config() Called in 5 Nodes

**Locations:**
- `nodes/orchestrator.py:161`
- `nodes/architect.py:138`
- `nodes/reviewer.py:143`
- `nodes/data_telemetry.py:103`
- `orchestrator/planner.py:133`

**Why it violates SRP:** Each node independently loads the router config. If config path changes or router initialization needs parameters, 5 places to update.

**Why dangerous:** Nodes couple to router's initialization details. Testing requires mocking or config files.

**Owner:** A single factory-level DI container (or graph-level shared state).

**Refactor:** Create a shared `_get_router()` singleton and inject into nodes via LangGraph config, OR inject at graph build time.

---

### Violation 3: GatewayClient() Created in 6 Nodes

**Locations:**
- `nodes/orchestrator.py:162`
- `nodes/architect.py:139`
- `nodes/reviewer.py:144`
- `nodes/data_telemetry.py:104`
- `orchestrator/planner.py:134`
- `spec_engine/generator.py:270`

**Why it violates SRP:** Same as #2. Each node creates its own HTTP client. If gateway URL changes or auth changes, 6 places to update.

**Why dangerous:** Multiple client instances = multiple TCP connections = resource waste. Also, each node reads `NINE_ROUTER_API_KEY` independently.

**Owner:** A single gateway instance shared across the workflow.

**Refactor:** Create once at graph invocation time, pass as shared dependency.

---

### Violation 4: Timeout Values Hardcoded in 5 Places

**Locations:**
- `executor/client.py:43` — `default_timeout: int = 300`
- `executor/session.py:93` — `timeout_seconds: int = 300`
- `executor/contracts.py:68` — `timeout_seconds=300`
- `nodes/validator.py:116` — `timeout=120`
- `nodes/engineer.py:109` — `timeout_seconds=300`

**Why it violates SRP:** 9Router owns timeout policy (per-model, per-task-type). Nodes should receive timeout from routing decision.

**Why dangerous:** Timeout in `router.yaml` says 120s for coding, but `engineer.py` hardcodes 300s → config is ignored.

**Owner:** `router/router.py` → `RouteResult.timeout_seconds`

**Refactor:** Nodes read `routing.timeout_seconds` from state. Remove all hardcoded timeouts from executor/nodes.

---

### Violation 5: Retry Logic in CLI Bridge (Should Be LangGraph/Router)

**Location:** `cli/bridge.py:223-247` — `retry()` method increments attempt counter and re-invokes

**Why it violates SRP:** Retry policy belongs to 9Router (escalation path, max attempts). Bridge should only trigger "retry" — the HOW (escalate model, increment counter) should be owned by router/orchestrator.

**Why partially acceptable:** Bridge is the entry point that re-invokes the graph. The counter increment IS a workflow concern. But `max_attempts: 3` is hardcoded in bridge instead of coming from config.

**Owner:** `router.yaml` → `retry.max_attempts`. Bridge reads from config.

**Refactor:** Bridge reads `max_attempts` from router config instead of hardcoding `3`.

---

### Violation 6: Gateway base_url Hardcoded as Default

**Location:** `gateway/client.py:72` — `base_url: str = "https://9router.ai/api/v1"`

**Why it violates SRP:** The actual base_url is in `config/router.yaml`. The hardcoded default in code is stale (should be localhost:20128 now).

**Why dangerous:** If someone creates GatewayClient() without params (as nodes do), it uses the wrong URL.

**Owner:** `config/router.yaml` → `gateway.base_url`

**Refactor:** Remove default from GatewayClient constructor. Require explicit base_url. The shared instance reads from config.

---

### Violation 7: Duplicated "Classify" JSON prompt

**Location:** `nodes/orchestrator.py:149-170` constructs gateway client + router + prompt for classification. This same pattern repeats in every node that needs LLM.

**Why it violates SRP:** The "call LLM with routing" pattern is duplicated 6 times. It should be a shared utility.

**Owner:** A shared `call_llm(task_type, prompt)` function that internally uses router + gateway.

**Refactor:** Already partially done (`_call_domain_llm` in `data_telemetry.py`). But other nodes don't use it — they duplicate the pattern.

---

## Refactoring Plan

### Step 1: Create Shared Service Container

Create `src/factory/services.py` — singleton container that holds router + gateway:

```python
# Lazy-loaded, shared across all nodes in a single invocation
_router = None
_gateway = None

def get_router():
    global _router
    if _router is None:
        _router = NineRouter.from_config("config/router.yaml")
    return _router

def get_gateway():
    global _gateway
    if _gateway is None:
        config = get_router_config()
        _gateway = GatewayClient(
            base_url=config.gateway.base_url,
            api_key=os.environ.get(config.gateway.api_key_env, ""),
        )
    return _gateway

def call_llm(task_type: str, prompt: str, **kwargs) -> str | None:
    router = get_router()
    gateway = get_gateway()
    route = router.route(task_type=task_type, **kwargs)
    # ... single implementation of the call pattern
```

### Step 2: Remove All Hardcoded Model IDs

Replace every `"anthropic/claude-sonnet-4.6"` fallback with reading from services.

### Step 3: Nodes Use Services (Not Internal Creation)

Every node changes from:
```python
# BEFORE (duplicated in each node)
router = NineRouter.from_config("config/router.yaml")
gateway = GatewayClient()
route = router.route(...)
response = gateway.complete(...)
```

To:
```python
# AFTER (single shared instance)
from factory.services import call_llm
response = call_llm(task_type="review", prompt=prompt)
```

---

## Decision: Execute or Hold?

This refactor is **correct architecturally** but has trade-offs:

| Pro | Con |
|---|---|
| True SRP compliance | ~15 files to modify |
| Single source of truth for model IDs | Testing gets slightly harder (must mock services.py) |
| One gateway connection per invocation | Adds a global state module |
| Config change = one place | Current DI pattern (per-node injection) still works |

**Recommendation:** Execute. The violations are real. Model hardcoding WILL bite when 9Router catalog changes.

**Effort:** ~2 hours
**Risk:** Low (no public API changes, no CLI changes, no user-visible difference)
**Breaking changes:** Zero (internal refactor only)
