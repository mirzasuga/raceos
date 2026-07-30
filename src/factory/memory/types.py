"""
Codebase Memory Data Types.

Shared type definitions used across the memory module:
indexer, search, symbols, dependencies, and context builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# --- Enums ---


class Language(Enum):
    """Supported programming languages."""

    CPP = "cpp"
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    MARKDOWN = "markdown"
    YAML = "yaml"


class SymbolKind(Enum):
    """Types of code symbols."""

    FUNCTION = "function"
    CLASS = "class"
    STRUCT = "struct"
    INTERFACE = "interface"
    ENUM = "enum"
    CONSTANT = "constant"
    TYPE = "type"
    MODULE = "module"
    VARIABLE = "variable"


class DependencyDirection(Enum):
    """Direction of a dependency relationship."""

    IMPORTS = "imports"         # This file imports that file
    IMPORTED_BY = "imported_by"  # This file is imported by that file


# --- Core Data Types ---


@dataclass
class FileInfo:
    """Metadata about an indexed file."""

    path: str                            # Relative path from repo root
    language: Language
    size_bytes: int = 0
    line_count: int = 0
    last_modified: str = ""              # ISO timestamp
    checksum: str = ""                   # For change detection
    indexed_at: str = ""                 # When we last indexed this file


@dataclass
class Chunk:
    """A indexed chunk of source code."""

    file_path: str
    content: str
    start_line: int
    end_line: int
    language: Language
    tokens: int = 0
    embedding: list[float] = field(default_factory=list)  # Vector embedding


@dataclass
class Symbol:
    """A code symbol (function, class, interface, etc.)."""

    name: str
    kind: SymbolKind
    file_path: str
    line: int
    language: Language
    signature: str = ""                  # Full signature (e.g., "void foo(int x)")
    docstring: str = ""                  # Documentation/comment above symbol
    scope: str = ""                      # Enclosing scope (e.g., class name)
    visibility: str = "public"           # public | private | protected


@dataclass
class Dependency:
    """A dependency relationship between two files."""

    source: str                          # File that imports
    target: str                          # File being imported
    direction: DependencyDirection
    import_statement: str = ""           # Raw import line
    language: Language = Language.CPP


@dataclass
class SearchResult:
    """A single search result with relevance scoring."""

    file_path: str
    content: str                         # Matching content snippet
    start_line: int
    end_line: int
    score: float                         # Relevance score (0.0 - 1.0)
    language: Language = Language.CPP
    symbols: list[str] = field(default_factory=list)  # Symbols in this chunk


@dataclass
class DependencyNode:
    """A node in the dependency graph."""

    file_path: str
    imports: list[str] = field(default_factory=list)      # Files this file imports
    imported_by: list[str] = field(default_factory=list)  # Files that import this
    layer: str = ""                                        # Architecture layer


@dataclass
class IndexStatus:
    """Status of the repository index."""

    total_files: int = 0
    indexed_files: int = 0
    total_chunks: int = 0
    total_symbols: int = 0
    total_dependencies: int = 0
    last_indexed_at: str = ""
    index_duration_seconds: float = 0.0
    languages: dict[str, int] = field(default_factory=dict)  # lang → file count


@dataclass
class MemoryContext:
    """Context produced by the context builder for Tier 4 injection."""

    content: str                         # Formatted text ready for prompt injection
    token_count: int                     # Tokens used
    sources: list[str]                   # Files/symbols referenced
    query: str                           # Query that produced this context
    result_count: int                    # How many results were found
