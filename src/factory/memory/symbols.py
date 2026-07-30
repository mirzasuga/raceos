"""
Symbol Lookup.

Provides fast lookup of code symbols (functions, classes, interfaces,
structs, enums) across the indexed codebase.

Supports:
    - Exact name lookup: find_symbol("parseEcuFrame")
    - Prefix search: find_by_prefix("parse")
    - Kind filtering: find_symbols(kind=SymbolKind.INTERFACE)
    - Scope search: find_in_file("firmware/middleware/ecu_parser.h")
    - RaceOS convention: find_interfaces() → all I* prefixed classes

Usage:
    symbols = SymbolLookup(client)
    result = symbols.find_symbol("JukenProtocol")
    interfaces = symbols.find_interfaces()
    funcs = symbols.find_in_file("firmware/middleware/ecu_parser.h")
"""

from __future__ import annotations

from .client import MemoryClient, MemoryClientError, ServerUnavailableError
from .types import Language, Symbol, SymbolKind


class SymbolLookup:
    """
    Fast symbol lookup across the indexed codebase.

    Symbols are extracted during indexing and stored with their
    location (file, line), signature, and documentation.
    """

    def __init__(self, client: MemoryClient):
        self.client = client

    def find_symbol(self, name: str) -> list[Symbol]:
        """
        Find a symbol by exact name.

        Returns all occurrences (a name may exist in multiple files
        as forward declarations, definitions, or overloads).

        Args:
            name: Exact symbol name (case-sensitive).

        Returns:
            List of Symbol objects with file paths and line numbers.
        """
        try:
            raw = self.client.call_tool("find_symbol", {"name": name})
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_symbols(raw)

    def find_by_prefix(self, prefix: str, limit: int = 20) -> list[Symbol]:
        """
        Find symbols starting with a prefix.

        Useful for discovering related symbols (e.g., "ecu" finds
        ecuParser, ecuFrame, ecuProtocol).

        Args:
            prefix: Symbol name prefix.
            limit: Maximum results.

        Returns:
            Matching symbols sorted by name.
        """
        try:
            raw = self.client.call_tool("find_symbols_prefix", {
                "prefix": prefix,
                "limit": limit,
            })
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_symbols(raw)

    def find_by_kind(
        self,
        kind: SymbolKind,
        scope: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """
        Find all symbols of a specific kind.

        Args:
            kind: Symbol kind (FUNCTION, CLASS, INTERFACE, etc.).
            scope: Restrict to file path prefix (e.g., "firmware/middleware/").
            limit: Maximum results.

        Returns:
            Symbols of the specified kind.
        """
        params: dict = {"kind": kind.value, "limit": limit}
        if scope:
            params["scope"] = scope

        try:
            raw = self.client.call_tool("find_symbols_by_kind", params)
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_symbols(raw)

    def find_in_file(self, file_path: str) -> list[Symbol]:
        """
        List all symbols defined in a specific file.

        Args:
            file_path: Relative file path.

        Returns:
            All symbols in the file, ordered by line number.
        """
        try:
            raw = self.client.call_tool("symbols_in_file", {"file_path": file_path})
        except (ServerUnavailableError, MemoryClientError):
            return []

        symbols = self._parse_symbols(raw)
        symbols.sort(key=lambda s: s.line)
        return symbols

    def find_interfaces(self, scope: str | None = None) -> list[Symbol]:
        """
        Find all interfaces (RaceOS convention: classes prefixed with 'I').

        RaceOS uses `IFoo` naming for HAL interfaces:
        IClock, ISerialPort, IGpio, IDisplayPanel, etc.

        Args:
            scope: Restrict to path prefix.

        Returns:
            All interface symbols.
        """
        # First try the dedicated interface kind
        interfaces = self.find_by_kind(SymbolKind.INTERFACE, scope=scope)

        # If server doesn't support INTERFACE kind, fall back to prefix
        if not interfaces:
            all_classes = self.find_by_kind(SymbolKind.CLASS, scope=scope, limit=200)
            interfaces = [s for s in all_classes if s.name.startswith("I") and s.name[1:2].isupper()]

        return interfaces

    def find_implementations(self, interface_name: str) -> list[Symbol]:
        """
        Find classes that implement a given interface.

        For RaceOS, this finds concrete implementations of HAL interfaces
        (e.g., "IClock" → "ArduinoClock", "FakeClock").

        Args:
            interface_name: Interface name (e.g., "ISerialPort").

        Returns:
            Classes that implement/inherit from the interface.
        """
        try:
            raw = self.client.call_tool("find_implementations", {
                "interface": interface_name,
            })
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_symbols(raw)

    # --- Internal ---

    def _parse_symbols(self, raw: dict) -> list[Symbol]:
        """Parse raw server response into Symbol list."""
        symbols: list[Symbol] = []

        for item in raw.get("symbols", []):
            kind_str = item.get("kind", "function")
            try:
                kind = SymbolKind(kind_str)
            except ValueError:
                kind = SymbolKind.FUNCTION

            lang_str = item.get("language", "cpp")
            try:
                language = Language(lang_str)
            except ValueError:
                language = Language.CPP

            symbols.append(Symbol(
                name=item.get("name", ""),
                kind=kind,
                file_path=item.get("file_path", ""),
                line=item.get("line", 0),
                language=language,
                signature=item.get("signature", ""),
                docstring=item.get("docstring", ""),
                scope=item.get("scope", ""),
                visibility=item.get("visibility", "public"),
            ))

        return symbols
