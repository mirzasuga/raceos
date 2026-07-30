"""
Codebase Memory MCP Client.

Low-level client that communicates with the codebase-memory-mcp server
via stdio transport. Provides tool-level access to memory operations.

All higher-level modules (indexer, search, symbols, dependencies)
use this client to interact with the server.

Connection lifecycle:
    client = MemoryClient(config)
    client.connect()    # Start server subprocess
    result = client.call_tool("search", {...})
    client.disconnect() # Kill server subprocess
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ServerConfig:
    """Configuration for the MCP server connection."""

    transport: str = "stdio"
    command: str = "npx"
    args: list[str] = field(default_factory=lambda: ["-y", "@deusdata/codebase-memory-mcp"])
    startup_timeout_seconds: int = 30
    request_timeout_seconds: int = 10
    max_retries: int = 2
    working_dir: str = ".."


class MemoryClientError(Exception):
    """Raised when the memory client encounters an error."""

    pass


class ServerUnavailableError(MemoryClientError):
    """Raised when the MCP server is not available."""

    pass


# Allowed env vars for MCP subprocess (security: least privilege)
_ALLOWED_ENV_VARS = {"PATH", "HOME", "USER", "SHELL", "LANG", "NODE_PATH", "NPM_CONFIG_PREFIX"}


def _build_filtered_env() -> dict[str, str]:
    """Build filtered env dict — no secrets passed to MCP server."""
    import os
    return {k: v for k, v in os.environ.items() if k in _ALLOWED_ENV_VARS}


class MemoryClient:
    """
    Low-level MCP client for codebase-memory server.

    Manages server subprocess lifecycle and provides
    tool invocation interface.

    Usage:
        client = MemoryClient()
        if client.is_available():
            results = client.call_tool("search", {"query": "ecu parser"})
        client.disconnect()
    """

    def __init__(self, config: ServerConfig | None = None):
        self.config = config or ServerConfig()
        self._process: subprocess.Popen | None = None
        self._connected: bool = False
        self._available: bool | None = None

    # --- Connection Lifecycle ---

    def is_available(self) -> bool:
        """
        Check if the MCP server binary is available.

        Caches result for the session. Returns False if:
        - npx is not installed
        - The MCP package can't be resolved
        - Server fails to start
        """
        if self._available is not None:
            return self._available

        # Check if npx exists AND the package is resolvable
        try:
            result = subprocess.run(
                [self.config.command] + self.config.args + ["--version"],
                capture_output=True,
                timeout=15,
            )
            self._available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            self._available = False

        return self._available

    def connect(self) -> None:
        """
        Start the MCP server subprocess.

        Raises:
            ServerUnavailableError: If server cannot be started.
        """
        if self._connected:
            return

        if not self.is_available():
            raise ServerUnavailableError(
                f"MCP server not available. Command: {self.config.command} "
                f"Args: {self.config.args}. Ensure npx and the package are installed."
            )

        try:
            cmd = [self.config.command] + self.config.args
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.config.working_dir,
                env=_build_filtered_env(),
            )
            # Wait briefly for server to initialize
            time.sleep(1.0)

            if self._process.poll() is not None:
                stderr = self._process.stderr.read() if self._process.stderr else ""
                raise ServerUnavailableError(
                    f"Server exited immediately. stderr: {stderr[:500]}"
                )

            self._connected = True

        except FileNotFoundError as e:
            raise ServerUnavailableError(f"Command not found: {e}") from e

    def disconnect(self) -> None:
        """Stop the MCP server subprocess."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._connected = False

    # --- Tool Invocation ---

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call a tool on the MCP server.

        This is the core method that all higher-level operations use.
        In a full MCP implementation, this would use the JSON-RPC protocol.

        Args:
            tool_name: Name of the MCP tool to invoke.
            arguments: Tool parameters.

        Returns:
            Tool result as a dictionary.

        Raises:
            MemoryClientError: If the tool call fails.
            ServerUnavailableError: If server is not connected.
        """
        if not self._connected:
            raise ServerUnavailableError("Not connected. Call connect() first.")

        # MCP JSON-RPC protocol implementation.
        # Sends tool call request over stdio to the running server process.
        # The server responds with a JSON-RPC result on stdout.

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": int(time.time() * 1000),
        }

        return self._send_request(request)

    def list_tools(self) -> list[dict[str, Any]]:
        """
        List available tools on the server.

        Returns:
            List of tool definitions with name, description, schema.
        """
        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": int(time.time() * 1000),
        }
        result = self._send_request(request)
        return result.get("tools", [])

    # --- Internal ---

    def _send_request(self, request: dict) -> dict[str, Any]:
        """
        Send a JSON-RPC request to the server via stdio.

        Handles serialization, timeouts, and error parsing.
        """
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise ServerUnavailableError("Server process not available.")

        try:
            # Write request
            request_str = json.dumps(request) + "\n"
            self._process.stdin.write(request_str)
            self._process.stdin.flush()

            # Read response (with timeout)
            # NOTE: In production, use asyncio or select() for proper timeout
            response_str = self._process.stdout.readline()
            if not response_str:
                raise MemoryClientError("Empty response from server")

            response = json.loads(response_str)

            # Check for JSON-RPC error
            if "error" in response:
                error = response["error"]
                raise MemoryClientError(
                    f"Server error [{error.get('code')}]: {error.get('message')}"
                )

            return response.get("result", {})

        except json.JSONDecodeError as e:
            raise MemoryClientError(f"Invalid JSON response: {e}") from e
        except (BrokenPipeError, OSError) as e:
            self._connected = False
            raise ServerUnavailableError(f"Server connection lost: {e}") from e

    # --- Context Manager ---

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
