"""Shared test fixtures for the factory test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def config_dir() -> Path:
    """Path to the config/ directory."""
    return Path(__file__).parent.parent / "config"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def factory_root() -> Path:
    """Path to the factory repository root."""
    return Path(__file__).parent.parent
