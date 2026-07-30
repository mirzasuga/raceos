# RaceOS AI Software Factory

> AI-native software factory for the RaceOS motorsport platform.

## Architecture

```
Project Brain (.raceos/) — Immutable Source of Truth
         ↓
    OpenSpec (specs/) — Behavioral Contracts
         ↓
    Planning — Context-aware task decomposition
         ↓
    Implementation — Isolated execution via OpenCode
         ↓
    Verification — Automated validation + human gates
```

## Stack

| Component | Role |
|---|---|
| OpenCode | AI coding agent (executor) |
| OpenRouter | LLM API gateway |
| 9Router | Intelligent model routing |
| LangGraph | Workflow orchestration |
| Codebase Memory MCP | Implementation memory |
| OpenSpec | Spec-driven planning |

## Quick Start

```bash
# Install dependencies
make setup

# Run tests
make test

# Run lint
make lint

# Submit a task
factory task "fix typo in ecu_parser.h" --domain firmware
```

## Project Structure

```
raceos-factory/
├── config/           Configuration (YAML)
├── src/factory/      Source code (Python)
│   ├── gateway/      OpenRouter thin wrapper
│   ├── router/       9Router model selection
│   ├── context/      Context injection pipeline
│   ├── orchestrator/ LangGraph DAG
│   ├── executor/     OpenCode integration
│   ├── memory/       Codebase Memory MCP client
│   ├── spec_engine/  OpenSpec generation
│   └── cli/          Command-line interface
├── langgraph/        Orchestrator graph definitions
├── specs/            OpenSpec artifacts
├── .raceos/          Project Brain pointer
├── .ai/              AI steering context
└── tests/            Test suite
```

## Documentation

- [Architecture](../docs/architecture/ai-software-factory.md)
- [Roadmap](../docs/architecture/ai-factory-roadmap.md)
- [Implementation Guide](../docs/architecture/ai-factory-implementation-guide.md)

## Principles

- **Brain is immutable** — Factory never writes to `.raceos/`
- **Spec first** — Complex tasks generate specs before execution
- **AI suggests, human decides** — Human gates on all critical decisions
- **Single responsibility** — Each component does one thing
- **No duplicated context** — One canonical source per data class
