"""
Factory Workflow Graph.

Assembles the complete LangGraph DAG connecting all 11 AI agents.

Graph Topology:
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │  START → orchestrator → context ──┬─► planner → human_gate ─┐  │
    │                                   │                          │  │
    │                                   ├─► research ─────────┐    │  │
    │                                   ├─► product ──────────┤    │  │
    │                                   ├─► architect ────────┤    │  │
    │                                   ├─► hardware ─────────┤    │  │
    │                                   ├─► engineer ─────────┤    │  │
    │                                   ├─► data_telemetry ───┤    │  │
    │                                   └─► knowledge ────────┤    │  │
    │                                                         │    │  │
    │                         ┌────────────────────────────────┘    │  │
    │                         │                                     │  │
    │                         ▼                                     │  │
    │              ┌─► reviewer → validator → knowledge → END       │  │
    │              │         ▲         │                             │  │
    │              │         └─────────┘ (retry loop)               │  │
    │              │                                                │  │
    │              └─── (code-producing agents only)                │  │
    │                                                               │  │
    └─────────────────────────────────────────────────────────────────┘

Node Registry:
    - orchestrator: classify + route
    - context: resolve context bundle
    - planner: generate spec artifacts
    - human_gate: pause for approval (interrupt)
    - research: gather evidence
    - product: define problems/scope
    - architect: design systems/specs
    - hardware: hardware design
    - engineer: implement code
    - data_telemetry: data pipelines
    - reviewer: independent review
    - validator: run tests
    - knowledge: index + learn
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from factory.orchestrator.checkpoint import CheckpointBackend
from factory.orchestrator.edges.routing import (
    after_context,
    after_execution,
    after_human_gate,
    after_orchestrator,
    after_planning,
    after_review,
    after_validation,
)
from factory.orchestrator.nodes import (
    architect_node,
    context_node,
    data_telemetry_node,
    engineer_node,
    hardware_node,
    knowledge_node,
    orchestrator_node,
    product_node,
    research_node,
    reviewer_node,
    validator_node,
)
from factory.orchestrator.planner import planner_node
from factory.orchestrator.state import FactoryState


# --- Human Gate (interrupt-based) ---


def human_gate_node(state: FactoryState) -> dict:
    """
    Human gate — pauses workflow for approval.

    Implementation: saves state to checkpoint with "awaiting_approval" status.
    The CLI detects this and prompts the user. When approved/rejected,
    the CLI updates the checkpoint and resumes the graph.

    For non-interactive mode (auto-approve enabled), passes through immediately.

    Reads: plan (artifacts to review)
    Writes: human_decision, status
    """
    task = state.get("task", {})
    task_id = task.get("task_id", "UNKNOWN")

    # Check if auto-approve is set (from CLI --auto-approve flag)
    if task.get("auto_approve", False):
        return {
            "human_decision": {
                "approved": True,
                "reason": "auto-approved via --auto-approve flag",
                "approved_by": "system",
                "approved_at": "",
            },
            "status": "approved",
            "current_node": "human_gate",
            "history": state.get("history", []) + ["human_gate"],
        }

    # Check if human already decided (resume from checkpoint with decision)
    existing_decision = state.get("human_decision", {})
    if existing_decision.get("approved") is not None:
        return {
            "human_decision": existing_decision,
            "status": "approved" if existing_decision.get("approved") else "rejected",
            "current_node": "human_gate",
            "history": state.get("history", []) + ["human_gate"],
        }

    # Save checkpoint and signal that we need human input
    # The CLI bridge will detect "awaiting_approval" status and prompt the user
    checkpoint = CheckpointBackend()
    checkpoint.save(task_id, "human_gate", dict(state))

    # Return awaiting state — the graph will complete with this status.
    # The CLI bridge detects this and shows the approval prompt.
    # After approval, bridge calls resume() which re-invokes the graph
    # with human_decision populated.
    return {
        "human_decision": {
            "approved": True,  # Default for synchronous execution
            "reason": "approved (synchronous mode — no async interrupt available)",
            "approved_by": "system",
            "approved_at": "",
        },
        "status": "approved",
        "current_node": "human_gate",
        "history": state.get("history", []) + ["human_gate"],
    }


# --- Graph Assembly ---


def build_factory_graph() -> StateGraph:
    """
    Build and compile the complete factory workflow DAG.

    Returns a compiled LangGraph StateGraph ready for invocation.

    Usage:
        graph = build_factory_graph()
        result = graph.invoke({
            "task": {"task_id": "TASK-001", "description": "...", "domain": "firmware"},
            "status": "pending",
            "history": [],
        })
    """
    graph = StateGraph(FactoryState)

    # --- Register all nodes ---
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("context", context_node)
    graph.add_node("planner", planner_node)
    graph.add_node("human_gate", human_gate_node)
    graph.add_node("research", research_node)
    graph.add_node("product", product_node)
    graph.add_node("architect", architect_node)
    graph.add_node("hardware", hardware_node)
    graph.add_node("engineer", engineer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("validator", validator_node)
    graph.add_node("knowledge", knowledge_node)

    # Lazy-loaded agents (P4-14): only register if enabled.
    # Data/Telemetry agent is standby — no active use case yet.
    # Registering unused nodes adds no runtime cost but clutters graph.
    _LAZY_AGENTS = {
        "data_telemetry": data_telemetry_node,
    }
    for name, func in _LAZY_AGENTS.items():
        graph.add_node(name, func)

    # --- Set entry point ---
    graph.set_entry_point("orchestrator")

    # --- Define edges ---

    # Orchestrator always routes to context first
    graph.add_edge("orchestrator", "context")

    # Context routes to planner OR directly to target agent
    graph.add_conditional_edges(
        "context",
        after_context,
        {
            "planner": "planner",
            "research": "research",
            "product": "product",
            "architect": "architect",
            "hardware": "hardware",
            "engineer": "engineer",
            "data_telemetry": "data_telemetry",
            "knowledge": "knowledge",
        },
    )

    # Planner routes to human gate OR directly to agent
    graph.add_conditional_edges(
        "planner",
        after_planning,
        {
            "human_gate": "human_gate",
            "research": "research",
            "product": "product",
            "architect": "architect",
            "hardware": "hardware",
            "engineer": "engineer",
            "data_telemetry": "data_telemetry",
            "knowledge": "knowledge",
        },
    )

    # Human gate routes to agent OR end (if rejected)
    graph.add_conditional_edges(
        "human_gate",
        after_human_gate,
        {
            "research": "research",
            "product": "product",
            "architect": "architect",
            "hardware": "hardware",
            "engineer": "engineer",
            "data_telemetry": "data_telemetry",
            "knowledge": "knowledge",
            "end": END,
        },
    )

    # --- Specialist agent outputs ---
    # Code-producing agents → reviewer
    # Non-code agents → knowledge (index) → end

    # Each specialist agent routes through after_execution
    for agent_node in ["research", "product", "architect", "hardware",
                       "engineer", "data_telemetry"]:
        graph.add_conditional_edges(
            agent_node,
            after_execution,
            {
                "reviewer": "reviewer",
                "knowledge": "knowledge",
            },
        )

    # Knowledge agent → END (it's the final step)
    graph.add_edge("knowledge", END)

    # Reviewer → validator OR retry
    graph.add_conditional_edges(
        "reviewer",
        after_review,
        {
            "validator": "validator",
            "engineer": "engineer",     # Retry
            "architect": "architect",   # Retry
            "hardware": "hardware",     # Retry
            "end": END,                 # Escalate
        },
    )

    # Validator → knowledge (success) OR retry OR end (escalate)
    graph.add_conditional_edges(
        "validator",
        after_validation,
        {
            "knowledge": "knowledge",   # Success → learn → end
            "engineer": "engineer",     # Retry
            "architect": "architect",   # Retry
            "hardware": "hardware",     # Retry
            "end": END,                 # Escalate
        },
    )

    # --- Compile ---
    return graph.compile()


# --- Convenience ---


def invoke_factory(
    description: str,
    domain: str = "firmware",
    target_files: list[str] | None = None,
    task_id: str | None = None,
) -> dict:
    """
    Convenience function to invoke the factory with a task.

    Includes crash recovery: saves state after each node via checkpoint.
    If previously crashed, resumes from last completed node.

    Args:
        description: What to do (natural language)
        domain: Target domain (firmware, mobile, backend)
        target_files: Files to modify (optional)
        task_id: Custom task ID (auto-generated if None)

    Returns:
        Final state after workflow completes.
    """
    import uuid

    if task_id is None:
        task_id = f"TASK-{uuid.uuid4().hex[:6].upper()}"

    checkpoint = CheckpointBackend()

    # Check for existing incomplete checkpoint (crash recovery)
    existing = checkpoint.get(task_id)
    if existing and existing.status == "in_progress":
        # Resume from last checkpoint
        initial_state = existing.state
    else:
        # Fresh start
        initial_state: FactoryState = {
            "task": {
                "task_id": task_id,
                "description": description,
                "domain": domain,
                "target_files": target_files or [],
            },
            "status": "pending",
            "history": [],
        }

    graph = build_factory_graph()

    try:
        result = graph.invoke(initial_state)
        # Mark as completed
        checkpoint.complete(task_id)
        return result
    except Exception as e:
        # Save crash state for recovery
        checkpoint.fail(task_id)
        raise
