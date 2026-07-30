# Orchestrator

> LangGraph DAG definition with state management and conditional edges.

## Responsibility

Defines the workflow graph as a LangGraph DAG. Manages workflow state transitions, conditional edge logic (e.g., approval gates, retry decisions), and coordinates node execution order. Each node in the graph delegates actual work to other modules — the orchestrator only decides *what* runs *when*.

## Does NOT

- Execute any domain logic (firmware compilation, code generation, etc.)
- Make LLM calls directly (nodes call Router → Gateway)
- Store persistent state (uses LangGraph's built-in checkpointing)
- Implement business rules beyond workflow control flow

## Key Files (planned)

- `graph.py` — main DAG definition and compilation
- `state.py` — TypedDict state schema for the workflow
- `edges.py` — conditional edge functions
- `nodes/plan.py` — planning node
- `nodes/execute.py` — execution node
- `nodes/review.py` — review node
- `nodes/learn.py` — learning/memory node

## Dependencies

- `langgraph` (graph framework)
- `factory.context` (context assembly for nodes)
- `factory.router` (model selection for LLM nodes)
- `factory.gateway` (LLM API calls)
- `factory.executor` (code execution delegation)
- `factory.memory` (learning node writes)
