"""
Backend Adapter.

Domain adapter for Python backend services (FastAPI, pytest, Pydantic).
"""

from __future__ import annotations

from .base import BaseAdapter


class BackendAdapter(BaseAdapter):
    """Adapter for Python backend development."""

    @property
    def name(self) -> str:
        return "backend"

    @property
    def working_dir(self) -> str:
        return "../backend"

    @property
    def build_commands(self) -> list[str]:
        return [
            "uv run python -m compileall src/ -q",  # Syntax check
        ]

    @property
    def test_commands(self) -> list[str]:
        return [
            "uv run pytest tests/ --tb=short -q",
        ]

    @property
    def lint_commands(self) -> list[str]:
        return [
            "uv run ruff check src/ tests/",
            "uv run ruff format --check src/ tests/",
        ]

    @property
    def constraints(self) -> list[str]:
        return [
            "Type hints on all public functions and methods.",
            "Use Pydantic for all data validation and serialization.",
            "Async where I/O bound (database, HTTP, file).",
            "All public functions must have corresponding tests.",
            "Use dependency injection for testability.",
            "No secrets in code. Use environment variables via pydantic-settings.",
            "Run 'uv run pytest' and verify all tests pass before declaring done.",
            "Commit on branch factory/<task-name>.",
        ]

    @property
    def file_patterns(self) -> list[str]:
        return ["*.py", "*.toml", "*.yaml"]
