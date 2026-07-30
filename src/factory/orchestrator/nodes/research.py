"""
Research Node — Evidence Gathering & Synthesis.

Synthesizes market/user research evidence from Brain documents.
Uses GPT-5 for analytical reasoning.

READS: task.description, context (market/product docs)
WRITES: execution.output (research report)
"""

from __future__ import annotations

import structlog
from factory.orchestrator.state import FactoryState
from factory.orchestrator.nodes.data_telemetry import _call_domain_llm

log = structlog.get_logger()


def research_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """Gather and synthesize research evidence via LLM."""
    task = state.get("task", {})
    context = state.get("context", {})
    routing = state.get("routing", {})

    description = task.get("description", "")
    brain_context = context.get("tier1_content", "") + "\n" + context.get("tier2_content", "")

    log.info("research.analyzing", description=description[:60])

    prompt = f"""You are a research analyst for RaceOS (motorsport technology platform).

## Project Context
{brain_context[:3000]}

## Research Task
{description}

## Instructions
Produce an evidence-based analysis. Include:
- Key findings (with confidence: high/medium/low)
- Supporting evidence (cite sources if available)
- Knowledge gaps (what we don't know)
- Recommended next steps

Format as structured markdown report.
Be specific. Cite data. Flag assumptions explicitly.
"""

    output = _call_domain_llm(prompt, "research", routing, router, gateway)

    return {
        "execution": {
            "modified_files": [],
            "output": output or f"Research LLM unavailable for: {description[:80]}",
            "token_usage": {},
            "learnings": [],
        },
        "status": "executing" if output else "failed",
        "error": None if output else "Research LLM unavailable",
        "current_node": "research",
        "history": state.get("history", []) + ["research"],
    }
