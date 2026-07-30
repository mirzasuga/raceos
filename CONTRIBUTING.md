# Contributing to RaceOS AI Factory

Thank you for your interest in contributing! This guide will help you get started.

## Quick Start (15 minutes)

```bash
git clone https://github.com/raceos/raceos-factory.git
cd raceos-factory
uv sync --all-extras
make test
make lint
uv run raceos doctor
```

## Development Setup

- **Python:** 3.11+ required
- **Package manager:** [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Lint/Format:** ruff (via `make lint` / `make fmt`)
- **Tests:** pytest (via `make test`)

## What to Contribute

| Type | Examples | Welcome? |
|---|---|---|
| 🐛 Bug fixes | Fix crash, correct behavior | Always |
| 📝 Documentation | Fix typos, add examples, clarify | Always |
| 🧪 Tests | Increase coverage, add edge cases | Always |
| 🔌 New domain adapter | Add FPGA, Rust, Go support | Yes (discuss first) |
| 🤖 Agent improvements | Better prompts, smarter routing | Yes (discuss first) |
| ✨ New features | New commands, integrations | Open issue first |

## Commit Convention

```
type(scope): description

feat(cli): add raceos chat command
fix(router): correct budget threshold calculation
docs(architecture): update sequence diagram
test(executor): add timeout edge case test
chore(deps): bump langgraph to 0.3.0
```

## Pull Request Process

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-change`
3. Make changes + write tests
4. Run: `make check` (lint + tests)
5. Commit with conventional commit format
6. Push + open PR against `main`
7. Fill out PR template
8. Wait for review (target: 48h response)

## Architecture Rules

These rules are enforced in code review:

- **No circular dependencies** (modules never import each other)
- **Single responsibility** (one file = one purpose)
- **Dependency injection** (nodes accept injected deps for testing)
- **Graceful degradation** (optional services fail silently, never crash)
- **Config over code** (deploy-time decisions in YAML, not hardcoded)
- **Brain is read-only** (factory never writes to `.raceos/`)

## Testing

```bash
make test          # Unit tests only
make test-cov      # With coverage report
make test-all      # Including slow/integration
```

## Questions?

- Open a [Discussion](https://github.com/raceos/raceos-factory/discussions)
- Check existing [Issues](https://github.com/raceos/raceos-factory/issues)
