"""
Semantic Search Interface.

Provides semantic (meaning-based) search across the indexed codebase.
Returns ranked results with relevance scores.

Search modes:
    - Semantic: Find code by meaning (e.g., "error handling for ECU")
    - File-scoped: Search within specific files/directories
    - Combined: Semantic + file scope filtering

Usage:
    searcher = SemanticSearch(client, config)
    results = searcher.search("ECU protocol handshake logic")
    results = searcher.search("parser", scope="firmware")
"""

from __future__ import annotations

from dataclasses import dataclass

from .client import MemoryClient, MemoryClientError, ServerUnavailableError
from .types import Language, SearchResult


@dataclass
class SearchConfig:
    """Configuration for semantic search."""

    default_top_k: int = 5
    max_top_k: int = 20
    similarity_threshold: float = 0.65
    boost_recent: bool = True
    boost_factor: float = 1.2


class SemanticSearch:
    """
    Semantic search over indexed codebase.

    Uses vector embeddings to find code by meaning, not just keywords.
    Results are ranked by relevance score (0.0 = irrelevant, 1.0 = exact match).
    """

    def __init__(self, client: MemoryClient, config: SearchConfig | None = None):
        self.client = client
        self.config = config or SearchConfig()

    def search(
        self,
        query: str,
        top_k: int | None = None,
        scope: str | None = None,
        language: Language | None = None,
        threshold: float | None = None,
    ) -> list[SearchResult]:
        """
        Search the codebase by semantic similarity.

        Args:
            query: Natural language query describing what to find.
            top_k: Number of results to return (default from config).
            scope: Restrict to scope name (firmware, mobile, backend, specs).
            language: Filter by programming language.
            threshold: Minimum relevance score override.

        Returns:
            List of SearchResult ordered by relevance (highest first).
            Returns empty list if server is unavailable (graceful degradation).
        """
        top_k = min(top_k or self.config.default_top_k, self.config.max_top_k)
        threshold = threshold or self.config.similarity_threshold

        # Build search parameters
        params: dict = {
            "query": query,
            "top_k": top_k,
            "threshold": threshold,
        }

        if scope:
            params["scope"] = scope
        if language:
            params["language"] = language.value

        # Execute search
        try:
            raw_results = self.client.call_tool("search", params)
        except (ServerUnavailableError, MemoryClientError):
            # Graceful degradation: return empty results
            return []

        # Parse results
        return self._parse_results(raw_results, threshold)

    def search_similar_files(self, file_path: str, top_k: int = 5) -> list[SearchResult]:
        """
        Find files similar to a given file.

        Useful for finding related modules, alternative implementations,
        or files that should be modified together.

        Args:
            file_path: Reference file to find similar files for.
            top_k: Number of results.

        Returns:
            List of similar files with relevance scores.
        """
        try:
            raw_results = self.client.call_tool("search_similar", {
                "file_path": file_path,
                "top_k": top_k,
            })
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_results(raw_results)

    def search_by_pattern(self, pattern: str, scope: str | None = None) -> list[SearchResult]:
        """
        Search for code matching a structural pattern.

        Unlike semantic search (meaning-based), pattern search finds
        code that structurally matches (e.g., "try/catch blocks", "callback registrations").

        Args:
            pattern: Code pattern description.
            scope: Restrict to scope.

        Returns:
            Matching code sections.
        """
        params: dict = {"pattern": pattern}
        if scope:
            params["scope"] = scope

        try:
            raw_results = self.client.call_tool("search_pattern", params)
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_results(raw_results)

    # --- Internal ---

    def _parse_results(
        self, raw: dict, threshold: float = 0.0
    ) -> list[SearchResult]:
        """Parse raw server response into SearchResult list."""
        results: list[SearchResult] = []

        for item in raw.get("results", []):
            score = item.get("score", 0.0)
            if score < threshold:
                continue

            results.append(SearchResult(
                file_path=item.get("file_path", ""),
                content=item.get("content", ""),
                start_line=item.get("start_line", 0),
                end_line=item.get("end_line", 0),
                score=score,
                language=Language(item.get("language", "cpp")),
                symbols=item.get("symbols", []),
            ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results
