# Configuration Index

> "I want to change X — which file do I edit?"

---

## Quick Lookup

| I want to change... | Edit this file |
|---|---|
| Which model handles which task type | `config/router.yaml` → `policy.rules` |
| Model pricing / catalog | `config/router.yaml` → `catalog` |
| Fallback chains (provider failure) | `config/router.yaml` → `fallback.chains` |
| Retry behavior (backoff, attempts) | `config/router.yaml` → `retry` |
| Timeout per model/task | `config/router.yaml` → `timeout` |
| Daily/per-task budget limits | `config/router.yaml` → `cost.budget` |
| Budget degradation strategy | `config/router.yaml` → `cost.degradation` |
| OpenCode tools (file/terminal/git/patch) | `config/opencode.json` → `tools` |
| OpenCode safety guardrails | `config/opencode.json` → `safety` |
| OpenCode allowed/blocked commands | `config/opencode.json` → `tools.terminal` |
| Context token budgets per tier | `config/context-tiers.yaml` → `tiers` |
| Which Brain docs load per task type | `config/context-tiers.yaml` → `tiers.tier2.load_by_task_type` |
| Brain path | `config/factory.yaml` → `brain.root` |
| OpenSpec paths | `config/factory.yaml` → `openspec` |
| Workflow concurrency / timeouts | `config/factory.yaml` → `workflow` |
| Logging level/format | `config/factory.yaml` → `logging` |
| MCP server access control | `config/mcp-servers.yaml` |
| Memory indexing paths/extensions | `config/memory.yaml` → `indexing` |
| Semantic search thresholds | `config/memory.yaml` → `search` |
| Symbol extraction patterns | `config/memory.yaml` → `symbols` |
| Layer validation rules | `config/memory.yaml` → `dependencies.layers` |
| Spec parser markers (GIVEN/WHEN/THEN) | `config/openspec.yaml` → `parser` |
| Spec validation severity | `config/openspec.yaml` → `validation` |
| Spec generation model/temperature | `config/openspec.yaml` → `generator` |
| API key | `.env` → `NINE_ROUTER_API_KEY` |

---

## Config File Responsibilities (No Overlap)

| File | Single Responsibility |
|---|---|
| `router.yaml` | **Model intelligence**: which model, when, how much, what if fails |
| `opencode.json` | **Execution safety**: what tools, what commands, what's blocked |
| `factory.yaml` | **System paths**: where Brain lives, where specs are, logging |
| `context-tiers.yaml` | **Context assembly**: what goes into the prompt, token budgets |
| `mcp-servers.yaml` | **Tool access control**: which nodes can use which MCP servers |
| `memory.yaml` | **Memory behavior**: indexing, search, symbols, dependencies |
| `openspec.yaml` | **Spec engine**: parsing rules, validation, generation |
| `.env` | **Secrets**: API keys (never in YAML/JSON) |

---

## Async Support Plan (P2-5)

Current: Single-task, synchronous execution via `graph.invoke()`.

Migration path to async (when needed):

```
Phase 1 (current): graph.invoke() — blocking, single task
Phase 2 (future):  graph.ainvoke() — async, single task
Phase 3 (future):  Task queue + worker pool — concurrent tasks
```

LangGraph natively supports `ainvoke()`. The migration requires:
1. Convert `invoke_factory()` to `async def`
2. Add `asyncio.run()` in CLI entry point
3. OpenCode session already uses subprocess (naturally async-friendly)
4. Gateway client: swap `httpx.Client` → `httpx.AsyncClient`

**When to migrate:** When daily task volume exceeds 20 tasks/day or
when multiple developers use the factory simultaneously.

**Effort:** ~1 day (all interfaces are already async-compatible).

---

## SQLite Migration Path (P3-7)

Current persistence uses JSON files:
- `data/tasks.json` — task state (filelock-protected)
- `data/cost_ledger.jsonl` — cost records (append-only)
- `data/patterns.jsonl` — codebase memory patterns
- `data/checkpoints.db` — already SQLite! (crash recovery)

Migration path when file-based persistence becomes limiting:

```
Step 1: checkpoints.db already uses SQLite ✅
Step 2: Migrate cost_ledger.jsonl → cost table in checkpoints.db
Step 3: Migrate tasks.json → tasks table in checkpoints.db
Step 4: Result: single SQLite file for all persistence
```

**When to migrate:** When concurrent access causes file lock contention
(multiple CLI processes running simultaneously).

**Effort:** ~2 hours (data is already structured, just change storage backend).

---

## brain/ vs factory/memory Distinction (P3-10)

Two "memory" systems exist in RaceOS. They serve different purposes:

| Aspect | `brain/` (existing RAG) | `raceos-factory/memory/` |
|---|---|---|
| Purpose | Human-interactive knowledge Q&A | Automated context injection (Tier 4) |
| User | Human developer asking questions | Factory orchestrator (programmatic) |
| Interface | CLI chat (`python cli.py`) | MCP protocol (programmatic API) |
| Storage | ChromaDB (vector embeddings) | codebase-memory-mcp (MCP server) |
| Content | All Brain docs + specs + ADRs | Code patterns + file relationships only |
| Embedding | Ollama (nomic-embed-text, local) | MCP server's internal embedding |
| Query | Natural language (human types) | Automated (from task description) |
| When used | Human wants to understand something | Factory needs Tier 4 context |

**They do NOT overlap.** brain/ is for humans. factory/memory is for the AI pipeline.
Both READ from the same source (`.raceos/`, `openspec/`) but serve different consumers.

---

## graph.yaml Drift Prevention (P3-8)

`langgraph/graph.yaml` documents the DAG topology. It may drift from `graph.py`.

Prevention options:
1. **CI check** (recommended): script compares graph.yaml nodes/edges with graph.py
2. **Auto-generate**: generate graph.yaml from graph.py on each build
3. **Delete graph.yaml**: rely solely on graph.py + README for documentation

Recommended: Add to CI pipeline:
```yaml
# .github/workflows/ci.yaml
- name: Check graph.yaml sync
  run: python scripts/check-graph-sync.py
```

Script compares node names in both files and fails if mismatched.
