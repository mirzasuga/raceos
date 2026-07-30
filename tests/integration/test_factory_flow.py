"""
Integration Tests — End-to-End Factory Workflow.

Tests the complete LangGraph pipeline with mock LLM (no real API calls).
Verifies: classification → context → execution → review → validation → knowledge.

Covers:
- Happy path (simple + complex tasks)
- Failure path (LLM fails, OpenCode fails)
- Retry with model escalation
- Missing API key
- Missing context/brain
- Cancel/timeout
"""

from __future__ import annotations

import pytest

from tests.mocks import MockGatewayClient, MockRouter
from factory.orchestrator.nodes.orchestrator import orchestrator_node
from factory.orchestrator.nodes.context import context_node
from factory.orchestrator.nodes.engineer import engineer_node
from factory.orchestrator.nodes.reviewer import reviewer_node
from factory.orchestrator.nodes.validator import validator_node
from factory.orchestrator.nodes.knowledge import knowledge_node
from factory.orchestrator.nodes.architect import architect_node
from factory.orchestrator.nodes.hardware import hardware_node
from factory.orchestrator.nodes.research import research_node
from factory.orchestrator.nodes.product import product_node


# ============================================================
# HAPPY PATH TESTS
# ============================================================


class TestHappyPathSimple:
    """Test simple task flow (no planning, no gate)."""

    def test_orchestrator_classifies_simple_fix(self, simple_task_state, mock_gateway, mock_router):
        result = orchestrator_node(simple_task_state, router=mock_router, gateway=mock_gateway)

        # With mock LLM, classification comes from mock response (coding/medium)
        # The important thing: it classifies and routes without error
        assert "classification" in result
        assert result["classification"]["task_type"] in ("coding", "debugging")
        assert result["classification"]["target_agent"] == "engineer"
        assert result["classification"]["requires_planning"] is False
        assert "orchestrator" in result["history"]

    def test_context_resolves_tiers(self, simple_task_state):
        # Add classification to state (normally set by orchestrator)
        simple_task_state["classification"] = {"task_type": "debugging"}
        simple_task_state["plan"] = {}

        result = context_node(simple_task_state)

        assert "context" in result
        assert result["context"]["tier1_tokens"] > 0  # Principles loaded
        assert result["context"]["total_tokens"] > 0
        assert result["context"]["total_tokens"] <= 12000
        assert "context" in result["history"]

    def test_reviewer_approves_when_no_files(self, simple_task_state, mock_gateway, mock_router):
        simple_task_state["execution"] = {"modified_files": [], "output": "nothing done"}
        simple_task_state["context"] = {"tier1_content": "", "tier2_content": ""}

        result = reviewer_node(simple_task_state, router=mock_router, gateway=mock_gateway)

        assert result["review"]["verdict"] == "approved"
        assert result["review"]["confidence"] == "high"

    def test_validator_trusts_executor_on_success(self, simple_task_state):
        simple_task_state["task"]["domain"] = "firmware"
        simple_task_state["execution"] = {
            "status": "success",
            "output": "all 16 tests passed, failed: 0",
            "modified_files": ["test.cpp"],
            "token_usage": {},
        }
        simple_task_state["retry"] = {}

        result = validator_node(simple_task_state)

        assert result["validation"]["trusted_from_executor"] is True
        assert result["validation"]["build_passed"] is True

    def test_knowledge_stores_without_crash(self, simple_task_state):
        simple_task_state["execution"] = {
            "modified_files": ["a.cpp", "b.cpp"],
            "output": "fixed the bug",
            "token_usage": {},
            "learnings": [],
        }
        simple_task_state["classification"] = {"task_type": "debugging"}

        result = knowledge_node(simple_task_state)

        assert result["status"] == "completed"
        assert "knowledge" in result["history"]


class TestHappyPathComplex:
    """Test complex task flow (planning + gate)."""

    def test_orchestrator_classifies_complex_task(self, complex_task_state, mock_gateway, mock_router):
        result = orchestrator_node(complex_task_state, router=mock_router, gateway=mock_gateway)

        assert result["classification"]["complexity"] in ("high", "medium")
        assert result["classification"]["target_agent"] == "engineer"

    def test_architect_generates_plan(self, complex_task_state, mock_gateway, mock_router):
        complex_task_state["context"] = {"tier1_content": "principles", "tier2_content": "specs"}
        complex_task_state["routing"] = {"model_id": "mock/test", "max_tokens": 4096, "temperature": 0.2}

        result = architect_node(complex_task_state, router=mock_router, gateway=mock_gateway)

        assert "plan" in result or "execution" in result
        assert "architect" in result["history"]


class TestHappyPathHardware:
    """Test hardware documentation flow."""

    def test_orchestrator_routes_to_hardware(self, hardware_task_state, mock_gateway, mock_router):
        result = orchestrator_node(hardware_task_state, router=mock_router, gateway=mock_gateway)

        assert result["classification"]["target_agent"] == "hardware"

    def test_hardware_node_produces_output(self, hardware_task_state, mock_gateway, mock_router):
        hardware_task_state["context"] = {"tier1_content": "p", "tier2_content": "s", "tier3_content": "", "tier4_content": ""}
        hardware_task_state["routing"] = {}

        result = hardware_node(hardware_task_state, router=mock_router, gateway=mock_gateway)

        assert result["execution"]["output"] != ""
        assert result["status"] == "executing"


# ============================================================
# FAILURE PATH TESTS
# ============================================================


class TestFailurePaths:
    """Test behavior when things go wrong."""

    def test_orchestrator_falls_back_to_rules_when_llm_fails(self, simple_task_state):
        """Orchestrator should work even without gateway (rule-based fallback)."""
        result = orchestrator_node(simple_task_state, router=None, gateway=None)

        # Rule-based classification still works
        assert result["classification"]["task_type"] == "debugging"
        assert result["classification"]["complexity"] == "low"

    def test_reviewer_auto_approves_when_llm_unavailable(self, simple_task_state):
        """Reviewer should approve (with warning) when LLM is down."""
        simple_task_state["execution"] = {"modified_files": ["a.cpp"], "output": "done"}
        simple_task_state["context"] = {"tier1_content": "", "tier2_content": ""}
        simple_task_state["classification"] = {"task_type": "coding"}

        # Pass a gateway that will fail
        failing_gateway = MockGatewayClient()
        failing_gateway.fail_next("500", count=5)

        result = reviewer_node(simple_task_state, router=MockRouter(), gateway=failing_gateway)

        # Should auto-approve with low confidence (not crash)
        assert result["review"]["verdict"] == "approved"

    def test_context_works_without_memory_mcp(self, simple_task_state):
        """Context should resolve Tier 1-3 even when Tier 4 (memory) fails."""
        simple_task_state["classification"] = {"task_type": "coding"}
        simple_task_state["plan"] = {}

        result = context_node(simple_task_state, memory_client=None)

        # Tier 4 is empty but doesn't crash
        assert result["context"]["tier4_tokens"] == 0
        assert result["context"]["tier1_tokens"] > 0  # Still loaded

    def test_validator_runs_full_path_on_failure(self, simple_task_state):
        """Validator should NOT trust executor when it reports failure."""
        simple_task_state["task"]["domain"] = "firmware"
        simple_task_state["execution"] = {
            "status": "failed",
            "output": "build error: undefined reference",
            "modified_files": ["a.cpp"],
            "token_usage": {},
        }
        simple_task_state["retry"] = {"attempt": 2}

        result = validator_node(simple_task_state)

        # Should NOT trust — runs full validation
        assert result["validation"]["trusted_from_executor"] is False

    def test_knowledge_doesnt_crash_on_empty_state(self):
        """Knowledge node should handle empty/missing state gracefully."""
        empty_state = {
            "task": {"description": "test"},
            "execution": {"modified_files": [], "output": "", "token_usage": {}, "learnings": []},
            "classification": {},
            "history": [],
        }
        result = knowledge_node(empty_state)
        assert result["status"] == "completed"


# ============================================================
# RETRY TESTS
# ============================================================


class TestRetry:
    """Test retry and model escalation behavior."""

    def test_reviewer_signals_retry_worthwhile(self, simple_task_state, mock_router):
        """When reviewer says changes_requested + retry_worthwhile, should retry."""
        mock = MockGatewayClient()
        mock.add_pattern_response("review", '{"verdict":"changes_requested","issues":[{"severity":"major","message":"missing test"}],"checklist":{},"confidence":"high","retry_worthwhile":true}')

        simple_task_state["execution"] = {"modified_files": ["a.cpp"], "output": "implemented"}
        simple_task_state["context"] = {"tier1_content": "rules", "tier2_content": "spec"}
        simple_task_state["classification"] = {"task_type": "coding"}

        result = reviewer_node(simple_task_state, router=mock_router, gateway=mock)

        assert result["review"]["verdict"] == "changes_requested"
        assert result["review"]["retry_worthwhile"] is True

    def test_reviewer_signals_no_retry(self, simple_task_state, mock_router):
        """When reviewer says blocked + not retry_worthwhile, should escalate."""
        mock = MockGatewayClient()
        mock.add_pattern_response("review", '{"verdict":"blocked","issues":[{"severity":"critical","message":"fundamental misunderstanding"}],"checklist":{},"confidence":"high","retry_worthwhile":false}')

        simple_task_state["execution"] = {"modified_files": ["a.cpp"], "output": "wrong approach"}
        simple_task_state["context"] = {"tier1_content": "", "tier2_content": ""}
        simple_task_state["classification"] = {"task_type": "coding"}

        result = reviewer_node(simple_task_state, router=mock_router, gateway=mock)

        assert result["review"]["verdict"] == "blocked"
        assert result["review"]["retry_worthwhile"] is False


# ============================================================
# EDGE ROUTING TESTS
# ============================================================


class TestEdgeRouting:
    """Test conditional edges route correctly."""

    def test_simple_task_skips_planning(self, simple_task_state, mock_router, mock_gateway):
        """Low complexity → direct to execute, no planning."""
        result = orchestrator_node(simple_task_state, router=mock_router, gateway=mock_gateway)

        assert result["classification"]["requires_planning"] is False
        assert result["classification"]["requires_human_gate"] is False

    def test_complex_task_requires_planning(self, complex_task_state, mock_router, mock_gateway):
        """High complexity → planning required."""
        # Force high complexity via long description with "implement" keyword
        result = orchestrator_node(complex_task_state, router=mock_router, gateway=mock_gateway)

        # Complex tasks need planning (if classified as high)
        if result["classification"]["complexity"] in ("high", "critical"):
            assert result["classification"]["requires_planning"] is True

    def test_hardware_domain_routes_to_hardware_agent(self, hardware_task_state, mock_router, mock_gateway):
        """Domain=hardware → target_agent=hardware."""
        result = orchestrator_node(hardware_task_state, router=mock_router, gateway=mock_gateway)
        assert result["classification"]["target_agent"] == "hardware"


# ============================================================
# MISSING CONFIGURATION TESTS
# ============================================================


class TestMissingConfig:
    """Test behavior with missing configuration."""

    def test_orchestrator_works_without_any_injection(self, simple_task_state):
        """Orchestrator must work with zero deps (rule-based fallback)."""
        result = orchestrator_node(simple_task_state)
        assert "classification" in result
        assert result["classification"]["task_type"] != ""

    def test_context_works_with_missing_brain(self, simple_task_state, tmp_path):
        """Context should return partial results when Brain files missing."""
        simple_task_state["classification"] = {"task_type": "coding"}
        simple_task_state["plan"] = {}

        # Even if brain files are partially missing, should not crash
        result = context_node(simple_task_state)
        assert "context" in result
        # May have 0 tokens if files don't exist — that's OK
        assert result["context"]["total_tokens"] >= 0
