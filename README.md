# RaceOS AI Software Factory

> AI-native software factory for the RaceOS motorsport platform.

[![PyPI](https://img.shields.io/pypi/v/raceos-factory)](https://pypi.org/project/raceos-factory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   Human: "implement engine load gauge"                              │
│     │                                                               │
│     ▼                                                               │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│   │   CLI    │───►│ 9Router  │───►│ LangGraph│───►│ OpenCode │    │
│   │ (raceos) │    │(select   │    │(orchestr)│    │(execute) │    │
│   └──────────┘    │ model)   │    └──────────┘    └──────────┘    │
│                   └──────────┘         │                │          │
│                        │               ▼                ▼          │
│                        │         ┌──────────┐    ┌──────────┐     │
│                        │         │  Brain   │    │LLM Gateway│     │
│                        │         │(.raceos/)│    │(9Router│     │
│                        │         └──────────┘    │ / 9Router)│     │
│                        │                         └──────────┘     │
│                        │                              │            │
│                        ▼                              ▼            │
│                   ┌──────────────────────────────────────┐        │
│                   │  LLM (Claude / GPT-5 / Gemini / DS)  │        │
│                   └──────────────────────────────────────┘        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Complete Flow

```
Human
  │
  │  $ raceos firmware "fix load always showing 100%"
  │
  ▼
┌─ CLI ──────────────────────────────────────────────────────────────┐
│  1. Parse input → intent: "debug", domain: "firmware"              │
│  2. Create task → TASK-A1B2C3                                      │
│  3. Save checkpoint (crash recovery)                               │
└────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─ 9Router (model selection) ────────────────────────────────────────┐
│  4. Task type: debugging → select Claude Sonnet 4.6, temp=0        │
│  5. Check budget: $3.42/$50.00 (OK, no downgrade)                  │
│  6. Set timeout: 120s                                              │
└────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─ LangGraph (orchestration) ────────────────────────────────────────┐
│                                                                    │
│  7. ORCHESTRATOR → classify: type=debugging, complexity=medium     │
│  │                                                                 │
│  8. CONTEXT AGENT → load tiered context:                           │
│  │   Tier 1: .raceos/ principles (cached)              2K tokens  │
│  │   Tier 2: openspec/specs/display-dashboard/         3K tokens  │
│  │   Tier 3: firmware/middleware/telemetry_parser.cpp   4K tokens  │
│  │   Tier 4: codebase memory patterns                  1K tokens  │
│  │                                                                 │
│  9. ENGINEER → dispatch to OpenCode                                │
│  │                                                                 │
│  10. REVIEWER → verify code quality (Claude, temp=0)               │
│  │                                                                 │
│  11. VALIDATOR → trust executor (tests already passed)             │
│  │                                                                 │
│  12. KNOWLEDGE → store patterns + suggest follow-ups               │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─ OpenCode (execution) ─────────────────────────────────────────────┐
│  13. Receive: context (10K tokens) + task + constraints            │
│  14. Tools: file.read → file.write → terminal.run → git.commit    │
│  15. LLM calls → via Gateway → Claude generates fix               │
│  16. Run: pio build ✅ → pio test ✅ (16 passed)                    │
│  17. Commit: [factory] fix: convert raw byte to percentage         │
└────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─ LLM Gateway (HTTP) ──────────────────────────────────────────────┐
│  18. POST /chat/completions → model: claude-sonnet-4.6             │
│  19. Retry: 429→backoff, 5xx→retry, 400→fail                      │
│  20. Fallback: Claude fails → try GPT-5 → try DeepSeek            │
│  21. Cost: track tokens, record to ledger                          │
└────────────────────────────────────────────────────────────────────┘
  │
  ▼
Human sees:
  ✅ Fixed: raw byte (0-255) not converted to percentage
  📁 Modified: telemetry_parser.cpp, board_config.h, test_telemetry_parser.cpp
  💰 Cost: $0.20
  ⏱️  Duration: 44s
  💡 Follow-up: "check if rpm, temp, duty also need conversion"
```

---

## Components

| Component | Role | Location |
|---|---|---|
| **CLI** | Human interface (15 commands + shell) | `src/factory/cli/` |
| **9Router** | Select model + enforce budget | `src/factory/router/` |
| **LangGraph** | Orchestrate 11 AI agents | `src/factory/orchestrator/` |
| **OpenCode** | Execute code via MCP tools | `src/factory/executor/` |
| **LLM Gateway** | HTTP proxy to LLM providers | `src/factory/gateway/` |
| **Context Agent** | Load Brain + specs + memory | `src/factory/context/` |
| **OpenSpec** | Parse/generate specs | `src/factory/spec_engine/` |
| **Codebase Memory** | Store implementation patterns | `src/factory/memory/` |
| **Project Brain** | Immutable knowledge (read-only) | `../.raceos/` |

---

## Install

```bash
pip install raceos-factory
```

## Setup

```bash
# 1. Get LLM API key (choose one gateway):
#    9Router: https://9router.ai/keys
#    9Router:    https://9router.ai

# 2. Configure
cd your-raceos-project/raceos-factory
cp .env.example .env
# Edit .env → add your API key

# 3. Verify
raceos doctor
```

See [LLM Gateway Setup Guide](docs/llm-gateway-setup.md) for detailed options.

---

## Usage

### Interactive Shell

```bash
$ raceos

raceos> implement engine load gauge
raceos> fix typo in ecu_parser.h
raceos> how to wire display to stm32
raceos> /status
raceos> /budget
raceos> /quit
```

### Direct Commands

```bash
raceos feature "add BLE support" --domain firmware
raceos firmware "fix watchdog timeout"
raceos hardware "wiring diagram for racepanel"
raceos docs "explain HAL interfaces"
raceos review
raceos doctor
raceos install
raceos update
```

---

## AI Agents (11)

| Agent | Handles | Model |
|---|---|---|
| Orchestrator | Classify + route tasks | DeepSeek (cheap) |
| Context | Load Brain + specs + memory | No LLM (file I/O) |
| Planner | Generate specs before execution | GPT-5 |
| Engineer | Write/fix code | Claude |
| Reviewer | Independent code review | Claude (temp=0) |
| Validator | Run build + tests | No LLM (subprocess) |
| Knowledge | Learn patterns + suggest follow-ups | No LLM |
| Architect | Design systems + ADRs | GPT-5 |
| Research | Market/user evidence | GPT-5 |
| Product | Problem definition + MVP | GPT-5 |
| Hardware | Wiring/BOM/pinout | Gemini |

---

## Cost

| Task Type | Cost | Time |
|---|---|---|
| Feature (complex) | $0.54 | ~56s |
| Bug fix | $0.20 | ~44s |
| Documentation | $0.13 | ~21s |
| Classification | $0.0001 | ~2s |

Daily budget: $50 (configurable). Auto-downgrades model when approaching limit.

---

## Architecture

```
Project Brain (.raceos/) ── read-only, immutable
         ↓
    OpenSpec (specs/) ── behavioral contracts
         ↓
    LangGraph (DAG) ── orchestrate 11 agents
         ↓
    OpenCode (tools) ── file, terminal, git, patch
         ↓
    9Router (rules) ── deterministic model selection
         ↓
    LLM Gateway ── HTTP to providers
         ↓
    LLM (Claude/GPT/Gemini/DeepSeek)
```

Zero circular dependencies. Single responsibility per component.

---

## Configuration

| File | Controls |
|---|---|
| `.env` | API key (secret) |
| `config/router.yaml` | Model routing + budget + fallback + retry |
| `config/factory.yaml` | Paths + workflow + logging |
| `config/opencode.json` | Execution tools + safety |
| `config/context-tiers.yaml` | Context budgets per tier |
| `config/memory.yaml` | Codebase memory indexing |
| `config/openspec.yaml` | Spec engine settings |

See [CONFIG_INDEX.md](config/CONFIG_INDEX.md) for "I want to change X → edit this file".

---

## Documentation

| Doc | Purpose |
|---|---|
| [LLM Gateway Setup](docs/llm-gateway-setup.md) | Choose + configure gateway |
| [Architecture](docs/system-flow.md) | Complete system flow |
| [CLI Design](docs/cli-design.md) | CLI commands + shell |
| [Integration](docs/integration.md) | How components connect |
| [Deployment](docs/deployment-handbook.md) | Production deployment |
| [CONFIG_INDEX](config/CONFIG_INDEX.md) | Configuration reference |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
