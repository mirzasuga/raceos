# Codebase Memory MCP client.
"""
Codebase memory integration for the AI Software Factory.

Provides:
    - Repository indexing (incremental, checksum-based)
    - Semantic search (meaning-based code discovery)
    - Symbol lookup (functions, classes, interfaces)
    - Dependency graph (imports, dependents, layer validation)
    - Context builder (Tier 4 context for prompt injection)

All operations gracefully degrade if the MCP server is unavailable.
Memory stores IMPLEMENTATION patterns only (not project knowledge).

Usage:
    from factory.memory import ContextBuilder, MemoryClient, SemanticSearch

    client = MemoryClient()
    if client.is_available():
        client.connect()
        builder = ContextBuilder(client)
        ctx = builder.build("add error handling", target_files=["parser.cpp"])
        client.disconnect()
"""

from .client import MemoryClient, MemoryClientError, ServerUnavailableError
from .context_builder import ContextBuilder, ContextBuilderConfig
from .dependencies import DependencyLookup, LayerConfig
from .indexer import IndexerConfig, RepositoryIndexer
from .search import SemanticSearch, SearchConfig
from .symbols import SymbolLookup
from .types import (
    Chunk,
    Dependency,
    DependencyNode,
    FileInfo,
    IndexStatus,
    Language,
    MemoryContext,
    SearchResult,
    Symbol,
    SymbolKind,
)

__all__ = [
    # Client
    "MemoryClient",
    "MemoryClientError",
    "ServerUnavailableError",
    # Indexer
    "RepositoryIndexer",
    "IndexerConfig",
    # Search
    "SemanticSearch",
    "SearchConfig",
    # Symbols
    "SymbolLookup",
    # Dependencies
    "DependencyLookup",
    "LayerConfig",
    # Context
    "ContextBuilder",
    "ContextBuilderConfig",
    # Types
    "Language",
    "SymbolKind",
    "FileInfo",
    "Chunk",
    "Symbol",
    "Dependency",
    "DependencyNode",
    "SearchResult",
    "IndexStatus",
    "MemoryContext",
]
