"""
Orchestrator Node — Classification & Routing.

The first node in every workflow. Determines:
    1. Task type (coding, debugging, documentation, architecture, etc.)
    2. Complexity (low, medium, high, critical)
    3. Target agent (engineer, architect, hardware, etc.)
    4. Whether planning is needed
    5. Whether human gate is required

Uses 9Router for model selection (DeepSeek for classification — cheapest).
Falls back to rule-based classification if LLM fails.

READS from state:
    - task.description
    - task.domain
    - task.target_files
    - task.priority

WRITES to state:
    - classification: { task_type, complexity, domain, target_agent, requires_planning, requires_human_gate, reasoning }
    - routing: { model_key, model_id, max_tokens, temperature }
    - status: "classifying"
    - current_node: "orchestrator"
    - history: append "orchestrator"

DEPENDENCIES (injected):
    - router: NineRouter (for model selection + LLM-based classification)
    - gateway: GatewayClient (for LLM call)
"""

from __future__ import annotations

import json
import structlog

from factory.orchestrator.state import FactoryState

log = structlog.get_logger()

# --- Rule-based fallback classification (no LLM needed) ---

_TYPE_PATTERNS = {
    "debugging": ["fix", "bug", "debug", "why", "broken", "error", "crash", "always", "never", "wrong"],
    "documentation": ["how", "what", "explain", "describe", "document", "diagram", "wiring"],
    "architecture": ["architect", "redesign", "migrate", "refactor major", "rethink"],
    "spec_writing": ["spec", "specification", "define", "requirement", "adr"],
    "review": ["review", "check", "audit", "inspect"],
    "research": ["research", "interview", "market", "user", "competitor"],
    "data_telemetry": ["data", "telemetry", "pipeline", "stream", "analytics"],
}

_COMPLEXITY_SIGNALS = {
    "low": {"short_desc": 50, "keywords": ["fix", "typo", "rename", "update", "comment", "bump"]},
    "high": {"long_desc": 80, "keywords": ["implement", "add", "create", "build", "design", "new"]},
    "critical": {"keywords": ["architecture", "safety", "production", "security", "migrate"]},
}

_AGENT_MAP = {
    "coding": "engineer",
    "debugging": "engineer",
    "refactoring": "engineer",
    "documentation": "engineer",  # Routed to engineer but with Gemini model
    "architecture": "architect",
    "spec_writing": "architect",
    "review": "engineer",  # Review agent handles post-execution
    "research": "research",
    "data_telemetry": "data_telemetry",
    "hardware": "hardware",
}


def orchestrator_node(
    state: FactoryState,
    router=None,
    gateway=None,
) -> dict:
    """
    Classify the task and determine routing.

    Strategy:
    1. Try LLM-based classification (structured output, cheap model)
    2. Fall back to rule-based if LLM fails or is unavailable
    3. Determine target agent from task type + domain
    4. Set planning/gate requirements from complexity

    Args:
        state: Current workflow state.
        router: NineRouter instance (injected for testing).
        gateway: GatewayClient instance (injected for testing).

    Returns:
        Partial state update with classification + routing.
    """
    task = state.get("task", {})
    description = task.get("description", "")
    domain = task.get("domain", "firmware")
    priority = task.get("priority", "normal")

    log.info("orchestrator.classifying", description=description[:80], domain=domain)

    # --- Attempt LLM classification ---
    classification = None
    try:
        classification = _classify_via_llm(description, domain, router, gateway)
    except Exception as e:
        log.warning("orchestrator.llm_classification_failed", error=str(e))

    # --- Fallback to rule-based ---
    if classification is None:
        classification = _classify_rule_based(description, domain, priority)

    # --- Resolve target agent ---
    target_agent = _resolve_agent(classification["task_type"], domain)
    classification["target_agent"] = target_agent

    # --- Determine planning and gate requirements ---
    complexity = classification["complexity"]
    classification["requires_planning"] = complexity in ("high", "critical")
    classification["requires_human_gate"] = complexity in ("high", "critical")

    # Override: priority=critical always needs gate
    if priority == "critical":
        classification["requires_human_gate"] = True

    # --- Get routing decision for downstream nodes ---
    routing = _get_routing(classification["task_type"], complexity, router)

    log.info(
        "orchestrator.classified",
        task_type=classification["task_type"],
        complexity=complexity,
        target_agent=target_agent,
        requires_planning=classification["requires_planning"],
        model=routing.get("model_id", ""),
    )

    return {
        "classification": classification,
        "routing": routing,
        "status": "classifying",
        "current_node": "orchestrator",
        "history": state.get("history", []) + ["orchestrator"],
    }


# --- LLM Classification ---


def _classify_via_llm(description: str, domain: str, router, gateway) -> dict | None:
    """
    Use a cheap LLM to classify the task (structured JSON output).

    Returns None if LLM is unavailable or fails to parse.
    """
    if router is None or gateway is None:
        # Try to load from config (non-injected path)
        try:
            from factory.router.router import NineRouter
            from factory.gateway.client import GatewayClient
            router = NineRouter.from_config("config/router.yaml")
            gateway = GatewayClient()
        except Exception:
            return None

    # Route to cheapest model for classification
    route = router.route(task_type="classification")

    prompt = f"""Classify this software development task.

Task: "{description}"
Domain: {domain}

Respond with JSON only:
{{
  "task_type": "coding|debugging|documentation|architecture|spec_writing|review|research|data_telemetry|hardware",
  "complexity": "low|medium|high|critical",
  "reasoning": "one sentence why"
}}"""

    from factory.gateway.models import CompletionRequest, Message
    try:
        response = gateway.complete(CompletionRequest(
            model=route.model_id,
            messages=[Message(role="user", content=prompt)],
            max_tokens=route.max_tokens,
            temperature=0.0,
        ))

        # Parse JSON from response
        data = json.loads(response.content.strip())
        result = {
            "task_type": data.get("task_type", "coding"),
            "complexity": data.get("complexity", "medium"),
            "domain": domain,
            "reasoning": data.get("reasoning", "LLM classification"),
        }

        # Record cost
        router.record_usage(
            model_key=route.model_key,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            task_type="classification",
        )

        return result

    except (json.JSONDecodeError, KeyError, Exception) as e:
        log.debug("orchestrator.llm_parse_failed", error=str(e))
        return None
    finally:
        try:
            gateway.close()
        except Exception:
            pass


# --- Rule-based Classification (fallback) ---


def _classify_rule_based(description: str, domain: str, priority: str) -> dict:
    """
    Deterministic classification using keyword patterns.

    Always succeeds — this is the fallback when LLM is unavailable.
    """
    desc_lower = description.lower()

    # Detect task type
    task_type = "coding"  # default
    for ttype, keywords in _TYPE_PATTERNS.items():
        if any(kw in desc_lower for kw in keywords):
            task_type = ttype
            break

    # Hardware domain override
    if domain == "hardware":
        task_type = "hardware" if task_type == "coding" else task_type

    # Detect complexity
    complexity = "medium"  # default
    desc_len = len(description)

    if any(kw in desc_lower for kw in _COMPLEXITY_SIGNALS["low"]["keywords"]) and desc_len < 50:
        complexity = "low"
    elif any(kw in desc_lower for kw in _COMPLEXITY_SIGNALS["high"]["keywords"]) and desc_len > 80:
        complexity = "high"
    elif any(kw in desc_lower for kw in _COMPLEXITY_SIGNALS["critical"]["keywords"]):
        complexity = "critical"

    # Priority override
    if priority == "critical":
        complexity = "critical"
    elif priority == "high" and complexity == "low":
        complexity = "medium"

    return {
        "task_type": task_type,
        "complexity": complexity,
        "domain": domain,
        "reasoning": f"Rule-based: type={task_type} from keywords, complexity={complexity} from length+keywords",
    }


# --- Agent Resolution ---


def _resolve_agent(task_type: str, domain: str) -> str:
    """Map task type + domain to target agent name."""
    # Domain override
    if domain == "hardware":
        return "hardware"

    return _AGENT_MAP.get(task_type, "engineer")


# --- Routing ---


def _get_routing(task_type: str, complexity: str, router) -> dict:
    """Get model routing for downstream execution."""
    if router is None:
        # Default routing without 9Router
        return {
            "model_key": "claude-sonnet-latest",
            "model_id": "anthropic/claude-sonnet-4.6",
            "max_tokens": 8192,
            "temperature": 0.1,
        }

    try:
        route = router.route(task_type=task_type, complexity=complexity)
        return {
            "model_key": route.model_key,
            "model_id": route.model_id,
            "max_tokens": route.max_tokens,
            "temperature": route.temperature,
        }
    except Exception:
        return {
            "model_key": "claude-sonnet-latest",
            "model_id": "anthropic/claude-sonnet-4.6",
            "max_tokens": 8192,
            "temperature": 0.1,
        }
