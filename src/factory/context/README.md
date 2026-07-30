# Context

> Deterministic resolver that assembles tiered context bundles from project knowledge.

## Responsibility

Loads context from multiple sources (Brain documents, OpenSpec specs, relevant files, codebase memory) and assembles them into token-budgeted context bundles. Uses a tiered priority system: mandatory context is always included, supplementary context fills remaining token budget. Resolution is fully deterministic — given the same task metadata, produces the same context bundle.

## Does NOT

- Use an LLM to select or summarize context
- Make decisions about what is relevant (uses rules and metadata)
- Generate or modify any content
- Manage the context sources themselves (only reads them)
- Exceed token budgets (hard cap enforcement)

## Key Files (planned)

- `resolver.py` — main resolver that assembles context bundles
- `sources.py` — adapters for each context source (brain, spec, files, memory)
- `budget.py` — token counting and budget allocation per tier
- `types.py` — context bundle, tier, and source dataclasses

## Dependencies

- `factory.memory` (codebase memory reads)
- `factory.config` (tier definitions, token budgets, source paths)
- `tiktoken` (token counting)
