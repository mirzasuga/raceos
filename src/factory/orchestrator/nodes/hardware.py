"""
Hardware Node — Hardware Design & Analysis.

Handles wiring diagrams, BOM, pinout, power architecture questions.
Uses Gemini (long context + documentation strength).

READS: task.description, context (hardware docs + specs)
WRITES: execution.output (hardware analysis/diagram)
"""

from __future__ import annotations

import structlog
from factory.orchestrator.state import FactoryState
from factory.orchestrator.nodes.data_telemetry import _call_domain_llm

log = structlog.get_logger()


def hardware_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """Hardware design, wiring, BOM, and pinout analysis via LLM."""
    task = state.get("task", {})
    context = state.get("context", {})

    description = task.get("description", "")
    brain_context = (
        context.get("tier1_content", "") + "\n" +
        context.get("tier2_content", "") + "\n" +
        context.get("tier3_content", "") + "\n" +
        context.get("tier4_content", "")
    )

    log.info("hardware.analyzing", description=description[:60])

    prompt = f"""You are a hardware engineer for RaceOS (motorsport embedded platform).

## Hardware Context
{brain_context[:5000]}

## Hardware Task
{description}

## Instructions
Provide a detailed hardware analysis. Include as appropriate:
- Wiring diagram (ASCII art)
- Pin assignments (table format)
- Power considerations (voltage rails, current budget)
- Signal integrity (cable length, shielding, baud rates)
- Component selection (with rationale)
- Risk assessment (thermal, EMI, sourcing)
- Safety warnings

Base all answers on actual hardware docs and datasheets.
Do NOT invent pin numbers — reference existing board_config.h.
Use ASCII diagrams (no images).
Respond in the user's language if not English.
"""

    output = _call_domain_llm(prompt, "documentation", state.get("routing", {}), router, gateway)

    return {
        "execution": {
            "modified_files": [],
            "output": output or f"Hardware LLM unavailable for: {description[:80]}",
            "token_usage": {},
            "learnings": [],
        },
        "status": "executing" if output else "failed",
        "error": None if output else "Hardware LLM unavailable",
        "current_node": "hardware",
        "history": state.get("history", []) + ["hardware"],
    }
