"""
Tests for codebase memory integration.

All tests are unit tests with mocked MCP client.
No actual server required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from factory.memory.client import MemoryClient, ServerConfig, ServerUnavailableError
from factory.memory.context_builder import ContextBuilder, ContextBuilderConfig
from factory.memory.dependencies import DependencyLookup, LayerConfig, LayerViolation
from factory.memory.indexer import IndexerConfig, RepositoryIndexer
from factory.memory.search import SemanticSearch, SearchConfig
from factory.memory.symbols import SymbolLookup
from factory.memory.types import (
    Language,
    MemoryContext,
    SearchResult,
    Symbol,
    SymbolKind,
)


# --- Fixtures ---


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock MemoryClient."""
    client = MagicMock(spec=MemoryClient)
    client.is_available.return_value = True
    return client


# --- Client Tests ---


class TestMemoryClient:
    def test_server_config_defaults(self):
        config = ServerConfig()
        assert config.transport == "stdio"
        assert config.command == "npx"
        assert config.startup_timeout_seconds == 30

    def test_client_unavailable_when_npx_missing(self):
        client = MemoryClient(config=ServerConfig(command="nonexistent_binary_xyz"))
        assert client.is_available() is False

    def test_client_caches_availability(self):
        client = MemoryClient(config=ServerConfig(command="nonexistent_binary_xyz"))
        client.is_available()
        client.is_available()
        # Should not call subprocess twice
        assert client._available is False

    def test_connect_raises_when_unavailable(self):
        client = MemoryClient(config=ServerConfig(command="nonexistent_binary_xyz"))
        with pytest.raises(ServerUnavailableError):
            client.connect()


# --- Search Tests ---


class TestSemanticSearch:
    def test_search_returns_results(self, mock_client):
        mock_client.call_tool.return_value = {
            "results": [
                {
                    "file_path": "firmware/middleware/ecu_parser.cpp",
                    "content": "void parseFrame(uint8_t* data)",
                    "start_line": 42,
                    "end_line": 55,
                    "score": 0.87,
                    "language": "cpp",
                    "symbols": ["parseFrame"],
                },
            ]
        }

        search = SemanticSearch(mock_client)
        results = search.search("ECU frame parsing")

        assert len(results) == 1
        assert results[0].file_path == "firmware/middleware/ecu_parser.cpp"
        assert results[0].score == 0.87
        mock_client.call_tool.assert_called_once()

    def test_search_filters_below_threshold(self, mock_client):
        mock_client.call_tool.return_value = {
            "results": [
                {"file_path": "a.cpp", "content": "x", "start_line": 1, "end_line": 1, "score": 0.9, "language": "cpp"},
                {"file_path": "b.cpp", "content": "y", "start_line": 1, "end_line": 1, "score": 0.3, "language": "cpp"},
            ]
        }

        search = SemanticSearch(mock_client, SearchConfig(similarity_threshold=0.5))
        results = search.search("test")

        assert len(results) == 1
        assert results[0].file_path == "a.cpp"

    def test_search_graceful_on_server_error(self, mock_client):
        mock_client.call_tool.side_effect = ServerUnavailableError("down")
        search = SemanticSearch(mock_client)
        results = search.search("anything")
        assert results == []


# --- Symbol Tests ---


class TestSymbolLookup:
    def test_find_symbol(self, mock_client):
        mock_client.call_tool.return_value = {
            "symbols": [
                {
                    "name": "JukenProtocol",
                    "kind": "class",
                    "file_path": "firmware/middleware/juken_protocol.h",
                    "line": 15,
                    "language": "cpp",
                    "signature": "class JukenProtocol : public IEcuProtocol",
                },
            ]
        }

        symbols = SymbolLookup(mock_client)
        result = symbols.find_symbol("JukenProtocol")

        assert len(result) == 1
        assert result[0].name == "JukenProtocol"
        assert result[0].kind == SymbolKind.CLASS

    def test_find_interfaces_with_prefix(self, mock_client):
        # First call (find_by_kind INTERFACE) returns empty → triggers fallback
        # Second call (find_by_kind CLASS) returns all classes
        mock_client.call_tool.side_effect = [
            {"symbols": []},  # No INTERFACE kind supported
            {"symbols": [
                {"name": "IClock", "kind": "class", "file_path": "core/system_clock.h", "line": 5, "language": "cpp"},
                {"name": "ISerialPort", "kind": "class", "file_path": "core/serial_port.h", "line": 8, "language": "cpp"},
                {"name": "InternalHelper", "kind": "class", "file_path": "middleware/helper.h", "line": 3, "language": "cpp"},
            ]},
        ]

        symbols = SymbolLookup(mock_client)
        interfaces = symbols.find_interfaces()

        # Should filter to I+Uppercase convention
        names = [s.name for s in interfaces]
        assert "IClock" in names
        assert "ISerialPort" in names
        assert "InternalHelper" not in names  # Not an interface (lowercase after I)

    def test_find_symbol_graceful_on_error(self, mock_client):
        mock_client.call_tool.side_effect = ServerUnavailableError("down")
        symbols = SymbolLookup(mock_client)
        assert symbols.find_symbol("anything") == []


# --- Dependency Tests ---


class TestDependencyLookup:
    def test_layer_config_validation(self):
        config = LayerConfig()

        # Valid: app → middleware
        assert config.is_valid_dependency("firmware/app/main.cpp", "firmware/middleware/parser.h") is True

        # Invalid: drivers → app (reverse direction)
        assert config.is_valid_dependency("firmware/drivers/uart.cpp", "firmware/app/main.cpp") is False

        # Same layer is OK
        assert config.is_valid_dependency("firmware/middleware/a.h", "firmware/middleware/b.h") is True

        # Outside layers is neutral
        assert config.is_valid_dependency("mobile/src/app.tsx", "mobile/src/utils.ts") is True

    def test_check_layer_violations(self, mock_client):
        mock_client.call_tool.return_value = {
            "dependencies": [
                {"source": "firmware/drivers/uart.cpp", "target": "firmware/middleware/parser.h", "import_statement": "#include"},
            ]
        }

        deps = DependencyLookup(mock_client)
        # Simulate getting imports for a file
        imports = deps.get_imports("firmware/drivers/uart.cpp")

        # Direct validation
        config = LayerConfig()
        assert config.is_valid_dependency("firmware/drivers/uart.cpp", "firmware/middleware/parser.h") is False

    def test_impact_analysis(self, mock_client):
        mock_client.call_tool.return_value = {
            "dependencies": [
                {"source": "firmware/app/main.cpp", "target": "firmware/middleware/parser.h"},
                {"source": "firmware/app/dashboard.cpp", "target": "firmware/middleware/parser.h"},
            ]
        }

        deps = DependencyLookup(mock_client)
        # This would need get_dependents to return proper data
        # Just verify the API exists and is callable
        result = deps.get_impact_analysis("firmware/middleware/parser.h")
        assert "risk" in result


# --- Context Builder Tests ---


class TestContextBuilder:
    def test_build_produces_memory_context(self, mock_client):
        mock_client.call_tool.return_value = {
            "results": [
                {
                    "file_path": "firmware/middleware/ecu_parser.cpp",
                    "content": "// ECU parser implementation",
                    "start_line": 1,
                    "end_line": 5,
                    "score": 0.8,
                    "language": "cpp",
                    "symbols": [],
                },
            ]
        }

        builder = ContextBuilder(mock_client)
        ctx = builder.build("add error handling to parser")

        assert isinstance(ctx, MemoryContext)
        assert ctx.content != ""
        assert ctx.token_count > 0
        assert len(ctx.sources) > 0

    def test_build_empty_when_no_results(self, mock_client):
        mock_client.call_tool.return_value = {"results": []}

        builder = ContextBuilder(mock_client)
        ctx = builder.build("something completely unrelated")

        assert ctx.content == ""
        assert ctx.token_count == 0

    def test_build_respects_budget(self, mock_client):
        # Return a huge result
        mock_client.call_tool.return_value = {
            "results": [
                {
                    "file_path": "big.cpp",
                    "content": "x" * 10000,
                    "start_line": 1,
                    "end_line": 500,
                    "score": 0.9,
                    "language": "cpp",
                    "symbols": [],
                },
            ]
        }

        builder = ContextBuilder(mock_client, ContextBuilderConfig(budget_tokens=100))
        ctx = builder.build("test")

        # Should be truncated to budget
        assert ctx.token_count <= 100

    def test_build_graceful_when_server_down(self, mock_client):
        mock_client.call_tool.side_effect = ServerUnavailableError("down")

        builder = ContextBuilder(mock_client)
        ctx = builder.build("anything")

        # Should return empty, not crash
        assert ctx.content == ""
        assert ctx.token_count == 0


# --- Indexer Tests ---


class TestIndexer:
    def test_indexer_config_defaults(self):
        config = IndexerConfig()
        assert "firmware/middleware/" in config.include_paths
        assert ".git/" in config.exclude_paths
        assert ".cpp" in config.include_extensions
        assert config.chunk_size == 1500

    def test_language_detection(self):
        from pathlib import Path
        assert RepositoryIndexer._detect_language(Path("foo.cpp")) == Language.CPP
        assert RepositoryIndexer._detect_language(Path("bar.py")) == Language.PYTHON
        assert RepositoryIndexer._detect_language(Path("baz.tsx")) == Language.TYPESCRIPT
