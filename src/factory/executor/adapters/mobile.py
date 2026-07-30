"""
Mobile Adapter.

Domain adapter for React Native mobile application (TypeScript, Jest).
"""

from __future__ import annotations

from .base import BaseAdapter


class MobileAdapter(BaseAdapter):
    """Adapter for React Native mobile development."""

    @property
    def name(self) -> str:
        return "mobile"

    @property
    def working_dir(self) -> str:
        return "../mobile"

    @property
    def build_commands(self) -> list[str]:
        return [
            "npx tsc --noEmit",                 # Type check (no output)
        ]

    @property
    def test_commands(self) -> list[str]:
        return [
            "npx jest --passWithNoTests --ci",  # Jest with CI mode
        ]

    @property
    def lint_commands(self) -> list[str]:
        return [
            "npx eslint src/ --ext .ts,.tsx",
        ]

    @property
    def constraints(self) -> list[str]:
        return [
            "Use TypeScript strict mode. No 'any' types.",
            "Follow React Native best practices (functional components, hooks).",
            "Accessibility compliant: all interactive elements must have a11y labels.",
            "No inline styles. Use StyleSheet.create().",
            "State management via React context or Zustand (no Redux).",
            "All screens must handle loading, error, and empty states.",
            "Run 'npx tsc --noEmit' to verify types before declaring done.",
            "Commit on branch factory/<task-name>.",
        ]

    @property
    def file_patterns(self) -> list[str]:
        return ["*.tsx", "*.ts", "*.json"]
