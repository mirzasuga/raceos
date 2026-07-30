# Complete System Flow — Final Integration

> How every component connects in the production system.
> All responsibilities unchanged. This documents the wiring.

---

## Component Chain (Verified)

```
Project Brain (.raceos/)     [READ-ONLY knowledge]
       ↓
   OpenSpec (specs/)         [Behavioral contracts]
       ↓
   Knowledge Agent           [Index + validate + follow-ups]
       ↓
   Context Agent             [Compose tiered bundle]
       ↓
   LangGraph (DAG)           [Orchestrate workflow]
       ↓
   OpenCode (executor)       [Edit code via MCP tools]
       ↓
   OpenRouter (gateway)      [HTTP proxy to LLM providers]
       ↓
   9Router (intelligence)    [Select model + enforce budget]
       ↓
   LLM (GPT-5/Claude/Gemini/DeepSeek)
```

---

## 1. Request Flow

```
HUMAN
  │
  │  $ raceos firmware "fix load always showing 100%"
  │
  ▼
CLI (app.py)
  │  Parse args → domain="firmware"
  │
  ▼
Shell Parser (parser.py)
  │  Intent detection: "fix" → intent="debug"
  │
  ▼
Factory Bridge (bridge.py)
  │  TaskRequest { description, domain, intent }
  │  Generate task_id: TASK-A1B2C3
  │  Save checkpoint (SQLite)
  │
  ▼
LangGraph.invoke(initial_state)
  │
  ├─► orchestrator_node
  │     9Router.route(task_type="classification") → DeepSeek
  │     OpenRouter.POST → DeepSeek classifies → {type:debugging, complexity:medium}
  │     Result: target_agent=engineer, no planning, no gate
  │
  ├─► context_node
  │     Brain Reader → .raceos/03-engineering/ (Tier 1, cached)
  │     Spec Reader → openspec/specs/display-dashboard/ (Tier 2)
  │     File Reader → firmware/middleware/telemetry_parser.cpp (Tier 3)
  │     Memory Client → "raw byte 0-255 maps to percentage" (Tier 4)
  │     Result: ContextBundle (9,480 tokens)
  │
  ├─► engineer_node
  │     9Router.route(task_type="debugging") → Claude Sonnet 4.6
  │     OpenCode.execute(context + constraints + task)
  │       └─► OpenCode internally calls OpenRouter → Claude
  │       └─► Reads files, identifies bug, applies fix, runs tests
  │     Result: {modified_files, test_result: 16 passed}
  │
  ├─► reviewer_node
  │     9Router.route(task_type="review") → Claude Sonnet 4, temp=0
  │     OpenRouter.POST → Claude reviews diff
  │     Result: {verdict: "approved", issues: []}
  │
  ├─► validator_node
  │     Trust-executor: tests already passed → skip re-run
  │     Result: {build_passed: true, tests_passed: true}
  │
  └─► knowledge_node
        Store patterns in codebase-memory
        Detect siblings: "rpm, temp, duty may have same issue"
        Result: {suggested_follow_ups: [...]}

  ▼
Bridge receives final state
  │  checkpoint.complete(task_id)
  │  Display result to human via AgentViz
  │
  ▼
HUMAN sees:
  ✅ Fixed: raw byte not converted to percentage
  💡 Follow-up: check rpm, temp, duty fields
```

---

## 2. Context Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                    CONTEXT FLOW (data path)                          │
│                                                                    │
│  ┌──────────────────┐                                              │
│  │ Project Brain    │  .raceos/03-engineering/engineering-principles│
│  │ (immutable)      │  .raceos/03-engineering/architecture-foundations│
│  │                  │  .ai/steering.md                              │
│  └────────┬─────────┘                                              │
│           │ read-only (BrainReader, path-safe)                     │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ OpenSpec         │  openspec/specs/firmware-core/spec.md         │
│  │ (contracts)      │  openspec/specs/ecu-protocol/spec.md         │
│  │                  │  openspec/specs/display-dashboard/spec.md    │
│  └────────┬─────────┘                                              │
│           │ SpecParser extracts Requirements + Scenarios           │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ Knowledge Agent  │  Validates: specs exist, ADRs valid,         │
│  │ (index+verify)   │  no conflicts, no stale docs                 │
│  │                  │  Stores: patterns in codebase-memory         │
│  └────────┬─────────┘                                              │
│           │ validation_status: ok                                   │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ Context Agent    │  TIER 1: principles (2K, cached 5min)        │
│  │ (compose)        │  TIER 2: domain spec (3K, cached per-domain) │
│  │                  │  TIER 3: target files (5K, never cached)     │
│  │                  │  TIER 4: memory patterns (1K, query-specific)│
│  │                  │  BUDGET: ≤ 12K total, truncate T3 first      │
│  └────────┬─────────┘                                              │
│           │ ContextBundle { tier1..4, total_tokens, sources }      │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ LangGraph State  │  state.context = ContextBundle               │
│  │ (carries)        │  Flows through all downstream nodes          │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ├──► Planner: context in prompt for spec generation      │
│           ├──► Engineer: context as system_prompt to OpenCode      │
│           ├──► Reviewer: context.tier1+tier2 for compliance check  │
│           └──► Architect: context for design decisions             │
│                                                                    │
│  ┌──────────────────┐                                              │
│  │ OpenCode Session │  system_prompt = tier1 + tier2 + tier3 + tier4│
│  │ (receives)       │  + adapter.constraints                       │
│  │                  │  + acceptance_criteria                        │
│  └────────┬─────────┘                                              │
│           │ OpenCode makes LLM calls with this context             │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ 9Router          │  Sees: task_type + complexity                 │
│  │ (selects model)  │  Checks: budget status                       │
│  │                  │  Returns: model_id + max_tokens + timeout    │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ OpenRouter       │  POST /chat/completions                      │
│  │ (sends)          │  model=selected, messages=[system+user]      │
│  │                  │  cache_control on system message (Tier 1)    │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ LLM              │  Receives: ~11K context + 2K task prompt     │
│  │ (processes)      │  Produces: code/analysis/spec                │
│  └──────────────────┘                                              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Context Budget Allocation (verified from walkthroughs)

| Tier | Source | Budget | Cached | Example Content |
|---|---|---|---|---|
| T1 | Brain (.raceos/) | 2K | ✅ 5min | "No magic numbers, no dynamic alloc, layered arch" |
| T2 | OpenSpec (specs/) | 3K | ✅ per-domain | Requirements + Scenarios for the domain |
| T3 | Source Files | 5K | ❌ never | Target .cpp/.h file contents |
| T4 | Codebase Memory | 1K | ❌ query-specific | "raw byte 0-255 maps to percentage" |
| **Total** | | **≤12K** | | ~6% of 200K model window |


---

## 3. Execution Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                    EXECUTION FLOW (tool path)                        │
│                                                                    │
│  LangGraph dispatches to engineer_node                             │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ Engineer Node    │  Builds ExecutionRequest:                     │
│  │                  │    model = routing.model_id (from 9Router)    │
│  │                  │    system_context = composed tier1-4          │
│  │                  │    constraints = adapter.constraints          │
│  │                  │    acceptance = plan.acceptance_criteria      │
│  │                  │    tools = [file, terminal, git, patch]       │
│  │                  │    previous_errors = retry.errors (if retry)  │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ OpenCode Client  │  executor/client.py                          │
│  │                  │    1. Get adapter (FirmwareAdapter)           │
│  │                  │    2. Build prompt (context + task + errors)  │
│  │                  │    3. Create session                          │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ Session Manager  │  executor/session.py                         │
│  │                  │    1. Write prompt to temp file               │
│  │                  │    2. Build CLI command                       │
│  │                  │    3. Filter env (security: only API key)     │
│  │                  │    4. subprocess.run(opencode, timeout=300s)  │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ OpenCode Process │  (external binary, isolated subprocess)      │
│  │                  │                                              │
│  │  MCP Tools:      │                                              │
│  │    file.read()   → read source files                           │
│  │    file.write()  → modify code                                 │
│  │    terminal.run()→ pio build, pio test                         │
│  │    git.branch()  → factory/fix-name                            │
│  │    git.commit()  → [factory] commit message                    │
│  │    patch.apply() → atomic code changes                         │
│  │                  │                                              │
│  │  LLM Calls:     │                                              │
│  │    (internally)  → OpenRouter → 9Router-selected model         │
│  └────────┬─────────┘                                              │
│           │ stdout: JSON result                                    │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ Result Parser    │  executor/client.py._parse_result()          │
│  │                  │    Parse: modified_files, test_results       │
│  │                  │    Extract: tokens, cost, learnings          │
│  │                  │    Status: success | failure | timeout       │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ State Update     │  Returns to LangGraph:                       │
│  │                  │    execution.modified_files                   │
│  │                  │    execution.output (summary)                │
│  │                  │    execution.token_usage                     │
│  │                  │    execution.learnings                       │
│  │                  │    retry.attempt (if failure)                │
│  └──────────────────┘                                              │
│                                                                    │
│  9Router involvement (model selection for OpenCode's LLM calls):   │
│                                                                    │
│  ┌──────────────────┐                                              │
│  │ 9Router          │  Called BEFORE OpenCode session:              │
│  │                  │    Input: task_type + complexity              │
│  │                  │    Check: budget status (degrade if > 90%)   │
│  │                  │    Output: model_id, max_tokens, timeout     │
│  │                  │                                              │
│  │  Policy:         │  debugging → Claude Sonnet 4.6, temp=0      │
│  │                  │  coding → Claude Sonnet 4.6, temp=0.1       │
│  │                  │  architecture → GPT-5, temp=0.2             │
│  │                  │  documentation → Gemini Pro, temp=0.3       │
│  │                  │  classification → DeepSeek, temp=0          │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ OpenRouter       │  Dumb HTTP pipe:                             │
│  │ (gateway)        │    POST https://openrouter.ai/api/v1/chat/  │
│  │                  │    Auth: Bearer $OPENROUTER_API_KEY          │
│  │                  │    Retry: 429→backoff, 5xx→retry, 400→fail  │
│  │                  │    Fallback: if Claude fails → GPT-5         │
│  │                  │    Cache: cache_control on Tier 1 prefix     │
│  └────────┬─────────┘                                              │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐                                              │
│  │ LLM Provider     │  Actually generates the code/review/spec    │
│  └──────────────────┘                                              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Execution Adapters (per domain)

| Domain | Build | Test | Constraints |
|---|---|---|---|
| firmware | `pio build -e native` | `pio test -e native` | No dynamic alloc, layered arch, HAL |
| mobile | `npx tsc --noEmit` | `npx jest --ci` | TypeScript strict, a11y labels |
| backend | `compileall src/` | `pytest --tb=short` | Type hints, Pydantic, async I/O |


---

## 4. Sequence Diagram

### Full Pipeline (Complex Feature Task)

```
Human    CLI     Bridge   LangGraph  9Router  Brain   OpenSpec  Memory  OpenCode  OpenRouter  LLM
  │       │        │         │         │       │        │        │        │          │        │
  │─cmd──►│        │         │         │       │        │        │        │          │        │
  │       │─req───►│         │         │       │        │        │        │          │        │
  │       │        │─invoke─►│         │       │        │        │        │          │        │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │         │─classify─────► │         │       │        │        │          │        │
  │       │        │         │         │──────────────────────────────────────────────►│──────►│
  │       │        │         │◄────────│◄─────────────────────────────────────────────│◄──────│
  │       │        │         │  type=coding, complexity=high                          │       │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │         │─context────────►│        │        │        │          │        │
  │       │        │         │         │       │─T1────►│        │        │          │        │
  │       │        │         │         │       │        │─T2────►│        │          │        │
  │       │        │         │         │       │        │        │─T4───► │          │        │
  │       │        │         │◄────────────────│◄───────│◄───────│◄──────│          │        │
  │       │        │         │  ContextBundle(9K tokens)         │        │          │        │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │         │─plan────────────────────►│        │        │          │        │
  │       │        │         │         │────────────────────────────────────────────►│──────►│
  │       │        │         │◄────────│◄──────────────────────────────────────────│◄──────│
  │       │        │         │  proposal.md + tasks.md (written to openspec/changes/)        │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │         │─gate───►│       │        │        │        │          │        │
  │◄──────│◄───────│◄────────│  "Approve?"     │        │        │        │          │        │
  │─yes──►│───────►│────────►│         │       │        │        │        │          │        │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │         │─execute─────────────────────────────────►│          │        │
  │       │        │         │         │────────────────────────────────│──────────►│──────►│
  │       │        │         │         │       │        │        │       │◄─────────│◄──────│
  │       │        │         │         │       │        │        │       │(edit+test)│        │
  │       │        │         │◄────────────────────────────────────────│           │        │
  │       │        │         │  ExecutionResult(files, 16 tests pass)  │           │        │
  │       │        │         │         │       │        │        │       │           │        │
  │       │        │         │─review──────────────────────────────────────────────►│──────►│
  │       │        │         │◄────────────────────────────────────────────────────│◄──────│
  │       │        │         │  verdict=approved                                   │        │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │         │─validate│       │        │        │        │          │        │
  │       │        │         │  (trust executor — skip)                              │        │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │         │─learn───────────────────────────────────►│           │        │
  │       │        │         │  store patterns + detect siblings        │           │        │
  │       │        │         │         │       │        │        │        │          │        │
  │       │        │◄────────│  DONE   │       │        │        │        │          │        │
  │       │◄───────│ result  │         │       │        │        │        │          │        │
  │◄──────│ display│         │         │       │        │        │        │          │        │
  │  ✅    │        │         │         │       │        │        │        │          │        │
```

### Simple Task (Bug Fix — No Planning, No Gate)

```
Human    CLI     Bridge   LangGraph  9Router  Context   Engineer  Reviewer  Validator  Knowledge
  │       │        │         │         │        │          │         │          │          │
  │─cmd──►│─req───►│─invoke─►│         │        │          │         │          │          │
  │       │        │         │─classify►│(DeepSeek)        │         │          │          │
  │       │        │         │◄────────│type=debug,low     │         │          │          │
  │       │        │         │─context──────────►│          │         │          │          │
  │       │        │         │◄─────────────────│(9K tok)  │         │          │          │
  │       │        │         │─execute──────────────────── ►│         │          │          │
  │       │        │         │         │(Claude)            │(fix+test)│         │          │
  │       │        │         │◄─────────────────────────── │          │          │          │
  │       │        │         │─review──────────────────────────────── ►│          │          │
  │       │        │         │◄──────────────────────────────────────│approved  │          │
  │       │        │         │─validate─────────────────────────────────────────►│          │
  │       │        │         │◄────────────────────────────────────────────────│(trusted) │
  │       │        │         │─learn───────────────────────────────────────────────────── ►│
  │       │        │◄────────│  DONE (44s, $0.20)                                         │
  │◄──────│◄───────│         │                                                            │
```

### Failure + Retry + Model Escalation

```
Engineer    9Router    OpenRouter    LLM      Reviewer    9Router(retry)  OpenRouter    LLM(better)
  │           │           │          │          │             │              │             │
  │─execute──►│           │          │          │             │              │             │
  │           │─Claude───►│─────────►│          │             │              │             │
  │◄──────────│◄──────────│◄─────────│          │             │              │             │
  │ (tests fail)          │          │          │             │              │             │
  │                       │          │          │             │              │             │
  │──────────────────────────────────────────── ►│             │              │             │
  │◄────────────────────────────────────────────│             │              │             │
  │ verdict=changes_requested, retry_worthwhile=true          │              │             │
  │                                                           │              │             │
  │─retry(attempt=2)─────────────────────────────────────────►│              │             │
  │           │           │          │          │  escalate───►│              │             │
  │           │           │          │          │  Claude4.6──►│──────────── ►│             │
  │◄──────────│◄──────────│◄─────────│──────────│◄────────────│◄─────────── │             │
  │ (tests pass on 2nd attempt with better model)             │              │             │
```

---

## File-to-Component Mapping

| Component | Implementation File(s) | Responsibility |
|---|---|---|
| Project Brain | `../.raceos/` (external) | Immutable knowledge |
| OpenSpec | `spec_engine/parser.py` + `validator.py` | Parse + validate specs |
| Knowledge Agent | `nodes/knowledge.py` | Index, follow-ups, persist |
| Context Agent | `nodes/context.py` + `context/cache.py` | Tier resolution + caching |
| LangGraph | `orchestrator/graph.py` + `edges/routing.py` | DAG coordination |
| OpenCode | `executor/client.py` + `session.py` | Subprocess execution |
| OpenRouter | `gateway/client.py` + `retry.py` | HTTP + retry + fallback |
| 9Router | `router/router.py` + `policy.py` + `cost.py` | Model selection + budget |
| LLM | External (GPT-5/Claude/Gemini/DeepSeek) | Generate content |

---

*End of System Flow*
