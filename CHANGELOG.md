# Changelog

All notable changes to raceos-factory will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [1.0.0] — 2026-07-30

### Added
- Complete AI Software Factory with 11 LangGraph nodes
- `raceos` CLI with 14 commands (feature, firmware, hardware, mobile, docs, review, research, telemetry, doctor, install, update, status, config, logs)
- Interactive shell with intent detection, slash commands, tab completion
- 9Router intelligent model routing (GPT-5/Claude/Gemini/DeepSeek)
- OpenCode executor integration with 3 domain adapters (firmware, mobile, backend)
- OpenSpec engine (parser, validator, task graph, acceptance criteria)
- Codebase memory integration (indexer, semantic search, symbols, dependencies)
- Context injection pipeline with 4-tier budget system (12K tokens max)
- Budget enforcement with daily/per-task limits and graceful degradation
- Crash recovery via SQLite checkpointing
- Human approval gates for complex/critical tasks
- Retry with model escalation (3 attempts, cross-provider fallback)
- Agent visualization during execution
- Auto-suggest follow-up tasks for bug fixes
- Auto-persist documentation output suggestions
- Output sanitization (ANSI, injection markers, control chars)
- Environment variable filtering for subprocess security
- Cost ledger with monthly rotation
- Full documentation (14 docs, architecture through installation)
- Docker support (multi-stage build)
- GitHub Actions CI/CD (lint, test, build, publish)
- Homebrew formula template

### Architecture
- Zero circular dependencies
- Zero duplicate memory/context/planning
- Single responsibility per component
- Config-driven behavior (7 YAML/JSON files)
- Clean layered architecture: CLI → Bridge → Orchestrator → Agents → Executor → Gateway

## [Unreleased]

### Planned
- `raceos chat` (open-ended conversation)
- `raceos init` (project setup wizard)
- Async task execution
- Multi-user support
- Web dashboard
