"""
Architect Node — System Design & Spec Generation.

Designs technical solutions, generates OpenSpec artifacts, and drafts ADRs.
Uses GPT-5 (best reasoning) for architectural decisions.

READS from state:
    - task.description, task.domain
    - context (full bundle — principles + existing specs)
    - routing (model from 9Router)

WRITES to state:
    - plan: { proposal, design, tasks, task_breakdown, artifacts_dir }
    - execution: { output, modified_files }
    - status: "executing"
    - current_node: "architect"
    - history: append "architect"

DEPENDENCIES (injected):
    - router: NineRouter
    - gateway: GatewayClient
    - spec_writer: SpecWriter (writes to openspec/changes/)
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from factory.orchestrator.state import FactoryState

log = structlog.get_logger()


def architect_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """
    Design systems and generate spec/ADR artifacts.

    Uses GPT-5 for deep reasoning about architecture decisions.
    Produces proposal.md + design.md + tasks.md in openspec/changes/.
    """
    task = state.get("task", {})
    context = state.get("context", {})
    routing = state.get("routing", {})

    description = task.get("description", "")
    domain = task.get("domain", "firmware")

    log.info("architect.designing", description=description[:60])

    # Compose prompt
    principles = context.get("tier1_content", "")[:2000]
    existing_specs = context.get("tier2_content", "")[:2000]

    prompt = f"""You are a systems architect for RaceOS (embedded motorsport platform).

## Architecture Principles
{principles}

## Existing Specifications
{existing_specs}

## Task
{description}

## Instructions
Design a technical solution. Produce:

1. **Proposal** (problem + scope + success criteria)
2. **Design** (interfaces, data flow, layer mapping)
3. **Task breakdown** (ordered implementation steps)

Respond with JSON:
{{
  "proposal": "markdown content for proposal.md",
  "design": "markdown content for design.md",
  "tasks": [
    {{"title": "...", "description": "...", "files": ["..."], "acceptance_criteria": ["..."], "complexity": "low|medium|high"}}
  ],
  "adr_needed": true/false,
  "adr_title": "ADR title if needed",
  "summary": "one sentence summary"
}}

Rules:
- Map to architecture layers (app/middleware/drivers/core)
- No dynamic allocation
- No magic numbers
- Host-native testable
- Reference existing specs where applicable
"""

    # Call LLM
    response_text = _call_llm(prompt, routing, router, gateway)

    if response_text is None:
        return _fallback_result(state, description)

    # Parse response
    result = _parse_architect_response(response_text, description, domain)

    log.info("architect.done", tasks=len(result.get("task_breakdown", [])))

    return {
        "plan": {
            "proposal": result.get("proposal", ""),
            "design": result.get("design", ""),
            "tasks": "",
            "task_breakdown": result.get("task_breakdown", []),
            "artifacts_dir": result.get("artifacts_dir", ""),
            "estimated_cost_usd": 0.0,
            "refined_target_files": _extract_files(result.get("task_breakdown", [])),
        },
        "execution": {
            "modified_files": [],
            "output": result.get("summary", "Architecture design produced."),
            "token_usage": result.get("token_usage", {}),
            "learnings": [],
        },
        "status": "executing",
        "current_node": "architect",
        "history": state.get("history", []) + ["architect"],
    }


def _call_llm(prompt: str, routing: dict, router, gateway) -> str | None:
    """Call the architecture LLM (GPT-5)."""
    try:
        if router is None or gateway is None:
            from factory.services import get_router
            from factory.services import _get_gateway
            router = get_router()
            gateway = _get_gateway()

        route = router.route(task_type="architecture")

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
            task_type="architecture",
        )
        gateway.close()
        return response.content

    except Exception as e:
        log.error("architect.llm_failed", error=str(e))
        return None


def _parse_architect_response(response: str, description: str, domain: str) -> dict:
    """Parse JSON response from architect LLM."""
    try:
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text)

        # Write artifacts to openspec/changes/
        artifacts_dir = _write_artifacts(description, data)

        return {
            "proposal": data.get("proposal", ""),
            "design": data.get("design", ""),
            "task_breakdown": data.get("tasks", []),
            "artifacts_dir": artifacts_dir,
            "summary": data.get("summary", "Design complete."),
        }
    except (json.JSONDecodeError, IndexError) as e:
        log.warning("architect.parse_failed", error=str(e))
        return {"summary": response[:200], "task_breakdown": []}


def _write_artifacts(description: str, data: dict) -> str:
    """Write generated specs to openspec/changes/."""
    import re
    slug = re.sub(r"[^a-z0-9\s-]", "", description.lower())[:50]
    slug = re.sub(r"\s+", "-", slug).strip("-")

    output_dir = Path("../openspec/changes") / slug
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        if data.get("proposal"):
            (output_dir / "proposal.md").write_text(data["proposal"], encoding="utf-8")
        if data.get("design"):
            (output_dir / "design.md").write_text(data["design"], encoding="utf-8")
        return str(output_dir)
    except OSError:
        return ""


def _extract_files(task_breakdown: list) -> list[str]:
    """Extract target files from task breakdown."""
    files = []
    for task_item in task_breakdown:
        files.extend(task_item.get("files", []))
    return list(set(files))[:10]


def _fallback_result(state: FactoryState, description: str) -> dict:
    """Return fallback when LLM unavailable."""
    return {
        "plan": {"proposal": "", "design": "", "tasks": "", "task_breakdown": [], "artifacts_dir": ""},
        "execution": {"modified_files": [], "output": f"Architecture LLM unavailable for: {description[:80]}", "token_usage": {}, "learnings": []},
        "status": "failed",
        "error": "Architecture LLM unavailable",
        "current_node": "architect",
        "history": state.get("history", []) + ["architect"],
    }
