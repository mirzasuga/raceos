"""
Factory Workflow State Schema.

Single source of truth for all data flowing through the LangGraph DAG.
Every node reads from and writes to this state. Fields use total=False
so nodes can incrementally build state without requiring all keys upfront.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TypedDict


# --- Enums ---


class TaskStatus(Enum):
    """Lifecycle status of a factory task."""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    VALIDATING = "validating"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class TaskType(Enum):
    """Classification of task purpose."""

    CODING = "coding"
    SPEC_WRITING = "spec_writing"
    ARCHITECTURE = "architecture"
    RESEARCH = "research"
    PRODUCT = "product"
    HARDWARE = "hardware"
    DATA_TELEMETRY = "data_telemetry"
    REVIEW = "review"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"


class Complexity(Enum):
    """Task complexity determines workflow path."""

    LOW = "low"          # Skip planning, direct execution
    MEDIUM = "medium"    # Light planning, optional gate
    HIGH = "high"        # Full planning, human gate required
    CRITICAL = "critical"  # Full planning, multi-stakeholder gate


class Domain(Enum):
    """Target domain for execution."""

    FIRMWARE = "firmware"
    MOBILE = "mobile"
    BACKEND = "backend"
    HARDWARE = "hardware"
    DOCS = "docs"


# --- State Schema ---


class TaskInput(TypedDict, total=False):
    """Input provided by the human/CLI when submitting a task."""

    task_id: str
    description: str
    domain: str
    target_files: list[str]
    priority: str             # low | normal | high | critical
    requested_agent: str      # Force specific agent (optional)


class Classification(TypedDict, total=False):
    """Result of the classification/routing step."""

    task_type: str            # TaskType value
    complexity: str           # Complexity value
    domain: str               # Domain value
    target_agent: str         # Which agent should handle this
    requires_planning: bool
    requires_human_gate: bool
    reasoning: str            # Why this classification


class RoutingDecision(TypedDict, total=False):
    """Model selection from 9Router."""

    model_id: str
    max_tokens: int
    temperature: float
    estimated_cost_usd: float


class ContextBundle(TypedDict, total=False):
    """Composed context from the Context Agent."""

    tier1_content: str        # Principles (always)
    tier1_tokens: int
    tier2_content: str        # Domain spec + ADR
    tier2_tokens: int
    tier3_content: str        # Target files
    tier3_tokens: int
    tier4_content: str        # Codebase memory patterns
    tier4_tokens: int
    total_tokens: int
    sources: list[str]        # Documents loaded


class PlanArtifacts(TypedDict, total=False):
    """Artifacts produced by the planning step."""

    proposal: str             # Generated proposal.md content
    design: str               # Generated design.md content
    tasks: str                # Generated tasks.md content
    task_breakdown: list[dict]  # Parsed structured tasks
    artifacts_dir: str        # Where artifacts were written
    estimated_cost_usd: float


class ExecutionResult(TypedDict, total=False):
    """Result from the execution step."""

    modified_files: list[str]
    output: str               # Summary of what was done
    token_usage: dict         # {input, output, model, latency}
    learnings: list[str]      # Patterns discovered


class ReviewResult(TypedDict, total=False):
    """Result from the review step."""

    verdict: str              # approved | changes_requested | blocked
    issues: list[dict]        # {severity, file, line, message, suggestion}
    checklist: dict           # {item: bool} compliance checklist
    confidence: str           # high | medium | low — retry signal
    retry_worthwhile: bool    # Whether retrying is likely to succeed


class ValidationResult(TypedDict, total=False):
    """Result from the validation step."""

    build_passed: bool
    tests_passed: bool
    tests_total: int
    tests_failed: int
    tests_skipped: int
    coverage_pct: float
    build_output: str
    test_output: str
    gaps: list[str]           # Untested paths


class RetryState(TypedDict, total=False):
    """Tracks retry attempts and escalation."""

    attempt: int              # Current attempt (1-based)
    max_attempts: int         # Hard cap (default: 3)
    errors: list[str]         # Error from each attempt
    escalated_model: str      # Model upgraded to (if any)


class HumanDecision(TypedDict, total=False):
    """Human approval/rejection at a gate."""

    approved: bool
    reason: str
    approved_by: str
    approved_at: str          # ISO timestamp


# --- Main Workflow State ---


class FactoryState(TypedDict, total=False):
    """
    Complete workflow state for the AI Software Factory.

    This TypedDict flows through every node in the LangGraph DAG.
    Nodes read what they need and return updates (partial dict).
    LangGraph merges updates into the running state.
    """

    # --- Task Input ---
    task: TaskInput

    # --- Classification ---
    classification: Classification
    routing: RoutingDecision

    # --- Context ---
    context: ContextBundle

    # --- Planning ---
    plan: PlanArtifacts

    # --- Human Gate ---
    human_decision: HumanDecision

    # --- Execution ---
    execution: ExecutionResult

    # --- Review ---
    review: ReviewResult

    # --- Validation ---
    validation: ValidationResult

    # --- Retry ---
    retry: RetryState

    # --- Workflow Meta ---
    status: str               # TaskStatus value
    current_node: str         # Which node is active
    error: str | None         # Latest error message
    history: list[str]        # Ordered list of nodes visited
    suggested_follow_ups: list[dict]  # Auto-generated follow-up task suggestions
    persist_suggestion: dict | None   # Suggestion to save documentation output
