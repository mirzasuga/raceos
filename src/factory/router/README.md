# Router

> Deterministic model routing based on task metadata and budget constraints.

## Responsibility

Selects the optimal model for each LLM call based on task type, complexity tier, and remaining budget. Uses rule-based logic (decision tables, not ML) to map task metadata to model choices. Enforces per-task and global budget constraints. Completely separate from OpenRouter — this is internal routing logic, OpenRouter is just the API provider.

## Does NOT

- Use an LLM to decide which model to use
- Make HTTP calls (that is Gateway's job)
- Access OpenRouter's routing features
- Handle authentication or retries
- Store or learn from past routing decisions

## Key Files (planned)

- `selector.py` — rule engine that maps task metadata → model ID
- `budget.py` — budget tracking and enforcement
- `rules.py` — routing rule definitions (from YAML config)
- `types.py` — task metadata schema, routing decision dataclass

## Dependencies

- `factory.config` (routing rules, model catalog, budget limits)
