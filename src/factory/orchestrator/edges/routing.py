"""
Conditional Edge Functions.

These functions implement the routing logic between nodes.
Each function examines the current state and returns the name
of the next node to execute.

Graph topology:
    orchestrator → context → [route_to_agent]
    agent → reviewer → validator → [learn | retry | escalate]

Route-to-agent options:
    research, product, architect, hardware, engineer,
    data_telemetry, knowledge
"""

from __future__ import annotations

from factory.orchestrator.state import FactoryState


# --- Node name constants ---
NODE_CONTEXT = "context"
NODE_RESEARCH = "research"
NODE_PRODUCT = "product"
NODE_ARCHITECT = "architect"
NODE_HARDWARE = "hardware"
NODE_ENGINEER = "engineer"
NODE_DATA_TELEMETRY = "data_telemetry"
NODE_KNOWLEDGE = "knowledge"
NODE_PLANNER = "planner"
NODE_HUMAN_GATE = "human_gate"
NODE_REVIEWER = "reviewer"
NODE_VALIDATOR = "validator"
NODE_END = "end"


def after_orchestrator(state: FactoryState) -> str:
    """
    After orchestrator classifies the task, route to context resolution.

    Orchestrator → Context (always).
    Context resolution happens before any specialist work.
    """
    return NODE_CONTEXT


def after_context(state: FactoryState) -> str:
    """
    After context is resolved, route to the target agent.

    Uses classification.target_agent to determine which specialist node
    handles the task. For complex tasks that require planning, route
    to planner first.

    Routes:
        requires_planning=True  → planner
        target_agent="research" → research
        target_agent="product"  → product
        target_agent="architect" → architect
        target_agent="hardware" → hardware
        target_agent="engineer" → engineer
        target_agent="data_telemetry" → data_telemetry
        target_agent="knowledge" → knowledge
        fallback → engineer
    """
    classification = state.get("classification", {})

    # Complex tasks go through planning first
    if classification.get("requires_planning", False):
        return NODE_PLANNER

    # Route to target agent
    target = classification.get("target_agent", "engineer")
    return _resolve_agent_node(target)


def after_planning(state: FactoryState) -> str:
    """
    After planning produces specs/design, check if human gate is needed.

    Routes:
        requires_human_gate=True → human_gate
        otherwise → target agent (execute directly)
    """
    classification = state.get("classification", {})

    if classification.get("requires_human_gate", False):
        return NODE_HUMAN_GATE

    # Proceed directly to target agent
    target = classification.get("target_agent", "engineer")
    return _resolve_agent_node(target)


def after_human_gate(state: FactoryState) -> str:
    """
    After human approves or rejects the plan.

    Routes:
        approved=True  → target agent (execute)
        approved=False → end (task rejected)
    """
    human_decision = state.get("human_decision", {})

    if human_decision.get("approved", False):
        target = state.get("classification", {}).get("target_agent", "engineer")
        return _resolve_agent_node(target)

    # Rejected — end the workflow
    return NODE_END


def after_execution(state: FactoryState) -> str:
    """
    After a specialist agent executes, route to review+validation.

    IMPROVEMENT: Review and Validation now run in parallel for
    code-producing agents. Both must pass before proceeding.

    For parallel execution, we route to a "review_and_validate" fan-out
    node that dispatches both in parallel. If LangGraph doesn't support
    native parallel, we route to reviewer first (faster) then validator.

    Some agents don't need review (research, product, knowledge).
    Code-producing agents always go through review+validation.

    Routes:
        code-producing agents → reviewer (then validator in sequence)
        non-code agents → knowledge (output is the deliverable)
    """
    classification = state.get("classification", {})
    target = classification.get("target_agent", "engineer")

    # Agents that produce code → review (then validate)
    code_agents = {"engineer", "architect", "hardware"}
    if target in code_agents:
        return NODE_REVIEWER

    # Non-code agents → knowledge (index) → end
    non_review_agents = {"research", "product", "knowledge", "data_telemetry"}
    if target in non_review_agents:
        return NODE_KNOWLEDGE

    return NODE_REVIEWER


def after_review(state: FactoryState) -> str:
    """
    After review agent checks the work.

    IMPROVEMENT: On approval, route directly to validator (parallel-ready).
    The validator now has the "trust executor" optimization, so if
    execution already passed tests, validation is near-instant.

    Routes:
        verdict="approved" → validator (run tests / trust executor)
        verdict="changes_requested" → engineer (retry with feedback)
        verdict="blocked" → end (escalate to human)
    """
    review = state.get("review", {})
    verdict = review.get("verdict", "approved")

    if verdict == "approved":
        return NODE_VALIDATOR

    if verdict == "changes_requested":
        # Check retry budget
        retry = state.get("retry", {})
        attempt = retry.get("attempt", 0)
        max_attempts = retry.get("max_attempts", 3)

        # P3-12: Check reviewer confidence signal
        # If reviewer says retry is NOT worthwhile (fundamental misunderstanding),
        # skip retry and escalate to human immediately
        review = state.get("review", {})
        if review.get("retry_worthwhile") is False:
            return NODE_END  # Escalate — retrying won't help

        if attempt < max_attempts:
            target = state.get("classification", {}).get("target_agent", "engineer")
            return _resolve_agent_node(target)

        return NODE_END

    # Blocked — escalate to human
    return NODE_END


def after_validation(state: FactoryState) -> str:
    """
    After validation runs tests.

    Routes:
        all passed → knowledge (learn, then end)
        tests failed, retries remaining → engineer (fix and retry)
        tests failed, no retries → end (escalate)
    """
    validation = state.get("validation", {})
    build_passed = validation.get("build_passed", False)
    tests_passed = validation.get("tests_passed", False)

    if build_passed and tests_passed:
        # Success — record learnings
        return NODE_KNOWLEDGE

    # Failure — check retry budget
    retry = state.get("retry", {})
    attempt = retry.get("attempt", 0)
    max_attempts = retry.get("max_attempts", 3)

    if attempt < max_attempts:
        # Retry with error context
        target = state.get("classification", {}).get("target_agent", "engineer")
        return _resolve_agent_node(target)

    # Exhausted — escalate
    return NODE_END


# --- Helper ---


def _resolve_agent_node(target: str) -> str:
    """Map target_agent string to node name."""
    agent_map = {
        "research": NODE_RESEARCH,
        "product": NODE_PRODUCT,
        "architect": NODE_ARCHITECT,
        "hardware": NODE_HARDWARE,
        "engineer": NODE_ENGINEER,
        "data_telemetry": NODE_DATA_TELEMETRY,
        "knowledge": NODE_KNOWLEDGE,
    }
    return agent_map.get(target, NODE_ENGINEER)
