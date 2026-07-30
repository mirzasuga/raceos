"""
Data/Telemetry Node — Data Pipeline Design.

Handles telemetry pipeline architecture, data schema design, and analytics.
Uses Claude for technical precision.

READS: task.description, context (protocol specs + architecture)
WRITES: execution.output (pipeline design)
"""

from __future__ import annotations

import structlog
from factory.orchestrator.state import FactoryState

log = structlog.get_logger()


def data_telemetry_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """Design data pipelines and telemetry architecture via LLM."""
    task = state.get("task", {})
    context = state.get("context", {})

    description = task.get("description", "")
    brain_context = context.get("tier1_content", "") + "\n" + context.get("tier2_content", "")

    log.info("data_telemetry.designing", description=description[:60])

    prompt = f"""You are a data/telemetry engineer for RaceOS (motorsport platform).

## System Context
{brain_context[:3000]}

## Telemetry Task
{description}

## Instructions
Design a data pipeline or telemetry solution. Include:
- Data flow diagram (source → transform → sink)
- Schema definitions (explicit, versioned)
- Real-time vs batch boundaries
- Bandwidth constraints (UART baud, BLE throughput)
- Validation rules (data integrity at ingestion)
- Storage strategy (retention, format)

Consider embedded constraints (limited memory, no dynamic alloc on MCU).
Format as structured markdown with diagrams where helpful.
"""

    output = _call_domain_llm(prompt, "coding", state.get("routing", {}), router, gateway)

    return {
        "execution": {
            "modified_files": [],
            "output": output or f"Telemetry LLM unavailable for: {description[:80]}",
            "token_usage": {},
            "learnings": [],
        },
        "status": "executing" if output else "failed",
        "error": None if output else "Telemetry LLM unavailable",
        "current_node": "data_telemetry",
        "history": state.get("history", []) + ["data_telemetry"],
    }


# ============================================================
# Shared helper: _call_domain_llm
# Used by research, product, hardware, data_telemetry nodes.
# ============================================================


def _call_domain_llm(
    prompt: str,
    task_type: str,
    routing: dict,
    router=None,
    gateway=None,
) -> str | None:
    """
    Call LLM for a domain-specific node.

    Delegates to factory.services.call_llm() which is the SOLE
    entry point for all LLM calls. 9Router selects model.
    Gateway handles transport. This function is just a thin wrapper
    for backward compatibility with injected test mocks.
    """
    # If mocks are injected (testing), use them directly
    if router is not None and gateway is not None:
        try:
            route = router.route(task_type=task_type)
            from factory.gateway.models import CompletionRequest, Message
            response = gateway.complete(CompletionRequest(
                model=route.model_id,
                messages=[Message(role="user", content=prompt)],
                max_tokens=route.max_tokens,
                temperature=route.temperature,
            ))
            router.record_usage(
                model_key=route.model_key,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                task_type=task_type,
            )
            gateway.close()
            return response.content
        except Exception as e:
            log.error("domain_llm.mock_failed", task_type=task_type, error=str(e))
            return None

    # Production path: use shared services (SOLE OWNER of router + gateway)
    from factory.services import call_llm
    return call_llm(task_type=task_type, prompt=prompt)
