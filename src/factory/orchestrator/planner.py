"""
Planner Node.

Decomposes complex tasks into structured execution plans.
The planner reads Brain context + existing specs, then produces:
  - proposal.md (why)
  - design.md (how)
  - tasks.md (what steps)

This node sits between context resolution and execution.
Only invoked for MEDIUM/HIGH/CRITICAL complexity tasks.

After planning produces target_files in tasks.md,
the planner outputs a `refined_target_files` list. If this differs
from the initial guess, the execution node should reload Tier 3
with the planner-identified files (lazy Tier 3 reload).

READS from state:
    - task.description, task.domain
    - classification.complexity, classification.task_type
    - context (full ContextBundle)
    - routing (model to use for planning)

WRITES to state:
    - plan (PlanArtifacts)
    - plan.refined_target_files (list — for lazy Tier 3 reload)
    - status = "planning"
    - current_node = "planner"
    - history += ["planner"]
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from factory.orchestrator.state import FactoryState

log = structlog.get_logger()


def planner_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """
    Plan node — generates spec artifacts before execution.

    For complex tasks:
    1. Reads Brain principles (from context.tier1)
    2. Reads existing domain specs (from context.tier2)
    3. Generates proposal (problem + scope + criteria)
    4. Generates task breakdown (ordered steps + acceptance)
    5. Optionally generates design doc (for HIGH/CRITICAL)
    6. Writes artifacts to openspec/changes/<task>/

    Returns plan artifacts for human review (if gate required).
    """
    task = state.get("task", {})
    classification = state.get("classification", {})
    context = state.get("context", {})
    routing = state.get("routing", {})

    description = task.get("description", "")
    domain = task.get("domain", "firmware")
    complexity = classification.get("complexity", "medium")

    log.info("planner.planning", description=description[:60], complexity=complexity)

    # Compose context for the planning prompt
    principles = context.get("tier1_content", "")[:2000]
    specs = context.get("tier2_content", "")[:2000]

    # Determine what to generate based on complexity
    generate_design = complexity in ("high", "critical")

    # Call LLM for planning
    plan_data = _generate_plan_via_llm(
        description, domain, principles, specs, generate_design, routing, router, gateway
    )

    if plan_data is None:
        # Fallback: return empty plan (planner unavailable)
        log.warning("planner.llm_unavailable")
        return _empty_plan_result(state)

    # Write artifacts to disk
    artifacts_dir = _write_plan_artifacts(description, plan_data)

    # Extract refined target files from task breakdown
    refined_files = _extract_target_files(plan_data.get("tasks", []))

    # Estimate cost for human approval display
    estimated_cost = _estimate_execution_cost(plan_data.get("tasks", []), routing)

    log.info("planner.done", tasks=len(plan_data.get("tasks", [])), artifacts_dir=artifacts_dir)

    return {
        "plan": {
            "proposal": plan_data.get("proposal", ""),
            "design": plan_data.get("design", ""),
            "tasks": json.dumps(plan_data.get("tasks", []), indent=2),
            "task_breakdown": plan_data.get("tasks", []),
            "artifacts_dir": artifacts_dir,
            "estimated_cost_usd": estimated_cost,
            "refined_target_files": refined_files,
        },
        "status": "planning",
        "current_node": "planner",
        "history": state.get("history", []) + ["planner"],
    }


def _generate_plan_via_llm(
    description: str,
    domain: str,
    principles: str,
    specs: str,
    generate_design: bool,
    routing: dict,
    router,
    gateway,
) -> dict | None:
    """Call LLM to generate structured plan."""
    try:
        if router is None or gateway is None:
            from factory.services import get_router
            from factory.services import _get_gateway
            router = get_router()
            gateway = _get_gateway()

        route = router.route(task_type="planning", complexity="high")

        design_instruction = ""
        if generate_design:
            design_instruction = '\n  "design": "markdown technical design (interfaces, data flow, layer mapping)",'

        prompt = f"""You are a software planner for RaceOS (embedded motorsport platform).

## Principles
{principles}

## Existing Specifications
{specs}

## Task to Plan
{description}
Domain: {domain}

## Instructions
Produce a structured execution plan. Respond with JSON only:
{{
  "proposal": "markdown proposal (problem statement + scope + success criteria + constraints)",{design_instruction}
  "tasks": [
    {{
      "title": "task title",
      "description": "what to do",
      "files": ["path/to/file.cpp"],
      "acceptance_criteria": ["criterion 1", "criterion 2"],
      "complexity": "low|medium|high"
    }}
  ]
}}

Rules:
- Tasks should be ordered by dependency (do first things first)
- Each task should be independently verifiable
- Include test-writing as explicit tasks
- Reference actual file paths where known
- Keep to 3-7 tasks maximum
"""

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
            task_type="planning",
        )
        gateway.close()

        # Parse JSON response
        text = response.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        return json.loads(text)

    except (json.JSONDecodeError, Exception) as e:
        log.warning("planner.llm_failed", error=str(e))
        return None


def _write_plan_artifacts(description: str, plan_data: dict) -> str:
    """Write generated plan artifacts to openspec/changes/."""
    slug = re.sub(r"[^a-z0-9\s-]", "", description.lower())[:50]
    slug = re.sub(r"\s+", "-", slug).strip("-") or "unnamed-plan"

    output_dir = Path("../openspec/changes") / slug
    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        proposal = plan_data.get("proposal", "")
        if proposal:
            (output_dir / "proposal.md").write_text(proposal, encoding="utf-8")

        design = plan_data.get("design", "")
        if design:
            (output_dir / "design.md").write_text(design, encoding="utf-8")

        tasks = plan_data.get("tasks", [])
        if tasks:
            tasks_md = _format_tasks_markdown(tasks, description)
            (output_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")

        return str(output_dir)
    except OSError as e:
        log.warning("planner.write_failed", error=str(e))
        return ""


def _format_tasks_markdown(tasks: list[dict], title: str) -> str:
    """Format task breakdown as markdown."""
    lines = [f"# Task Breakdown: {title}", ""]
    for i, task in enumerate(tasks, 1):
        lines.append(f"## Task {i}: {task.get('title', 'Unnamed')}")
        lines.append(f"\n**Files:** {', '.join(task.get('files', ['TBD']))}")
        lines.append(f"**Complexity:** {task.get('complexity', 'medium')}")
        lines.append(f"\n{task.get('description', '')}")
        lines.append("\n**Acceptance Criteria:**")
        for ac in task.get("acceptance_criteria", []):
            lines.append(f"- [ ] {ac}")
        lines.append("")
    return "\n".join(lines)


def decompose_tasks(plan_content: str) -> list[dict]:
    """
    Parse a generated tasks.md into structured task list.

    Each task has:
        - title: str
        - description: str
        - files: list[str]
        - acceptance_criteria: list[str]
        - domain: str
        - complexity: str
    """
    try:
        return json.loads(plan_content)
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_target_files(tasks: list[dict]) -> list[str]:
    """Extract all target files from task breakdown for Tier 3 reload."""
    files: list[str] = []
    for task in tasks:
        files.extend(task.get("files", []))
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for f in files:
        if f not in seen and f != "TBD":
            seen.add(f)
            unique.append(f)
    return unique[:10]


def _estimate_execution_cost(tasks: list[dict], routing: dict) -> float:
    """
    Estimate total cost for executing the task breakdown.

    Uses per-task token estimation × model pricing.
    Rough estimate for human approval display.
    """
    if not tasks:
        return 0.0

    # Estimate ~2000 input + 1000 output tokens per task
    estimated_tokens_per_task = 3000
    total_tokens = len(tasks) * estimated_tokens_per_task

    # Use routing model cost (approximate)
    # Claude Sonnet 4.6: $0.004/1K input + $0.020/1K output
    input_cost = (total_tokens * 0.67 / 1000) * 0.004  # ~67% input
    output_cost = (total_tokens * 0.33 / 1000) * 0.020  # ~33% output

    return round(input_cost + output_cost, 4)


def _empty_plan_result(state: FactoryState) -> dict:
    """Return empty plan when LLM is unavailable."""
    return {
        "plan": {
            "proposal": "",
            "design": "",
            "tasks": "",
            "task_breakdown": [],
            "artifacts_dir": "",
            "estimated_cost_usd": 0.0,
            "refined_target_files": [],
        },
        "status": "planning",
        "current_node": "planner",
        "history": state.get("history", []) + ["planner"],
    }
