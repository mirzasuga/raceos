# .raceos/ — Project Brain Pointer

> This directory is a **pointer** to the canonical Project Brain.

## Location of Canonical Brain

The real Project Brain lives at:

```
../../../.raceos/
```

(Relative to this factory repository at `RaceOS/raceos-factory/.raceos/`)

Or equivalently: `/Users/mirza/Documents/MIRZA/RaceOS/.raceos/`

## Why This Directory Exists

This `.raceos/` directory exists to:

1. Signal to AI agents that this is a RaceOS sub-project
2. Provide a quick reference to the Brain structure
3. Document which Brain sections the factory reads

## What the Factory Reads

| Brain Section | Used By | Purpose |
|---|---|---|
| `03-engineering/engineering-principles.md` | Context Resolver (Tier 1) | Always-on constraints |
| `03-engineering/architecture-foundations.md` | Context Resolver (Tier 1) | Batasan lintas-fondasi |
| `08-ai/ai-workflow.md` | Planning Node | Workflow orchestration reference |
| `08-ai/ai-governance.md` | Human Gate logic | Approval rules |
| `02-product/` | Planning Node (Tier 2) | Product context for spec generation |

## Rules

- **IMMUTABLE**: The factory NEVER writes to the Brain.
- **READ-ONLY**: The `BrainReader` class enforces this programmatically.
- **PATH-SAFE**: Path traversal attacks are rejected.
- **CONFIGURABLE**: Brain path is set in `config/factory.yaml` → `brain.root`
