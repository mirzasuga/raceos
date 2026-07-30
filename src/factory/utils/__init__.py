# Shared utilities.
"""
Cross-cutting utilities used by multiple factory modules.

Contains functionality that doesn't belong to a single module
but is needed by several (avoids circular imports).
"""

from factory.utils.persist import PersistSuggestion, save_output, suggest_persist

__all__ = ["suggest_persist", "save_output", "PersistSuggestion"]
