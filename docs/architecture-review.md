# Principal AI Architect Review

> Complete architectural review of the RaceOS AI Software Factory.
> Reviewed: 80+ source files, 9 config files, 11 agent definitions, 3 validation walkthroughs.

---

## Scorecard

| Category | Score | Verdict |
|---|---|---|
| Responsibility Overlap | **8/10** | Good — minor overlap identified |
| Tight Coupling | **9/10** | Excellent — clean boundaries |
| Circular Dependency | **10/10** | None detected |
| Context Duplication | **9/10** | Well-controlled |
| Memory Duplication | **9/10** | Clear tier separation |
| Agent Redundancy | **7/10** | One concern |
| Scalability | **7/10** | Single-user limitations |
| Maintainability | **9/10** | Excellent structure |
| Cost Optimization | **9/10** | Well-designed |
| Failure Recovery | **8/10** | Good with one gap |
| Retry Strategy | **9/10** | Comprehensive |
| Security | **8/10** | Good with one concern |
| Configuration Smells | **7/10** | Several overlapping configs |

**Overall: 8.4 / 10** — Production-ready architecture with minor refinements needed.

---

## Detailed Review

---

### 1. Responsibility Overlap — 8/10

**Finding:** Orchestrator node (`nodes/orchestrator.py`) and the Context node (`nodes/context.py`) both touch classification.

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| Orchestrator classifies task AND context node also uses classification to resolve tiers | Classification happens in orchestrator, but context resolver re-reads classification from state to decide tier loading | LOW — they share state correctly, no re-computation | No change needed. State-passing is the correct LangGraph pattern. | — |
| Review Agent checks architecture + Validator checks build | Both verify "code is correct" from different angles | LOW — intentional defense-in-depth | Document explicitly that overlap is by design. Not redundancy — complementary checks. | P3 |

**Verdict:** The overlaps found are intentional (defense-in-depth) or architectural conventions (state sharing). No fix needed.

---

### 2. Tight Coupling — 9/10

**Finding:** Components communicate exclusively via state (LangGraph) or config (YAML). No direct module imports between peers.

```
Dependency direction (verified):
  cli/ → orchestrator/ → [context/, router/, executor/, memory/, spec_engine/]
  gateway/ ← standalone (no imports from other factory modules)
  router/ ← standalone (reads config, no peer imports)
  memory/ ← standalone (MCP client)
  spec_engine/ ← standalone (file parser)
```

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| `knowledge_node` imports from `persist.py` (within orchestrator) | Persist logic is in orchestrator package, called by knowledge node | LOW — both in same package, valid intra-package dependency | Acceptable. Could move persist to a shared `utils/` if it grows. | P4 |

**Verdict:** Clean architecture. No cross-package coupling. Gateway doesn't know about routing. Router doesn't know about execution. Excellent.

---

### 3. Circular Dependency — 10/10

**Finding:** Zero circular dependencies detected.

```
Verified dependency graph:
  graph.py → nodes/* (one-way)
  graph.py → edges/* (one-way)
  nodes/* → state.py (one-way, types only)
  edges/* → state.py (one-way, types only)
  executor/* → gateway (one-way, for OpenCode's internal LLM calls)
  No cycles.
```

**Verdict:** Perfect. The layered structure prevents cycles by design.

---

### 4. Context Duplication — 9/10

**Finding:** Context flows through a single pipeline (Context Agent → state.context) and is consumed by all downstream nodes from state. No node loads its own context independently.

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| `config/models.yaml` and `config/router.yaml` both contain model catalogs | Historical — models.yaml was created first (M0 skeleton), router.yaml later replaced it | LOW — router.yaml is canonical, models.yaml is now stale | Remove `config/models.yaml` or mark as deprecated. `router.yaml` is the source of truth for model catalog. | P2 |

**Verdict:** Context injection is well-designed. One config duplication to clean up.

---

### 5. Memory Duplication — 9/10

**Finding:** Three-tier memory architecture (Brain / Codebase Memory / LangGraph State) has clear boundaries.

```
Brain (.raceos/)        → project knowledge (immutable, human-curated)
Codebase Memory (MCP)   → implementation patterns (AI-written, prunable)
LangGraph State         → session state (ephemeral, per-task)
```

No datum exists in two tiers.

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| `brain/` directory (existing RAG system with ChromaDB) coexists with `raceos-factory/memory/` | Historical — brain/ was built before the factory | LOW — different purpose (brain/ is interactive query, factory/memory is automated Tier 4) | Document the distinction. brain/ = human interactive queries. factory/memory = automated context injection. They serve different users. | P3 |

**Verdict:** Memory boundaries are clean. No operational duplication.

---

### 6. Agent Redundancy — 7/10

**Finding:** 11 agents defined. One potential redundancy detected.

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| **Orchestrator Agent** vs **Context Agent** — could be merged | Orchestrator classifies then hands off to context. Two separate nodes for what could be one "intake" step. | MEDIUM — adds one extra node transition (~100ms) per task | Keep separate. Orchestrator's responsibility (classify + route) is distinct from Context Agent's (resolve files + compose bundle). Merging would create a god-node. Single responsibility wins. | — |
| **Data/Telemetry Agent** is marked "standby" | No telemetry features in current roadmap. Agent exists but has no implementation path. | LOW — no runtime cost (never invoked unless explicitly routed) | Keep but document as "future" in agent README. Remove from graph compilation if never needed (lazy loading). | P4 |
| **Research Analyst** + **Product Strategist** have similar structures | Both read Brain, both produce markdown reports | LOW — different domains (market evidence vs product decisions). Different allowed tools. Not actually redundant. | No change. | — |

**Verdict:** Minor concern with dormant agent. No true redundancy in active workflow.

---

### 7. Scalability — 7/10

**Finding:** Current design is single-user, single-task, synchronous.

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| **Single-task execution** — LangGraph invokes synchronously | Design choice for v1 simplicity | MEDIUM — can only process one task at a time | Add `workflow.max_concurrent_tasks` support in Phase 3 (roadmap already plans this). LangGraph supports async. | P2 |
| **File-based persistence** (tasks.json, cost_ledger.jsonl) | Simple implementation choice | MEDIUM — file locking needed for concurrent access. No query capabilities. | Acceptable for single-user. Migrate to SQLite when multi-user needed. | P3 |
| **No queue** — tasks are fire-and-forget | Synchronous CLI invocation | LOW for current use — one developer | Add task queue (Redis/file-based) when concurrent tasks needed. | P3 |
| **OpenCode single session** — one subprocess at a time | Executor spawns one session | MEDIUM — can't parallelize multi-file tasks | Acceptable for v1. Plan session pooling for v2. | P3 |

**Verdict:** Architecture is scalability-ready (config for concurrency exists, LangGraph supports async) but current implementation is single-threaded. Appropriate for a single-developer project at this phase.

---

### 8. Maintainability — 9/10

**Finding:** Excellent structure.

```
Strengths:
  ✅ Every module has README.md explaining responsibility + "Does NOT"
  ✅ Config is external YAML (not hardcoded)
  ✅ Tests exist for all implemented modules
  ✅ Verification scripts for every integration
  ✅ Clean src/ layout with single-responsibility packages
  ✅ Type hints throughout (Pydantic + TypedDict)
  ✅ Agent definitions document inputs/outputs/rules
```

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| Some config files overlap in purpose | Evolved incrementally during implementation | LOW — developer confusion about which config to edit | Create a CONFIG_INDEX.md mapping "I want to change X → edit this file" | P3 |
| `langgraph/graph.yaml` duplicates `orchestrator/graph.py` | One is documentation, other is code | LOW — graph.yaml may drift from code over time | Add CI check: graph.yaml must match graph.py node/edge list. Or remove graph.yaml and generate from code. | P3 |

**Verdict:** Highly maintainable. A new developer can understand the system by reading READMEs → agent defs → graph.py → integration.md.

---

### 9. Cost Optimization — 9/10

**Finding:** Multi-layer cost control is well-designed.

```
Layer 1: 9Router selects cheapest adequate model per task type
Layer 2: Budget tracking with daily/per-task limits
Layer 3: Degradation strategy (downgrade at 90%, queue at 95%)
Layer 4: Trust-executor optimization (avoids redundant LLM calls)
Layer 5: Context budget (12K max — prevents token waste)
Layer 6: Classification via DeepSeek ($0.0001 — cheapest possible)
```

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| No prompt caching signal to 9Router | 9Router supports automatic prompt caching for stable system prompts (50% discount on cached input) | MEDIUM — Tier 1 context is identical across tasks; could get cached pricing | Add stable system prompt header that doesn't change per-task. Move Tier 1 into a fixed prefix that 9Router can cache. | P2 |
| Cost ledger has no archival/rotation | JSON Lines file grows unbounded | LOW — at 50 tasks/day × 365 days = ~18K lines = ~2MB (fine) | Add monthly rotation when file exceeds 10MB. | P4 |

**Verdict:** Cost optimization is a first-class concern, not an afterthought. Well-designed.

---

### 10. Failure Recovery — 8/10

**Finding:** Graceful degradation is implemented at multiple levels.

```
✅ Gateway: retry with exponential backoff (429, 5xx)
✅ Router: fallback chains across providers
✅ Executor: timeout + kill
✅ Memory: graceful degradation (returns empty if MCP unavailable)
✅ Validator: trust-executor fast path
✅ Knowledge: best-effort (failure doesn't block task)
```

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| **No state recovery after process crash** | LangGraph state is in-memory during execution | HIGH — if Python process crashes mid-task, all state is lost. Human must re-submit. | Add LangGraph checkpointing (SQLite-backed). After each node, persist state. On restart, resume from last checkpoint. | **P1** |
| **No dead letter queue** for failed tasks | Tasks that exhaust retries simply end with "failed" | LOW — human sees failure in CLI, can re-submit | Acceptable for v1. Add DLQ when operating at scale. | P3 |

**Verdict:** Good for happy-path and transient failures. Process crash recovery is the main gap.

---

### 11. Retry Strategy — 9/10

**Finding:** Comprehensive and well-layered.

```
Layer 1: Gateway retry (HTTP 429/5xx — exponential backoff)
Layer 2: Fallback chains (provider failure → switch provider)
Layer 3: Model escalation (task failure → upgrade to better model)
Layer 4: Human escalation (3 failures → stop, ask human)
```

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| No distinction between "wrong answer" and "error" | Retry is triggered by build/test failure, but that could be a fundamental misunderstanding (not retryable) vs a typo (retryable) | LOW — model escalation usually handles this (smarter model succeeds) | Consider adding confidence scoring from review agent. If review says "fundamental misunderstanding," skip retry and escalate immediately. | P3 |

**Verdict:** Retry strategy is one of the architecture's strengths. Well-thought-out escalation path.

---

### 12. Security — 8/10

**Finding:** Multiple security layers exist.

```
✅ Brain is read-only (BrainReader refuses writes + path traversal)
✅ MCP filesystem has blocked paths (.raceos, .ai, .env, config)
✅ Terminal has command allowlist + blocklist
✅ Git blocks force-push, main-branch commit, branch -D
✅ API key from environment only (never in config files)
✅ Patch validates before apply
✅ Audit logging for OpenCode sessions
```

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| **OpenCode subprocess inherits full environment** | `session.py` passes `env=None` (inherit parent) | MEDIUM — OpenCode has access to ALL env vars including secrets it doesn't need | Pass explicit env dict with only NINE_ROUTER_API_KEY and PATH. Strip GITHUB_TOKEN, AWS keys, etc. | **P1** |
| **No output sanitization** | LLM output injected into system without sanitization | LOW — factory is local CLI (no web surface). But if output contains shell-like content, it could confuse. | Add output escaping for CLI display. Not critical for v1 single-user. | P3 |

**Verdict:** Good security posture for a local CLI tool. The env inheritance issue should be fixed before any multi-user or networked deployment.

---

### 13. Configuration Smells — 7/10

**Finding:** 9 config files exist. Some overlap.

| File | Purpose | Overlap With |
|---|---|---|
| `factory.yaml` | Master config | — |
| `router.yaml` | 9Router (catalog + policy + fallback + retry + timeout + cost) | `models.yaml` (older catalog) |
| `models.yaml` | Model catalog (original, from M0) | `router.yaml` (newer, canonical) |
| `opencode.yaml` | OpenCode settings (YAML format) | `opencode.json` (JSON format, same data) |
| `opencode.json` | OpenCode settings (JSON, native format) | `opencode.yaml` (duplicate) |
| `context-tiers.yaml` | Context tier definitions | — |
| `mcp-servers.yaml` | MCP server registry | `opencode.json` tools section (partial overlap) |
| `memory.yaml` | Codebase memory settings | — |
| `openspec.yaml` | Spec engine settings | — |

| Issue | Root Cause | Impact | Recommendation | Priority |
|---|---|---|---|---|
| **`models.yaml` duplicates `router.yaml` catalog** | models.yaml created in M0, router.yaml superseded it | MEDIUM — developer confusion about which is canonical | Delete `models.yaml`. `router.yaml` is the single source for model catalog. | **P1** |
| **`opencode.yaml` duplicates `opencode.json`** | YAML created for factory-internal reference, JSON is OpenCode's native format | MEDIUM — two files to keep in sync | Delete `opencode.yaml`. Keep only `opencode.json` (native format). Factory reads JSON directly. | **P1** |
| **`mcp-servers.yaml` partially overlaps `opencode.json` tools section** | mcp-servers.yaml defines access control, opencode.json defines tool capabilities | LOW — different purpose (access control vs capability definition) | Document the distinction: mcp-servers.yaml = "who can use what", opencode.json = "what tools can do". | P3 |

**Verdict:** 3 files should be removed/consolidated. Config sprawl is the primary maintainability risk.

---

## Priority Summary

### P1 — Fix Before Production (3 issues)

| # | Issue | Category | Fix |
|---|---|---|---|
| 1 | No state recovery after crash | Failure Recovery | Add LangGraph checkpointing (SQLite backend) |
| 2 | OpenCode inherits full environment | Security | Pass explicit filtered env dict |
| 3 | Config duplicates (models.yaml + opencode.yaml) | Configuration | Delete duplicate files |

### P2 — Fix Soon (3 issues)

| # | Issue | Category | Fix |
|---|---|---|---|
| 4 | No prompt caching signal | Cost | Stabilize Tier 1 as cacheable prefix |
| 5 | Single-task execution | Scalability | Plan async support in LangGraph |
| 6 | models.yaml/router.yaml confusion | Context Duplication | Remove models.yaml |

### P3 — Fix Eventually (7 issues)

| # | Issue | Category | Fix |
|---|---|---|---|
| 7 | File-based persistence limits | Scalability | Migrate to SQLite when multi-user |
| 8 | graph.yaml drift from code | Maintainability | CI check or auto-generate |
| 9 | Config index missing | Maintainability | Create CONFIG_INDEX.md |
| 10 | brain/ vs factory/memory distinction | Memory | Document in README |
| 11 | No DLQ for failed tasks | Failure Recovery | Add when operating at scale |
| 12 | No retry confidence scoring | Retry | Add after production data available |
| 13 | Output sanitization | Security | Add for any networked deployment |

### P4 — Nice to Have (3 issues)

| # | Issue | Category | Fix |
|---|---|---|---|
| 14 | Data/Telemetry agent dormant | Agent Redundancy | Lazy-load or remove from graph |
| 15 | Cost ledger no rotation | Cost | Add monthly rotation at 10MB |
| 16 | persist.py in orchestrator package | Coupling | Move to utils/ if it grows |

---

## Final Architecture Assessment

```
╔══════════════════════════════════════════════════════════╗
║  ARCHITECTURE HEALTH: 8.4 / 10                          ║
║                                                         ║
║  Strengths:                                             ║
║    • Clean separation of concerns (9/10)                ║
║    • Zero circular dependencies (10/10)                 ║
║    • Comprehensive retry + fallback (9/10)              ║
║    • Cost-aware by design (9/10)                        ║
║    • Excellent maintainability (9/10)                   ║
║                                                         ║
║  Weaknesses:                                            ║
║    • Config duplication (7/10)                          ║
║    • Scalability is single-user (7/10)                  ║
║    • No crash recovery (8/10 → 10/10 with checkpoint)  ║
║                                                         ║
║  Production Readiness:                                  ║
║    After fixing 3 P1 issues: READY for single-user     ║
║    After fixing P1+P2: READY for team use              ║
║    After fixing P1+P2+P3: READY for scale              ║
║                                                         ║
║  Architecture Changes Needed: ZERO                      ║
║  (All fixes are config cleanup or node-level logic)     ║
╚══════════════════════════════════════════════════════════╝
```
