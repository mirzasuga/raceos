"""
Product Node — Problem Definition & MVP Scoping.

Translates evidence into product decisions: problem statements, MVP scope,
success metrics. Uses GPT-5 for strategic reasoning.

READS: task.description, context (product/vision docs)
WRITES: execution.output (product brief)
"""

from __future__ import annotations

import structlog
from factory.orchestrator.state import FactoryState
from factory.orchestrator.nodes.data_telemetry import _call_domain_llm

log = structlog.get_logger()


def product_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """Define product problems, scope MVP, set success metrics via LLM."""
    task = state.get("task", {})
    context = state.get("context", {})

    description = task.get("description", "")
    brain_context = context.get("tier1_content", "") + "\n" + context.get("tier2_content", "")

    log.info("product.defining", description=description[:60])

    prompt = f"""You are a product strategist for RaceOS (motorsport technology platform).

## Project Context
{brain_context[:3000]}

## Product Task
{description}

## Instructions
Produce a structured product brief. Include:
- Problem statement (evidence-backed)
- Proposed scope (what's in / what's out)
- Success metrics (measurable)
- Priority rationale (impact × effort × risk)
- Constraints from project principles

Do NOT include technical implementation details.
Focus on WHAT is needed and WHY, not HOW to build it.
Format as structured markdown.
"""

    output = _call_domain_llm(prompt, "planning", state.get("routing", {}), router, gateway)

    return {
        "execution": {
            "modified_files": [],
            "output": output or f"Product LLM unavailable for: {description[:80]}",
            "token_usage": {},
            "learnings": [],
        },
        "status": "executing" if output else "failed",
        "error": None if output else "Product LLM unavailable",
        "current_node": "product",
        "history": state.get("history", []) + ["product"],
    }
