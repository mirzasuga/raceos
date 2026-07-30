# Executor

> Spawns OpenCode as subprocess with context and constraints, parses results.

## Responsibility

Manages the lifecycle of OpenCode subprocess executions. Prepares execution context (instructions, constraints, relevant files), spawns OpenCode with appropriate configuration, monitors execution, and parses structured results. Domain adapters customize behavior for different project types (firmware C, mobile Kotlin/Swift, backend Python/Go).

## Does NOT

- Execute code directly (delegates to OpenCode)
- Make LLM calls (OpenCode handles its own LLM interaction)
- Decide what to execute (receives instructions from Orchestrator)
- Modify source files directly (OpenCode does the actual edits)

## Key Files (planned)

- `runner.py` — OpenCode subprocess lifecycle management
- `context_builder.py` — prepares execution context and constraints
- `result_parser.py` — parses OpenCode output into structured results
- `adapters/firmware.py` — firmware domain adapter (STM32, C, PlatformIO)
- `adapters/mobile.py` — mobile domain adapter
- `adapters/backend.py` — backend domain adapter

## Dependencies

- `factory.context` (assembled context bundles)
- `factory.config` (OpenCode paths, timeout settings)
- `subprocess` / `asyncio.subprocess` (process management)
