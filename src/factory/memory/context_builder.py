"""
Context Builder.

Composes Tier 4 context (codebase memory patterns) from search results,
symbol lookups, and dependency information. Produces formatted text
ready for injection into the LLM system prompt.

This is the bridge between codebase-memory-mcp and the Context Agent's
Tier 4 loading. The Context Agent calls context_builder to get formatted
memory context within the 1K token budget.

Usage:
    builder = ContextBuilder(client, config)
    memory_context = builder.build(
        task_description="add error handling to ECU parser",
        target_files=["firmware/middleware/ecu_parser.cpp"],
        domain="firmware",
    )
    # memory_context.content → formatted text for Tier 4
    # memory_context.token_count → tokens used
"""

from __future__ import annotations

from dataclasses import dataclass

from .client import MemoryClient, ServerUnavailableError
from .dependencies import DependencyLookup
from .search import SemanticSearch, SearchConfig
from .symbols import SymbolLookup
from .types import MemoryContext, SearchResult, Symbol


@dataclass
class ContextBuilderConfig:
    """Configuration for context building."""

    budget_tokens: int = 1000           # Max tokens for Tier 4
    max_search_results: int = 3         # Max semantic search results
    max_symbols: int = 5                # Max symbols to include
    include_dependencies: bool = True   # Include dependency info
    include_symbols: bool = True        # Include symbol signatures
    format: str = "condensed"           # condensed | verbose


class ContextBuilder:
    """
    Builds Tier 4 context from codebase memory.

    Orchestrates semantic search, symbol lookup, and dependency
    analysis to produce a compact, relevant context section.

    Priority order (when budget is tight):
    1. Semantic search results (most relevant code)
    2. Symbol signatures (for target files)
    3. Dependency info (what's connected)
    """

    def __init__(self, client: MemoryClient, config: ContextBuilderConfig | None = None):
        self.client = client
        self.config = config or ContextBuilderConfig()
        self.search = SemanticSearch(client, SearchConfig(default_top_k=self.config.max_search_results))
        self.symbols = SymbolLookup(client)
        self.deps = DependencyLookup(client)

    def build(
        self,
        task_description: str,
        target_files: list[str] | None = None,
        domain: str | None = None,
    ) -> MemoryContext:
        """
        Build Tier 4 context from codebase memory.

        Queries memory with task description and target files,
        then formats results within the token budget.

        Args:
            task_description: Natural language task description.
            target_files: Files that will be modified (optional).
            domain: Scope search to domain (firmware, mobile, backend).

        Returns:
            MemoryContext with formatted content and metadata.
            Returns empty context if server is unavailable.
        """
        parts: list[str] = []
        sources: list[str] = []
        total_results = 0

        # 1. Semantic search for relevant code
        search_results = self._search_relevant(task_description, domain)
        if search_results:
            formatted = self._format_search_results(search_results)
            parts.append(formatted)
            sources.extend(r.file_path for r in search_results)
            total_results += len(search_results)

        # 2. Symbols in target files
        if target_files and self.config.include_symbols:
            symbols = self._get_target_symbols(target_files)
            if symbols:
                formatted = self._format_symbols(symbols)
                parts.append(formatted)
                sources.extend(s.file_path for s in symbols)
                total_results += len(symbols)

        # 3. Dependencies of target files
        if target_files and self.config.include_dependencies:
            dep_info = self._get_dependency_info(target_files)
            if dep_info:
                parts.append(dep_info)

        # Compose final context
        content = "\n\n".join(parts) if parts else ""

        # Rough token estimation (4 chars ≈ 1 token)
        token_estimate = len(content) // 4

        # Truncate if over budget
        if token_estimate > self.config.budget_tokens:
            char_budget = self.config.budget_tokens * 4
            content = content[:char_budget] + "\n[...truncated for budget...]"
            token_estimate = self.config.budget_tokens

        return MemoryContext(
            content=content,
            token_count=token_estimate,
            sources=list(set(sources)),
            query=task_description,
            result_count=total_results,
        )

    def build_empty(self) -> MemoryContext:
        """Return an empty context (when memory is unavailable)."""
        return MemoryContext(
            content="",
            token_count=0,
            sources=[],
            query="",
            result_count=0,
        )

    # --- Internal: Query ---

    def _search_relevant(self, query: str, domain: str | None) -> list[SearchResult]:
        """Run semantic search with task description."""
        try:
            return self.search.search(
                query=query,
                top_k=self.config.max_search_results,
                scope=domain,
            )
        except Exception:
            return []

    def _get_target_symbols(self, target_files: list[str]) -> list[Symbol]:
        """Get key symbols from target files."""
        symbols: list[Symbol] = []
        for file_path in target_files[:3]:  # Limit to 3 files
            try:
                file_symbols = self.symbols.find_in_file(file_path)
                symbols.extend(file_symbols[:self.config.max_symbols])
            except Exception:
                continue
        return symbols

    def _get_dependency_info(self, target_files: list[str]) -> str:
        """Get compact dependency info for target files."""
        lines: list[str] = []
        for file_path in target_files[:2]:  # Limit to 2 files
            try:
                imports = self.deps.get_imports(file_path)
                if imports:
                    import_list = ", ".join(d.target.split("/")[-1] for d in imports[:5])
                    lines.append(f"- `{file_path.split('/')[-1]}` imports: {import_list}")

                dependents = self.deps.get_dependents(file_path)
                if dependents:
                    dep_list = ", ".join(d.source.split("/")[-1] for d in dependents[:5])
                    lines.append(f"- `{file_path.split('/')[-1]}` used by: {dep_list}")
            except Exception:
                continue

        if lines:
            return "**Dependencies:**\n" + "\n".join(lines)
        return ""

    # --- Internal: Format ---

    def _format_search_results(self, results: list[SearchResult]) -> str:
        """Format search results for context injection."""
        lines: list[str] = ["**Related Code:**"]
        for r in results:
            filename = r.file_path.split("/")[-1]
            # Truncate content to ~3 lines
            snippet = r.content.strip().split("\n")[:3]
            snippet_str = "\n".join(f"  {line}" for line in snippet)
            lines.append(f"- `{filename}` (L{r.start_line}-{r.end_line}):\n{snippet_str}")
        return "\n".join(lines)

    def _format_symbols(self, symbols: list[Symbol]) -> str:
        """Format symbols for context injection."""
        lines: list[str] = ["**Key Symbols:**"]
        for s in symbols:
            if s.signature:
                lines.append(f"- `{s.signature}` ({s.file_path.split('/')[-1]}:{s.line})")
            else:
                lines.append(f"- `{s.name}` [{s.kind.value}] ({s.file_path.split('/')[-1]}:{s.line})")
        return "\n".join(lines)
