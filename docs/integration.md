# Complete System Integration

> How every component connects end-to-end.

---

## Component Chain

```
Project Brain (.raceos/)
       ↓ read-only
   OpenSpec (specs/)
       ↓ parse
   Knowledge Agent
       ↓ index + validate
   Context Agent
       ↓ compose bundle
   LangGraph (orchestrator)
       ↓ dispatch
   OpenCode (executor)
       ↓ calls
   9Router (model selection)
       ↓ decides model
   OpenRouter (gateway)
       ↓ HTTP
   LLM (GPT-5 / Claude / Gemini / DeepSeek)
```

---

## 1. Complete Request Flow

### Step-by-step: From human request to LLM response

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE REQUEST FLOW                              │
│                                                                         │
│  STEP 1: Human submits task                                             │
│  ─────────────────────────────                                          │
│  $ factory task "implement watchdog timer HAL" --domain firmware         │
│                                                                         │
│  STEP 2: CLI creates initial state                                      │
│  ─────────────────────────────────                                      │
│  FactoryState = {                                                       │
│    task: { id: "TASK-A1B2C3", description: "...", domain: "firmware" }, │
│    status: "pending",                                                   │
│    history: []                                                          │
│  }                                                                      │
│                                                                         │
│  STEP 3: LangGraph invokes orchestrator node                            │
│  ─────────────────────────────────────────────                          │
│  orchestrator_node(state):                                              │
│    → Classify task: type=coding, complexity=high                        │
│    → Determine: requires_planning=true, requires_human_gate=true        │
│    → Set target_agent="engineer"                                        │
│    → Returns: { classification, status: "classifying" }                 │
│                                                                         │
│  STEP 4: LangGraph invokes context node                                 │
│  ─────────────────────────────────────────                              │
│  context_node(state):                                                   │
│    → Knowledge Agent: index check (specs current? ADRs valid?)          │
│    → Context Agent resolves tiers:                                      │
│        Tier 1: .ai/steering.md + engineering-principles (2K tokens)     │
│        Tier 2: openspec/specs/firmware-core/spec.md (3K tokens)         │
│        Tier 3: (none yet — no target files specified)                   │
│        Tier 4: codebase-memory patterns for "watchdog" (1K tokens)      │
│    → Returns: { context: ContextBundle, status: "planning" }            │
│                                                                         │
│  STEP 5: Edge routes to planner (complexity=high)                       │
│  ─────────────────────────────────────────────────                      │
│  after_context(state) → "planner"                                       │
│                                                                         │
│  STEP 6: Planner generates spec artifacts                               │
│  ─────────────────────────────────────────                              │
│  planner_node(state):                                                   │
│    → 9Router: route(task_type="planning") → GPT-5, 8192 tokens          │
│    → OpenRouter: POST /chat/completions (model: openai/gpt-5)           │
│    → LLM generates: proposal.md + tasks.md                              │
│    → Write to: openspec/changes/implement-watchdog-timer-hal/           │
│    → Returns: { plan: PlanArtifacts, status: "planning" }               │
│                                                                         │
│  STEP 7: Edge routes to human gate (requires_human_gate=true)           │
│  ─────────────────────────────────────────────────────────────          │
│  after_planning(state) → "human_gate"                                   │
│                                                                         │
│  STEP 8: Human approves plan                                            │
│  ─────────────────────────────                                          │
│  $ factory approve TASK-A1B2C3                                          │
│  human_gate_node(state):                                                │
│    → Returns: { human_decision: { approved: true }, status: "approved" }│
│                                                                         │
│  STEP 9: Edge routes to engineer                                        │
│  ─────────────────────────────                                          │
│  after_human_gate(state) → "engineer"                                   │
│                                                                         │
│  STEP 10: Engineer node executes via OpenCode                           │
│  ──────────────────────────────────────────────                         │
│  engineer_node(state):                                                  │
│    → Build ExecutionRequest from plan.task_breakdown[0]                 │
│    → Get adapter: FirmwareAdapter (constraints, build/test cmds)        │
│    → 9Router: route(task_type="coding") → Claude Sonnet 4.6, 8192      │
│    → OpenCode session:                                                  │
│        - System prompt = context.tier1 + tier2 + tier4                  │
│        - Task prompt = task description + constraints + criteria         │
│        - Tools: file, terminal, git, patch                              │
│        - Model: anthropic/claude-sonnet-4.6                             │
│    → OpenCode internally calls OpenRouter for LLM completions           │
│    → OpenCode edits files, runs build, runs tests                       │
│    → Returns: { execution: ExecutionResult, status: "executing" }       │
│                                                                         │
│  STEP 11: Edge routes to reviewer                                       │
│  ──────────────────────────────                                         │
│  after_execution(state) → "reviewer" (code-producing agent)             │
│                                                                         │
│  STEP 12: Reviewer checks the work                                      │
│  ──────────────────────────────                                         │
│  reviewer_node(state):                                                  │
│    → 9Router: route(task_type="review") → Claude Sonnet 4, temp=0       │
│    → Review: architecture compliance, magic numbers, tests              │
│    → Returns: { review: { verdict: "approved" }, status: "reviewing" }  │
│                                                                         │
│  STEP 13: Edge routes to validator                                      │
│  ──────────────────────────────                                         │
│  after_review(state) → "validator"                                      │
│                                                                         │
│  STEP 14: Validator runs tests                                          │
│  ──────────────────────────────                                         │
│  validator_node(state):                                                 │
│    → Run: pio build -e native ✅                                        │
│    → Run: pio test -e native ✅ (14 passed, 0 failed)                  │
│    → Returns: { validation: { build_passed, tests_passed } }            │
│                                                                         │
│  STEP 15: Edge routes to knowledge (success)                            │
│  ────────────────────────────────────────────                           │
│  after_validation(state) → "knowledge"                                  │
│                                                                         │
│  STEP 16: Knowledge agent learns + indexes                              │
│  ──────────────────────────────────────────                             │
│  knowledge_node(state):                                                 │
│    → Store patterns in codebase-memory                                  │
│    → Update changelog                                                   │
│    → Returns: { status: "completed" }                                   │
│                                                                         │
│  STEP 17: Graph reaches END                                             │
│  ──────────────────────────                                             │
│  Final state returned to CLI → display result to human                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Request Flow Summary Table

| Step | Component | Action | Calls |
|---|---|---|---|
| 1 | Human | Submit task | CLI |
| 2 | CLI | Create state | LangGraph |
| 3 | Orchestrator Node | Classify + route | 9Router (DeepSeek, classify) |
| 4 | Context Node | Resolve tiers | Brain Reader + Memory MCP |
| 5 | Edge | Route to planner | — |
| 6 | Planner Node | Generate specs | 9Router → OpenRouter → GPT-5 |
| 7 | Edge | Route to gate | — |
| 8 | Human Gate | Wait + approve | CLI (factory approve) |
| 9 | Edge | Route to agent | — |
| 10 | Engineer Node | Execute code | OpenCode → OpenRouter → Claude |
| 11 | Edge | Route to review | — |
| 12 | Reviewer Node | Check code | 9Router → OpenRouter → Claude |
| 13 | Edge | Route to validate | — |
| 14 | Validator Node | Run tests | Terminal (pio test) |
| 15 | Edge | Route to learn | — |
| 16 | Knowledge Node | Store patterns | Codebase Memory MCP |
| 17 | END | Return result | CLI → Human |


---

## 2. Complete Context Flow

### How context travels from Brain to LLM

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT FLOW                                      │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ SOURCE: Project Brain (.raceos/)                          │           │
│  │                                                          │           │
│  │  01-vision/     → NOT loaded (irrelevant for code tasks) │           │
│  │  02-product/    → Loaded for product/planning tasks      │           │
│  │  03-engineering/→ ALWAYS loaded (Tier 1)                  │           │
│  │  08-ai/         → Loaded for AI/governance tasks         │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │ read-only                                  │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ KNOWLEDGE AGENT                                           │           │
│  │                                                          │           │
│  │  1. Verifies Brain docs are indexed                      │           │
│  │  2. Checks for stale documents                           │           │
│  │  3. Validates cross-references (ADR→Spec links)          │           │
│  │  4. Flags conflicts if any detected                      │           │
│  │                                                          │           │
│  │  Output: validation_status (ok | stale | conflict)       │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ OPENSPEC PARSER                                           │           │
│  │                                                          │           │
│  │  Input: openspec/specs/<domain>/spec.md                  │           │
│  │                                                          │           │
│  │  Extracts:                                               │           │
│  │    - Requirements (SHALL/SHOULD/MAY)                     │           │
│  │    - Scenarios (GIVEN/WHEN/THEN)                         │           │
│  │    - Acceptance criteria (from THEN clauses)             │           │
│  │    - Keyword strengths + priorities                      │           │
│  │                                                          │           │
│  │  Output: Spec objects + AcceptanceReport                 │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ CONTEXT AGENT (Tier Resolution)                           │           │
│  │                                                          │           │
│  │  Task type: "firmware" → apply reading order:            │           │
│  │                                                          │           │
│  │  TIER 1 (always, ~2K tokens):                            │           │
│  │    ├── .ai/steering.md (engineering mission)             │           │
│  │    └── .raceos/03-engineering/engineering-principles.md   │           │
│  │                                                          │           │
│  │  TIER 2 (domain, ~3K tokens):                            │           │
│  │    ├── openspec/specs/firmware-core/spec.md              │           │
│  │    └── adr/ADR-relevant.md (matched by keyword)          │           │
│  │                                                          │           │
│  │  TIER 3 (target files, ~5K tokens):                      │           │
│  │    ├── firmware/core/watchdog.h (if exists)              │           │
│  │    └── firmware/core/system_clock.h (pattern reference)  │           │
│  │                                                          │           │
│  │  TIER 4 (memory, ~1K tokens):                            │           │
│  │    └── codebase-memory: "IClock pattern", "HAL interface"│           │
│  │                                                          │           │
│  │  Budget enforcement: total ≤ 12K tokens                  │           │
│  │  Truncation order: T3 first → T4 → T2 → T1 (never trim)│           │
│  │                                                          │           │
│  │  Output: ContextBundle { tier1, tier2, tier3, tier4 }    │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ LANGGRAPH STATE (carries context through DAG)             │           │
│  │                                                          │           │
│  │  state.context = {                                       │           │
│  │    tier1_content: "...",  tier1_tokens: 1850,            │           │
│  │    tier2_content: "...",  tier2_tokens: 2900,            │           │
│  │    tier3_content: "...",  tier3_tokens: 4200,            │           │
│  │    tier4_content: "...",  tier4_tokens: 800,             │           │
│  │    total_tokens: 9750,                                   │           │
│  │    sources: ["steering.md", "firmware-core/spec.md", ...]│           │
│  │  }                                                       │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ OPENCODE SESSION (receives context as system prompt)      │           │
│  │                                                          │           │
│  │  system_prompt = compose(tier1 + tier2 + tier3 + tier4)  │           │
│  │  + adapter.constraints                                   │           │
│  │  + acceptance_criteria (from OpenSpec)                    │           │
│  │                                                          │           │
│  │  Total system prompt: ~11K tokens                        │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ 9ROUTER (selects model based on task metadata)            │           │
│  │                                                          │           │
│  │  Input: { task_type: "coding", complexity: "high" }      │           │
│  │  Rule match: coding → claude-sonnet-latest               │           │
│  │  Budget check: 45% used → no downgrade                   │           │
│  │  Timeout: coding → 120s                                  │           │
│  │                                                          │           │
│  │  Output: RouteResult {                                   │           │
│  │    model_id: "anthropic/claude-sonnet-4.6",              │           │
│  │    max_tokens: 8192,                                     │           │
│  │    temperature: 0.1,                                     │           │
│  │    timeout: 120                                          │           │
│  │  }                                                       │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ OPENROUTER (dumb HTTP pipe)                               │           │
│  │                                                          │           │
│  │  POST https://openrouter.ai/api/v1/chat/completions     │           │
│  │  Headers:                                                │           │
│  │    Authorization: Bearer sk-or-v1-...                    │           │
│  │    X-Title: RaceOS Factory                               │           │
│  │  Body:                                                   │           │
│  │    model: "anthropic/claude-sonnet-4.6"                  │           │
│  │    messages: [system_prompt + user_task]                  │           │
│  │    max_tokens: 8192                                      │           │
│  │    temperature: 0.1                                      │           │
│  │                                                          │           │
│  │  Retry: 429 → wait 1s → retry | 5xx → wait 2s → retry  │           │
│  │  Fallback: claude-sonnet-4.6 fails → claude-sonnet-4    │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ LLM RESPONSE                                              │           │
│  │                                                          │           │
│  │  Content: generated code / analysis / spec               │           │
│  │  Usage: { prompt_tokens: 11420, completion_tokens: 3200 }│           │
│  │  Cost: $0.11                                             │           │
│  │  Latency: 4.2s                                           │           │
│  └──────────────────────────┬───────────────────────────────┘           │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ RESPONSE FLOWS BACK UP THE CHAIN                          │           │
│  │                                                          │           │
│  │  LLM → OpenRouter → OpenCode → LangGraph state          │           │
│  │  → Reviewer → Validator → Knowledge Agent → Human        │           │
│  │                                                          │           │
│  │  Cost tracked: 9Router.record_usage(...)                 │           │
│  │  Patterns stored: codebase-memory.store_pattern(...)     │           │
│  │  Changelog updated: knowledge_node(...)                  │           │
│  └──────────────────────────────────────────────────────────┘           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Context Flow Per Task Type

| Task Type | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Model |
|---|---|---|---|---|---|
| Firmware coding | steering + principles | firmware-core spec + ADR | target .cpp/.h files | HAL patterns | Claude |
| Architecture | steering + foundations | all related specs + ADRs | — | historical decisions | GPT-5 |
| Planning | steering + principles | existing specs | — | — | GPT-5 |
| Documentation | steering | related specs | target docs | — | Gemini |
| Classification | steering (minimal) | — | — | — | DeepSeek |
| Review | steering + foundations | relevant spec | diff content | code patterns | Claude |

### Context Budget Allocation

```
┌──────────────────────────────────────────────────────────┐
│  Model Context Window: 200K tokens (Claude Sonnet 4.6)    │
│                                                          │
│  ┌────────────────────────────────────┐                  │
│  │ System prompt (context):  ~11K     │ ← Our budget     │
│  │   Tier 1:  2K (principles)         │                  │
│  │   Tier 2:  3K (domain spec)        │                  │
│  │   Tier 3:  5K (source files)       │                  │
│  │   Tier 4:  1K (memory patterns)    │                  │
│  ├────────────────────────────────────┤                  │
│  │ Task prompt:              ~2K      │                  │
│  ├────────────────────────────────────┤                  │
│  │ Reserved for output:      ~8K      │                  │
│  ├────────────────────────────────────┤                  │
│  │ UNUSED (headroom):       ~179K     │                  │
│  └────────────────────────────────────┘                  │
│                                                          │
│  Why so conservative: quality > quantity.                 │
│  Research shows focused context outperforms dumping.      │
└──────────────────────────────────────────────────────────┘
```


---

## 3. Sequence Diagrams

### 3.1 Complete Happy Path (Complex Task)

```
Human        CLI       LangGraph   Knowledge   Context    9Router   Planner   HumanGate  Engineer   OpenCode   OpenRouter    LLM       Reviewer   Validator  KnowledgeAg
  │           │           │           │          │          │          │          │          │          │           │          │           │          │          │
  │──task────►│           │           │          │          │          │          │          │          │           │          │           │          │          │
  │           │──invoke──►│           │          │          │          │          │          │          │           │          │           │          │          │
  │           │           │                      │          │          │          │          │          │           │          │           │          │          │
  │           │           │──classify────────────────────── ►│          │          │          │          │           │          │           │          │          │
  │           │           │◄─DeepSeek(type=high)─────────── │          │          │          │          │           │          │           │          │          │
  │           │           │                      │          │          │          │          │          │           │          │           │          │          │
  │           │           │──validate────────── ►│          │          │          │          │          │           │          │           │          │          │
  │           │           │◄─ok──────────────── │          │          │          │          │          │           │          │           │          │          │
  │           │           │                      │          │          │          │          │          │           │          │           │          │          │
  │           │           │──resolve tiers────────────────► │          │          │          │          │           │          │           │          │          │
  │           │           │◄─ContextBundle(11K)──────────── │          │          │          │          │           │          │           │          │          │
  │           │           │                                 │          │          │          │          │           │          │           │          │          │
  │           │           │──route(planning)─────────────── ►│          │          │          │          │           │          │           │          │          │
  │           │           │◄─GPT-5, 8K, t=0.3────────────── │          │          │          │          │           │          │           │          │          │
  │           │           │                                            │          │          │          │           │          │           │          │          │
  │           │           │──plan(context+task)────────────────────── ►│          │          │          │           │          │           │          │          │
  │           │           │                                            │          │          │          │           │          │           │          │          │
  │           │           │                                            │──────────────────────────────────────────► │          │           │          │          │
  │           │           │                                            │◄─────────────────── completion ──────────── │          │           │          │          │
  │           │           │                                            │          │          │          │           │          │           │          │          │
  │           │           │◄─proposal.md + tasks.md────────────────── │          │          │          │           │          │           │          │          │
  │           │           │                                                       │          │          │           │          │           │          │          │
  │           │           │──await approval──────────────────────────────────────►│          │          │           │          │           │          │          │
  │◄──review──│◄──notify──│                                                       │          │          │           │          │           │          │          │
  │           │           │                                                       │          │          │           │          │           │          │          │
  │──approve─►│──approve─►│                                                       │          │          │           │          │           │          │          │
  │           │           │◄─approved─────────────────────────────────────────────│          │          │           │          │           │          │          │
  │           │           │                                                                  │          │           │          │           │          │          │
  │           │           │──route(coding)──────────────────────────── ►│                    │          │           │          │           │          │          │
  │           │           │◄─Claude 4.6, 8K, t=0.1─────────────────── │                    │          │           │          │           │          │          │
  │           │           │                                                                  │          │           │          │           │          │          │
  │           │           │──execute(context+plan+model)──────────────────────── ►│          │           │          │           │          │          │
  │           │           │                                                        │──spawn─►│           │          │           │          │          │
  │           │           │                                                        │         │──POST───► │──call───►│           │          │          │
  │           │           │                                                        │         │◄─resp──── │◄─resp────│           │          │          │
  │           │           │                                                        │         │  (edit files, run tests)         │          │          │
  │           │           │                                                        │◄─result─│           │          │           │          │          │
  │           │           │◄─ExecutionResult(files, tests)───────────────────────── │          │           │          │           │          │          │
  │           │           │                                                                              │           │          │           │          │          │
  │           │           │──review(diff+spec)──────────────────────────────────────────────────────────────────────►│           │          │          │
  │           │           │                                                                              │           │──POST───►│          │          │
  │           │           │                                                                              │           │◄─resp────│          │          │
  │           │           │◄─verdict:approved──────────────────────────────────────────────────────────────────────── │           │          │          │
  │           │           │                                                                                                      │          │          │
  │           │           │──validate(build+test)─────────────────────────────────────────────────────────────────────────────── ►│          │
  │           │           │◄─passed(14/14)──────────────────────────────────────────────────────────────────────────────────────── │          │
  │           │           │                                                                                                                 │          │
  │           │           │──learn(patterns)──────────────────────────────────────────────────────────────────────────────────────────────── ►│
  │           │           │◄─indexed───────────────────────────────────────────────────────────────────────────────────────────────────────── │
  │           │           │                                                                                                                            │
  │           │◄─done─────│                                                                                                                            │
  │◄─result──│           │                                                                                                                            │
```

### 3.2 Failure + Retry + Fallback

```
Human     LangGraph    9Router     OpenCode    OpenRouter     LLM        9Router(fb)  OpenRouter(fb)   LLM(fb)
  │          │            │           │            │           │             │              │             │
  │──task──► │            │           │            │           │             │              │             │
  │          │──route────►│           │            │           │             │              │             │
  │          │◄─Claude4.6─│           │            │           │             │              │             │
  │          │            │           │            │           │             │              │             │
  │          │──execute──────────────►│            │           │             │              │             │
  │          │            │           │──POST─────►│           │             │              │             │
  │          │            │           │◄─429 RATE─ │           │             │              │             │
  │          │            │           │  (retry 1s)│           │             │              │             │
  │          │            │           │──POST─────►│           │             │              │             │
  │          │            │           │◄─429 RATE─ │           │             │              │             │
  │          │            │           │  (retry 2s)│           │             │              │             │
  │          │            │           │──POST─────►│           │             │              │             │
  │          │            │           │◄─429 RATE─ │           │             │              │             │
  │          │            │           │            │           │             │              │             │
  │          │◄─FAILED (retries exhausted)─────── │            │           │             │              │             │
  │          │            │           │            │           │             │              │             │
  │          │──fallback─────────────────────────────────────────────────── ►│              │             │
  │          │◄─Claude4.0 (different provider instance)────────────────────  │              │             │
  │          │            │           │            │           │             │              │             │
  │          │──execute(Claude4.0)───►│            │           │             │              │             │
  │          │            │           │────────────────────────────────────────────────────►│             │
  │          │            │           │◄───────────────────────────────── completion ───────│             │
  │          │            │           │            │           │             │              │             │
  │          │◄─SUCCESS───│           │            │           │             │              │             │
  │◄─done────│            │           │            │           │             │              │             │
```

### 3.3 Budget Degradation

```
Human     LangGraph    9Router     CostTracker
  │          │            │            │
  │──task──► │            │            │
  │          │──route────►│            │
  │          │            │──check────►│
  │          │            │◄─92% used──│
  │          │            │            │
  │          │            │  DOWNGRADE: gpt-5 → claude-sonnet-latest
  │          │            │  (budget > 90% threshold)
  │          │            │            │
  │          │◄─claude-sonnet-latest   │
  │          │  (was_downgraded=true)  │
  │          │  (reason="Budget 92%")  │
  │          │            │            │
  │          │  ... execute with cheaper model ...
  │          │            │            │
  │          │──record───────────────► │
  │          │            │◄─$0.08─────│
  │          │            │  (93% used)│
  │◄─done────│            │            │
```

### 3.4 Context Injection Detail

```
Brain        SpecParser   ContextAgent   MemoryMCP    Tokenizer     LangGraph
  │              │             │              │            │             │
  │◄─read T1────────────────── │              │            │             │
  │─steering.md──────────────► │              │            │             │
  │─principles.md─────────────►│              │            │             │
  │              │             │              │            │             │
  │              │◄─read T2────│              │            │             │
  │              │─spec.md────►│              │            │             │
  │              │             │              │            │             │
  │              │             │──query T4───►│            │             │
  │              │             │◄─patterns────│            │             │
  │              │             │              │            │             │
  │              │             │──count──────────────────► │             │
  │              │             │◄─T1:1850, T2:2900, T4:800│             │
  │              │             │  total: 5550 (within 12K) │             │
  │              │             │              │            │             │
  │              │             │──────── ContextBundle ──────────────── ►│
  │              │             │              │            │             │
```


---

## 4. Configuration Wiring

### How configs connect components

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION MAP                              │
│                                                                 │
│  .env                                                           │
│    └── OPENROUTER_API_KEY ──► gateway/client.py (auth)          │
│                                                                 │
│  config/router.yaml                                             │
│    ├── catalog ──────────► router/policy.py (model info)        │
│    ├── policy.rules ─────► router/policy.py (routing rules)     │
│    ├── fallback.chains ──► router/fallback.py (fallback logic)  │
│    ├── retry ────────────► gateway/retry.py (backoff config)    │
│    ├── timeout ──────────► router/router.py (per-model/task)    │
│    └── cost ─────────────► router/cost.py (budget limits)       │
│                                                                 │
│  config/factory.yaml                                            │
│    ├── brain.root ───────► context/brain_reader.py (path)       │
│    ├── openspec.* ───────► spec_engine/parser.py (paths)        │
│    ├── executor.* ───────► executor/session.py (timeout, bin)   │
│    └── workflow.* ───────► orchestrator/graph.py (concurrency)  │
│                                                                 │
│  config/opencode.json                                           │
│    ├── tools.file ───────► executor/tools.py (FILE_TOOL)        │
│    ├── tools.terminal ───► executor/tools.py (TERMINAL_TOOL)    │
│    ├── tools.git ────────► executor/tools.py (GIT_TOOL)         │
│    ├── tools.patch ──────► executor/tools.py (PATCH_TOOL)       │
│    └── safety ───────────► executor/session.py (guardrails)     │
│                                                                 │
│  config/memory.yaml                                             │
│    ├── server ───────────► memory/client.py (MCP connection)    │
│    ├── indexing ─────────► memory/indexer.py (paths, chunks)    │
│    ├── search ───────────► memory/search.py (thresholds)        │
│    ├── symbols ──────────► memory/symbols.py (patterns)         │
│    ├── dependencies ─────► memory/dependencies.py (layers)      │
│    └── context_builder ──► memory/context_builder.py (budget)   │
│                                                                 │
│  config/openspec.yaml                                           │
│    ├── parser ───────────► spec_engine/parser.py (markers)      │
│    ├── task_graph ───────► spec_engine/task_graph.py (rules)    │
│    ├── validation ───────► spec_engine/validator.py (checks)    │
│    ├── acceptance ───────► spec_engine/acceptance.py (format)   │
│    └── generator ────────► spec_engine/generator.py (model)     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Complete `.env` for Full System

```bash
# === REQUIRED ===
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GITHUB_TOKEN=ghp_your-token-here

# === OPTIONAL OVERRIDES ===
DAILY_BUDGET_USD=50.00
PER_TASK_BUDGET_USD=5.00
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Wiring: How a Task Flows Through Config

```yaml
# STEP 1: Task arrives → factory.yaml determines workflow behavior
factory:
  workflow:
    enable_auto_approve_simple: true    # Simple tasks skip gate

# STEP 2: Classification → router.yaml selects model
policy:
  rules:
    - match: { task_type: "coding" }
      model: "claude-sonnet-latest"     # Claude for code

# STEP 3: Context → memory.yaml + factory.yaml determine what to load
memory:
  context_builder:
    budget_tokens: 1000                 # Max 1K for Tier 4
factory:
  brain:
    root: "../.raceos/"                 # Where to read Brain

# STEP 4: Planning → openspec.yaml controls spec generation
openspec:
  generator:
    model: "anthropic/claude-sonnet-4.6"
    temperature: 0.3                    # Creative for specs

# STEP 5: Execution → opencode.json controls what tools are available
{
  "tools": {
    "terminal": {
      "allowedCommands": ["pio build *", "pio test *"]
    },
    "git": {
      "branchPrefix": "factory/",
      "blockMainCommit": true
    }
  }
}

# STEP 6: Retry → router.yaml controls retry + fallback
retry:
  max_attempts: 3
  backoff:
    type: "exponential"
    base_delay_ms: 1000

fallback:
  chains:
    claude-sonnet-latest:
      - "claude-sonnet"               # Same provider, older
      - "gpt-5"                       # Different provider
      - "deepseek-reasoner"           # Cheapest capable

# STEP 7: Cost → router.yaml enforces budget
cost:
  budget:
    daily_limit_usd: 50.00
  degradation:
    - threshold_pct: 90
      action: "downgrade"
      downgrade_map:
        gpt-5: "claude-sonnet-latest"
```

### Minimal Working Configuration

For a fresh setup that gets the system running:

```yaml
# config/router.yaml (minimal)
gateway:
  base_url: "https://openrouter.ai/api/v1"
  api_key_env: "OPENROUTER_API_KEY"

catalog:
  claude-sonnet-latest:
    id: "anthropic/claude-sonnet-4.6"
    provider: "anthropic"
    context_window: 200000
    cost_per_1k_input: 0.004
    cost_per_1k_output: 0.020
    latency_class: "normal"

policy:
  rules:
    - match: { task_type: "coding" }
      model: "claude-sonnet-latest"
      max_tokens: 8192
      temperature: 0.1
  default:
    model: "claude-sonnet-latest"
    max_tokens: 4096

fallback:
  chains:
    claude-sonnet-latest: []

retry:
  max_attempts: 3
  backoff:
    type: "exponential"
    base_delay_ms: 1000

timeout:
  per_model:
    claude-sonnet-latest: 60

cost:
  budget:
    daily_limit_usd: 50.00
```

### Integration Test Command

```bash
# Verify complete chain works:
cd /Users/mirza/Documents/MIRZA/RaceOS/raceos-factory

# 1. Config loads
PYTHONPATH=src python3 -c "
from factory.router import NineRouter
router = NineRouter.from_config('config/router.yaml')
result = router.route(task_type='coding')
print(f'✅ Route: {result.model_id} ({result.timeout_seconds}s timeout)')

result = router.route(task_type='architecture')
print(f'✅ Route: {result.model_id} (architecture)')

result = router.route(task_type='batch')
print(f'✅ Route: {result.model_id} (batch)')

print(f'✅ Budget: {router.get_budget_status().pct_used}% used')
"

# 2. Full chain (requires OPENROUTER_API_KEY)
source .env
PYTHONPATH=src python3 -c "
from factory.router import NineRouter
from factory.gateway import GatewayClient, CompletionRequest, Message

# Route
router = NineRouter.from_config('config/router.yaml')
route = router.route(task_type='classification')
print(f'Model: {route.model_id}, Timeout: {route.timeout_seconds}s')

# Call
client = GatewayClient(default_timeout=route.timeout_seconds)
resp = client.complete(CompletionRequest(
    model=route.model_id,
    messages=[Message(role='user', content='Say OK')],
    max_tokens=route.max_tokens,
    temperature=route.temperature,
))
print(f'Response: {resp.content}')
print(f'Tokens: {resp.usage.prompt_tokens}in / {resp.usage.completion_tokens}out')
print(f'Latency: {resp.latency_seconds:.2f}s')

# Record cost
router.record_usage(
    model_key=route.model_key,
    input_tokens=resp.usage.prompt_tokens,
    output_tokens=resp.usage.completion_tokens,
)
print(f'Budget: {router.get_budget_status().spent_today_usd:.4f} USD spent')
client.close()
print('✅ Complete chain verified!')
"
```

---

*End of Integration Document*
