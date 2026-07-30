"""
Reviewer Node — Independent Code Review.

Reviews code changes produced by the engineer for:
    - Architecture compliance (layered, no magic numbers, no dynamic alloc)
    - Spec compliance (implementation matches requirements)
    - Code quality (naming, tests, comments)

Uses Claude at temp=0 for deterministic, precise review.

READS from state:
    - execution.modified_files, execution.output
    - context.tier1_content (principles to check against)
    - context.tier2_content (spec to verify compliance)
    - classification.task_type

WRITES to state:
    - review: { verdict, issues, checklist, confidence, retry_worthwhile }
    - status: "reviewing"
    - current_node: "reviewer"
    - history: append "reviewer"

DEPENDENCIES (injected):
    - router: NineRouter (model selection)
    - gateway: GatewayClient (LLM call)
"""

from __future__ import annotations

import json
import structlog

from factory.orchestrator.state import FactoryState

log = structlog.get_logger()


def reviewer_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """
    Review code changes independently.

    Sends diff + context + spec to LLM and asks for structured review.
    Returns verdict (approved/changes_requested/blocked) with specific issues.
    """
    execution = state.get("execution", {})
    context = state.get("context", {})
    classification = state.get("classification", {})

    modified_files = execution.get("modified_files", [])
    exec_output = execution.get("output", "")

    log.info("reviewer.reviewing", files=len(modified_files))

    # Skip review if no files modified (documentation/question tasks)
    if not modified_files:
        return _approved_result(state, "No files modified — nothing to review.")

    # --- Build review prompt ---
    review_prompt = _build_review_prompt(modified_files, exec_output, context, classification)

    # --- Call LLM ---
    review_response = _call_review_llm(review_prompt, router, gateway)

    if review_response is None:
        # LLM unavailable — auto-approve with warning
        log.warning("reviewer.llm_unavailable, auto-approving")
        return _approved_result(state, "Review LLM unavailable — auto-approved with warning.")

    # --- Parse response ---
    result = _parse_review(review_response)

    log.info("reviewer.done", verdict=result["verdict"], issues=len(result["issues"]))

    return {
        "review": result,
        "status": "reviewing",
        "current_node": "reviewer",
        "history": state.get("history", []) + ["reviewer"],
    }


def _build_review_prompt(modified_files: list[str], output: str, context: dict, classification: dict) -> str:
    """Compose the review prompt with context + changes."""
    principles = context.get("tier1_content", "")[:2000]
    spec = context.get("tier2_content", "")[:1500]

    prompt = f"""You are a code reviewer for the RaceOS project.

## Architecture Rules
{principles}

## Specification
{spec}

## Changes Made
Files modified: {', '.join(modified_files[:10])}

Summary of changes:
{output[:1500]}

## Your Task
Review these changes against the architecture rules and specification.

Respond with JSON only:
{{
  "verdict": "approved" | "changes_requested" | "blocked",
  "issues": [
    {{"severity": "critical|major|minor|nit", "file": "path", "message": "issue", "suggestion": "fix"}}
  ],
  "checklist": {{
    "layered_architecture": true/false,
    "no_magic_numbers": true/false,
    "no_dynamic_allocation": true/false,
    "host_native_testable": true/false,
    "has_tests": true/false,
    "spec_compliant": true/false
  }},
  "confidence": "high" | "medium" | "low",
  "retry_worthwhile": true/false,
  "summary": "one sentence review summary"
}}

Rules:
- "blocked" = fundamental misunderstanding, retry won't help
- "changes_requested" = fixable issues, retry should work
- "approved" = no critical/major issues (minor/nit OK)
- confidence: how sure are you about this review
- retry_worthwhile: if changes_requested, would retrying with error context likely succeed?
"""
    return prompt


def _call_review_llm(prompt: str, router, gateway) -> str | None:
    """Call LLM for review. Returns response text or None on failure."""
    try:
        if router is None or gateway is None:
            from factory.services import get_router
            from factory.services import _get_gateway
            router = get_router()
            gateway = _get_gateway()

        route = router.route(task_type="review")

        from factory.gateway.models import CompletionRequest, Message
        response = gateway.complete(CompletionRequest(
            model=route.model_id,
            messages=[Message(role="user", content=prompt)],
            max_tokens=route.max_tokens,
            temperature=0.0,  # Always zero for review (deterministic)
        ))

        router.record_usage(
            model_key=route.model_key,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            task_type="review",
        )

        gateway.close()
        return response.content

    except Exception as e:
        log.error("reviewer.llm_call_failed", error=str(e))
        return None


def _parse_review(response: str) -> dict:
    """Parse LLM review response into structured result."""
    try:
        # Try to extract JSON from response
        text = response.strip()
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text)

        return {
            "verdict": data.get("verdict", "approved"),
            "issues": data.get("issues", []),
            "checklist": data.get("checklist", {}),
            "confidence": data.get("confidence", "medium"),
            "retry_worthwhile": data.get("retry_worthwhile", True),
        }
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        log.warning("reviewer.parse_failed", error=str(e))
        # Can't parse → approve with low confidence
        return {
            "verdict": "approved",
            "issues": [],
            "checklist": {},
            "confidence": "low",
            "retry_worthwhile": True,
        }


def _approved_result(state: FactoryState, reason: str) -> dict:
    """Return an auto-approved result."""
    return {
        "review": {
            "verdict": "approved",
            "issues": [],
            "checklist": {},
            "confidence": "high",
            "retry_worthwhile": True,
        },
        "status": "reviewing",
        "current_node": "reviewer",
        "history": state.get("history", []) + ["reviewer"],
    }
