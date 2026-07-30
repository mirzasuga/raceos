# Factory Validation: "Implement Engine Load Gauge"

> End-to-end trace of the complete AI Software Factory processing a real task.

---

## Task Input

```
$ factory task "Implement Engine Load Gauge for the race dashboard" --domain firmware
```

---

## Phase 1: Classification + Routing

### Agent: Orchestrator

**Action:** Classify task type and complexity.

```
Input:  "Implement Engine Load Gauge for the race dashboard"
Domain: firmware

Classification:
  task_type: coding
  complexity: HIGH (keyword "implement" + new visual component + multi-file)
  target_agent: engineer
  requires_planning: true (complexity >= HIGH)
  requires_human_gate: true (complexity >= HIGH)

Reasoning:
  - "Implement" signals new capability (not fix/refactor)
  - "Gauge" implies new display element (spec + ADR needed)
  - Multi-layer: middleware (formatting) + drivers (rendering) + tests
```

**9Router call:** `route(task_type="classification")` → DeepSeek Chat, 32 tokens, $0.0001

**Duration:** ~2 seconds

---

## Phase 2: Knowledge Validation

### Agent: Knowledge Agent

**Action:** Verify knowledge base consistency before proceeding.

```
Checks:
  ✅ openspec/specs/display-dashboard/spec.md — exists, current
  ✅ openspec/specs/firmware-core/spec.md — exists, valid
  ✅ adr/ADR-0011-raceos-hmi-design-language.md — exists
  ✅ adr/ADR-0012-display-hardware-ili9341.md — exists
  ✅ adr/ADR-0020-graphics-display-panel-hal.md — exists
  ⚠️ No existing spec for "engine load gauge" specifically
  ℹ️ Related: display-dashboard spec mentions LOAD in vitals

Status: OK (no conflicts, no stale documents)
```

**Duration:** ~500ms (file system reads only, no LLM)

---

## Phase 3: Context Resolution

### Agent: Context Agent

**Action:** Compose tiered context bundle.

```
TIER 1 (Principles — always loaded):
  ├── .ai/steering.md (270 tokens)
  └── .raceos/03-engineering/engineering-principles.md (1,580 tokens)
  Subtotal: 1,850 tokens

TIER 2 (Domain — display-dashboard + relevant ADRs):
  ├── openspec/specs/display-dashboard/spec.md (1,800 tokens)
  ├── openspec/specs/hal-display-panel/spec.md (900 tokens)
  └── adr/ADR-0020-graphics-display-panel-hal.md (extract: 400 tokens)
  Subtotal: 3,100 tokens → truncated to 3,000 budget

TIER 3 (Target files — existing gauge implementations):
  ├── firmware/middleware/dashboard_view.h (800 tokens)
  ├── firmware/middleware/dashboard_view.cpp (2,100 tokens)
  ├── firmware/core/display_tokens.h (600 tokens)
  └── firmware/core/telemetry_data.h (400 tokens)
  Subtotal: 3,900 tokens

TIER 4 (Codebase Memory — patterns):
  ├── "DashboardView uses dirty-region rendering" (200 tokens)
  ├── "Vitals bar: TftDisplay::drawBar() with FieldState color" (180 tokens)
  └── "DisplayTokens: named constants for thresholds" (120 tokens)
  Subtotal: 500 tokens

TOTAL: 9,250 tokens (within 12K budget ✅)
Sources: 10 documents
```

**Duration:** ~400ms (file reads + memory query, no LLM)

---

## Phase 4: Planning

### Agent: Planner (via Systems Architect logic)

**Action:** Generate spec artifacts using GPT-5.

**9Router call:** `route(task_type="planning")` → GPT-5, 8192 tokens, temp=0.3

**Generated artifacts:**

```
openspec/changes/implement-engine-load-gauge/
├── proposal.md
│   Problem: Dashboard shows LOAD as text; needs visual gauge for at-a-glance reading
│   Scope: Add radial/bar gauge for engine load percentage (0-100%)
│   Criteria:
│     - Gauge renders within vitals area (320×240 constraints)
│     - Colors follow FieldState (Normal/Warn/Danger)
│     - Threshold constants in display_tokens.h
│     - Host-native testable (env: native)
│   Out of scope: new HAL methods, custom fonts
│
└── tasks.md
    Task 1: Add load gauge threshold constants to display_tokens.h
    Task 2: Implement LoadGaugeView render logic in middleware/
    Task 3: Integrate LoadGaugeView into DashboardView layout
    Task 4: Write Unity tests for gauge state transitions
    Task 5: Verify pio build + pio test pass
```

**Cost:** ~$0.30 (GPT-5, ~3K input + 2K output)
**Duration:** ~8 seconds

---

## Phase 5: Human Approval

### Agent: Human Gate

**Action:** Pause and wait for human review.

```
$ factory status
┌─────────────────────────────────────────────────────────────┐
│ TASK-A1B2C3 │ Implement Engine Load Gauge │ AWAITING_APPROVAL│
│ Domain: firmware │ Complexity: HIGH │ Est. cost: $0.45     │
│ Plan: openspec/changes/implement-engine-load-gauge/         │
└─────────────────────────────────────────────────────────────┘

$ factory approve TASK-A1B2C3
✅ Task TASK-A1B2C3 approved.
```

**Duration:** Human-dependent (minutes to hours)

---

## Phase 6: Execution

### Agent: Engineering Agent (via OpenCode)

**Action:** Implement code from approved plan (5 sub-tasks).

**9Router call:** `route(task_type="coding", complexity="high")` → Claude Sonnet 4.6, 8192 tokens, temp=0.1, timeout=120s

**OpenCode session:**

```
System prompt: context.tier1 + tier2 + tier3 + tier4 (9,250 tokens)
Constraints:
  - No dynamic allocation
  - No magic numbers (use display_tokens.h)
  - Host-native testable
  - Layered: middleware/ only (no driver changes)
  - Guard hardware with #if defined(ARDUINO)
Tools: file (read/write), terminal (pio build/test), git (branch/commit), patch

Execution:
  1. git branch "factory/implement-engine-load-gauge"
  2. Edit firmware/core/display_tokens.h → add kLoadWarnThreshold, kLoadDangerThreshold
  3. Create firmware/middleware/load_gauge_view.h → LoadGaugeView class
  4. Create firmware/middleware/load_gauge_view.cpp → render logic
  5. Edit firmware/middleware/dashboard_view.cpp → integrate gauge
  6. Create firmware/tests/test_load_gauge_view.cpp → Unity tests
  7. terminal: pio build -e native → ✅ (0 errors)
  8. terminal: pio test -e native → ✅ (18 passed, 0 failed)
  9. git add + git commit "[factory] implement engine load gauge"
```

**Result:**
```
modified_files:
  - firmware/core/display_tokens.h
  - firmware/middleware/load_gauge_view.h (NEW)
  - firmware/middleware/load_gauge_view.cpp (NEW)
  - firmware/middleware/dashboard_view.cpp
  - firmware/tests/test_load_gauge_view.cpp (NEW)

test_result: { passed: 18, failed: 0 }
git_branch: "factory/implement-engine-load-gauge"
```

**Cost:** ~$0.18 (Claude Sonnet 4.6, ~11K input + 4K output)
**Duration:** ~45 seconds

---

## Phase 7: Review

### Agent: Review Agent

**Action:** Independent review of code changes.

**9Router call:** `route(task_type="review")` → Claude Sonnet 4, 4096 tokens, temp=0.0

**Review checklist:**

```
Architecture Foundations:
  ✅ Layered: new files in middleware/ (correct layer)
  ✅ No #include from lower to higher layer
  ✅ No dynamic allocation (static buffers only)
  ✅ No magic numbers (kLoadWarnThreshold in display_tokens.h)
  ✅ Host-native testable (compiles on native env)
  ✅ Hardware guarded (no Arduino calls in middleware)

Spec compliance:
  ✅ Gauge renders within 320×240
  ✅ Uses FieldState for color decisions
  ✅ Threshold constants named in display_tokens.h

Code quality:
  ✅ Comments in Indonesian (convention followed)
  ✅ Small functions, meaningful names
  ✅ Tests cover normal/warn/danger states

Verdict: APPROVED (0 critical, 0 major, 1 nit)
  nit: Consider adding brief docstring to LoadGaugeView class
```

**Cost:** ~$0.08 (Claude Sonnet 4, ~6K input + 1K output)
**Duration:** ~5 seconds

---

## Phase 8: Validation

### Agent: Validation Agent

**Action:** Run build + tests independently.

```
$ pio build -e native
  ✅ Build succeeded (0 errors, 0 warnings)

$ pio test -e native
  ✅ 18 tests passed, 0 failed, 0 skipped

$ pio build -e blackpill_f411ce
  ✅ Build succeeded (flash: 82%, RAM: 45%)

Acceptance criteria check:
  ✅ Gauge renders within vitals area
  ✅ Colors follow FieldState thresholds
  ✅ Constants in display_tokens.h
  ✅ Host-native testable (tests pass on native)
  ✅ No regression (pre-existing 14 tests still pass)
```

**Cost:** $0.00 (no LLM — terminal commands only)
**Duration:** ~15 seconds

---

## Phase 9: Knowledge Update

### Agent: Knowledge Agent

**Action:** Index learnings, update patterns.

```
Patterns stored in codebase-memory:
  1. "LoadGaugeView: radial gauge component using dirty-region rendering"
     files: [load_gauge_view.h, load_gauge_view.cpp]
  2. "New display component pattern: header + render() + getFieldState()"
     files: [load_gauge_view.h, dashboard_view.cpp]
  3. "Display threshold constants: k{Field}WarnThreshold, k{Field}DangerThreshold"
     files: [display_tokens.h]

Cross-reference update:
  - display-dashboard spec now has implementation for LOAD gauge
  - No CHANGELOG update (not a release-worthy change yet)
```

**Cost:** $0.00 (file writes to memory store, no LLM)
**Duration:** ~1 second

---

## Complete Task Summary

| Phase | Agent | Duration | Cost | LLM Calls |
|---|---|---|---|---|
| Classification | Orchestrator | 2s | $0.0001 | 1 (DeepSeek) |
| Knowledge | Knowledge Agent | 0.5s | $0.00 | 0 |
| Context | Context Agent | 0.4s | $0.00 | 0 |
| Planning | Planner | 8s | $0.30 | 1 (GPT-5) |
| Human Gate | Human | variable | $0.00 | 0 |
| Execution | Engineer | 45s | $0.18 | 1-3 (Claude) |
| Review | Reviewer | 5s | $0.08 | 1 (Claude) |
| Validation | Validator | 15s | $0.00 | 0 |
| Knowledge | Knowledge Agent | 1s | $0.00 | 0 |
| **TOTAL** | | **~77s** | **$0.56** | **4-6** |

---

## Bottleneck Analysis

| Bottleneck | Location | Severity | Impact |
|---|---|---|---|
| **Human gate latency** | Phase 5 | HIGH | Blocks entire pipeline until human responds |
| **Planning LLM call** | Phase 4 | MEDIUM | GPT-5 is slow (~8s); longest single LLM call |
| **OpenCode session** | Phase 6 | MEDIUM | 45s is the bulk of execution time |
| **Sequential sub-tasks** | Phase 6 | LOW | 5 sub-tasks run sequentially (no parallelism) |
| **Review is redundant with validation** | Phase 7+8 | LOW | Both check architecture compliance |

### Bottleneck Root Causes

1. **Human gate** — By design. This is the "AI suggests, human decides" principle. Not a bug.
2. **Planning latency** — GPT-5 processes the full context (9K tokens) before generating plan. Unavoidable for quality.
3. **OpenCode serial execution** — Sub-tasks within a session execute sequentially because files may depend on each other.

---

## Duplicated Responsibility Analysis

| Concern | Checked By | Redundancy? |
|---|---|---|
| Architecture compliance | Review Agent + Validator | **PARTIAL OVERLAP** — Review checks code structure, Validator runs tests. Different angles. |
| Tests pass | OpenCode (during execution) + Validator | **REDUNDANT** — OpenCode already runs tests before reporting success. Validator re-runs them. |
| Magic numbers | Review Agent + Engineering constraints | **ACCEPTABLE** — Defense in depth. Constraint prevents, review catches escapes. |
| Build succeeds | OpenCode + Validator | **REDUNDANT** — Same build command run twice. |

### Actual Duplications Found

1. **Tests run twice:** OpenCode runs `pio test` during execution (Step 6.8), then Validator runs it again (Step 8). Same command, same result.
2. **Build run twice:** OpenCode builds during execution, Validator rebuilds.

---

## Improvement Suggestions

### 1. Skip Redundant Validation Build/Test (LOW effort, HIGH impact)

**Problem:** Validator re-runs the exact same build+test that OpenCode already ran.

**Fix:** If OpenCode's `ExecutionResult.test_result.passed == total` AND `build_result.passed`, Validator can trust the result and only run a quick sanity check (or skip entirely).

**Implementation:**
```python
# In validator_node:
if state["execution"].get("test_result", {}).get("failed", 1) == 0:
    # OpenCode already verified — trust the result
    return {"validation": state["execution"]["test_result"], "status": "success"}
```

**Why not always skip:** If OpenCode's test environment differs from production test config, or if we don't trust the executor, keep the redundant check.

**Recommendation:** Add config flag `validation.trust_executor_tests: true` — skips rebuild when executor reports green.

---

### 2. Parallelize Review + Validation (MEDIUM effort, MEDIUM impact)

**Problem:** Review and Validation run sequentially (review → validate). They don't depend on each other.

**Fix:** Run both in parallel. Only proceed to Knowledge if BOTH pass.

**Implementation:**
```python
# In graph.py — use LangGraph parallel branches:
# after_execution → [reviewer, validator] (parallel)
# → join → knowledge (if both pass)
```

**Estimated savings:** ~5 seconds (review and validate overlap instead of serial).

**Why not now:** LangGraph parallel nodes add complexity. Worth it when task volume justifies.

---

### 3. Cache Context Between Related Tasks (MEDIUM effort, HIGH impact)

**Problem:** If a human submits 3 tasks for the same domain, Context Agent re-reads the same Brain files 3 times.

**Fix:** Cache Tier 1 and Tier 2 with a TTL (already in config: `brain.cache_ttl_seconds: 300`). Implement the actual caching.

**Implementation:** In-memory LRU cache in `brain_reader.py` with 5-minute TTL.

**Estimated savings:** ~300ms per subsequent task in same domain within 5 minutes.

---

### 4. Reduce Planning Cost for Medium-Complexity Tasks (LOW effort, MEDIUM impact)

**Problem:** Planning uses GPT-5 ($0.30) even for medium tasks. For this gauge implementation, Claude could plan adequately.

**Fix:** Split planning routing:
- `complexity: HIGH/CRITICAL` → GPT-5 (current)
- `complexity: MEDIUM` → Claude Sonnet 4.6 (cheaper + faster)

**Implementation:**
```yaml
# config/router.yaml — add complexity-aware planning rule:
- match: { task_type: "planning", complexity: "medium" }
  model: "claude-sonnet-latest"
  max_tokens: 4096
  temperature: 0.3
  reason: "Medium tasks don't need GPT-5 reasoning depth"
```

**Estimated savings:** $0.20 per medium-complexity planning call.

---

### 5. Lazy Tier 3 Loading (LOW effort, LOW impact)

**Problem:** Context Agent loads target files (Tier 3) before the planner runs. But the planner might identify DIFFERENT files to modify.

**Fix:** Load Tier 3 lazily — after planning identifies specific target files, reload context with those files for execution.

**Trade-off:** Adds a second context resolution step. Only worth it if initial file guess is often wrong.

**Recommendation:** Keep current approach. The initial guess (based on task keywords) is usually close enough. Planner output refines which files to touch, and OpenCode can read additional files during execution.

---

## Validation Verdict

### ✅ Architecture is Sound

The "Implement Engine Load Gauge" task successfully flows through all components:
- Brain principles are injected (Tier 1)
- Domain specs constrain the implementation (Tier 2)
- Existing code provides context (Tier 3)
- Codebase patterns guide style (Tier 4)
- Planning produces reviewable artifacts
- Human gate enforces "AI suggests, human decides"
- Execution produces working code with tests
- Review catches compliance issues
- Validation verifies independently
- Knowledge learns for next time

### ⚠️ Minor Issues (Non-blocking)

1. Build/test runs twice (OpenCode + Validator) — wastes ~15s per task
2. Review + Validation are serial — could be parallel
3. GPT-5 for all planning is overkill for medium tasks

### ❌ No Critical Issues Found

- No duplicated context (each tier has unique source)
- No duplicated memory (Brain ≠ Codebase Memory — clear boundary)
- No duplicated planning (planner runs once, execution follows plan)
- No overlapping responsibilities (each agent has clear boundary)
- Single responsibility maintained across all 11 agents

---

## Recommendations Priority

| # | Improvement | Effort | Impact | Do When |
|---|---|---|---|---|
| 1 | Skip redundant validator tests | LOW | HIGH | M5 implementation |
| 2 | Medium-planning uses Claude | LOW | MEDIUM | Config change now |
| 3 | Cache Tier 1+2 context | MEDIUM | HIGH | M2 implementation |
| 4 | Parallelize review+validation | MEDIUM | MEDIUM | After M11 (LangGraph parallel) |
| 5 | Lazy Tier 3 loading | LOW | LOW | Defer (current approach works) |
