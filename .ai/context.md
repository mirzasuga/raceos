# AI Context — RaceOS Factory

This directory provides AI steering for the factory repository.

## Reading Order

Before working on this factory:

1. Read `../docs/architecture/ai-software-factory.md` — full architecture
2. Read `../docs/architecture/ai-factory-roadmap.md` — implementation milestones
3. Read `../docs/architecture/ai-factory-implementation-guide.md` — step-by-step

## Source of Truth

The factory's source of truth is:

| Layer | Location | Access |
|---|---|---|
| Knowledge | `../.raceos/` (parent repo) | Read-only |
| Definition | `../openspec/specs/` | Read-only |
| Factory Config | `config/` | Read at startup |
| Implementation | `src/factory/` | This repo |
| Tests | `tests/` | This repo |

## Principles

- Factory never writes to Brain (`.raceos/`)
- Factory never writes to parent `openspec/specs/` (only to `openspec/changes/`)
- All architectural decisions come from Brain, not from factory memory
- AI suggests, human decides on all critical/complex tasks
- Spec first: complex tasks generate specs before execution

## Task Type Classification

| If working on... | Read... |
|---|---|
| Gateway/Router | `src/factory/gateway/README.md`, `config/router.yaml` |
| Context injection | `src/factory/context/README.md`, `config/context-tiers.yaml` |
| Orchestration | `src/factory/orchestrator/README.md`, `langgraph/` |
| Executor | `src/factory/executor/README.md`, `config/opencode.yaml` |
| Memory | `src/factory/memory/README.md`, `config/mcp-servers.yaml` |
| Specs | `src/factory/spec_engine/README.md` |
| CLI | `src/factory/cli/README.md` |
