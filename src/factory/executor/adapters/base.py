"""
Base Adapter Interface.

All domain adapters inherit from BaseAdapter and provide
domain-specific build commands, test commands, constraints,
and file patterns. The executor uses adapters to configure
sessions appropriately for each domain.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AdapterConfig:
    """Configuration produced by an adapter for a session."""

    working_dir: str
    build_commands: list[str]
    test_commands: list[str]
    lint_commands: list[str]
    constraints: list[str]
    file_patterns: list[str]
    pre_commands: list[str] = field(default_factory=list)
    post_commands: list[str] = field(default_factory=list)


class BaseAdapter(ABC):
    """Abstract base for domain-specific execution adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Domain name (firmware, mobile, backend)."""
        ...

    @property
    @abstractmethod
    def working_dir(self) -> str:
        """Root working directory for this domain."""
        ...

    @property
    @abstractmethod
    def build_commands(self) -> list[str]:
        """Commands to build/compile the project."""
        ...

    @property
    @abstractmethod
    def test_commands(self) -> list[str]:
        """Commands to run tests."""
        ...

    @property
    @abstractmethod
    def lint_commands(self) -> list[str]:
        """Commands to lint/check code quality."""
        ...

    @property
    @abstractmethod
    def constraints(self) -> list[str]:
        """Domain-specific constraints injected into every session."""
        ...

    @property
    @abstractmethod
    def file_patterns(self) -> list[str]:
        """File extensions/patterns for this domain."""
        ...

    def get_config(self) -> AdapterConfig:
        """Produce the full adapter configuration."""
        return AdapterConfig(
            working_dir=self.working_dir,
            build_commands=self.build_commands,
            test_commands=self.test_commands,
            lint_commands=self.lint_commands,
            constraints=self.constraints,
            file_patterns=self.file_patterns,
        )
