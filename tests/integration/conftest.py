"""
Integration Test Fixtures.

Shared fixtures for all integration tests:
- Mock gateway (no real API calls)
- Mock router (no config file needed)
- Sample state objects
- Temporary directories
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tests.mocks import MockGatewayClient, MockRouter


# --- Mock Fixtures ---


@pytest.fixture
def mock_gateway() -> MockGatewayClient:
    """Pre-configured mock gateway with canned responses for common tasks."""
    mock = MockGatewayClient()

    # Classification response
    mock.add_pattern_response("classify", json.dumps({
        "task_type": "coding",
        "complexity": "medium",
        "reasoning": "mock classification"
    }))

    # Review response
    mock.add_pattern_response("review", json.dumps({
        "verdict": "approved",
        "issues": [],
        "checklist": {"layered_architecture": True, "no_magic_numbers": True},
        "confidence": "high",
        "retry_worthwhile": True,
        "summary": "Looks good"
    }))

    # Planning response
    mock.add_pattern_response("plan", json.dumps({
        "proposal": "# Proposal\n\nTest proposal content.",
        "tasks": [
            {
                "title": "Implement feature",
                "description": "Write the code",
                "files": ["firmware/middleware/test.cpp"],
                "acceptance_criteria": ["Tests pass"],
                "complexity": "medium"
            }
        ]
    }))

    # Architecture response
    mock.add_pattern_response("architect", json.dumps({
        "proposal": "# Architecture\n\nDesign doc.",
        "design": "# Design\n\nInterfaces.",
        "tasks": [{"title": "Implement", "files": ["test.cpp"], "acceptance_criteria": ["pass"], "complexity": "medium"}],
        "summary": "Architecture designed"
    }))

    # Default (general questions)
    mock.set_default_response("This is a mock LLM response for testing purposes.")

    return mock


@pytest.fixture
def mock_router() -> MockRouter:
    """Mock router that doesn't need config files."""
    return MockRouter()


# --- State Fixtures ---


@pytest.fixture
def simple_task_state() -> dict:
    """State for a simple task (no planning, no gate)."""
    return {
        "task": {
            "task_id": "TEST-001",
            "description": "fix typo in ecu_parser.h",
            "domain": "firmware",
            "target_files": [],
        },
        "status": "pending",
        "history": [],
    }


@pytest.fixture
def complex_task_state() -> dict:
    """State for a complex task (planning + gate)."""
    return {
        "task": {
            "task_id": "TEST-002",
            "description": "implement engine load gauge for race dashboard with threshold coloring",
            "domain": "firmware",
            "target_files": ["firmware/middleware/dashboard_view.cpp"],
        },
        "status": "pending",
        "history": [],
    }


@pytest.fixture
def debug_task_state() -> dict:
    """State for a debugging task."""
    return {
        "task": {
            "task_id": "TEST-003",
            "description": "why engine load indicator always 100% show in display",
            "domain": "firmware",
            "target_files": [],
        },
        "status": "pending",
        "history": [],
    }


@pytest.fixture
def hardware_task_state() -> dict:
    """State for a hardware documentation task."""
    return {
        "task": {
            "task_id": "TEST-004",
            "description": "how to wire display to stm32 with uart from ecu under seat",
            "domain": "hardware",
            "target_files": [],
        },
        "status": "pending",
        "history": [],
    }


# --- Temp Directory Fixtures ---


@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:
    """Temporary data directory for checkpoints/ledger."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir
