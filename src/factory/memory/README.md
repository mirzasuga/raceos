# Memory

> MCP client for codebase-memory server, storing implementation patterns.

## Responsibility

Provides a client interface to the codebase-memory MCP server. Stores and retrieves implementation patterns — coding conventions, architectural decisions observed in practice, and recurring solutions. Read during planning to inform context assembly. Written by the learning node after successful task completion.

## Does NOT

- Store project knowledge (that lives in .raceos/ Brain documents)
- Store specs or ADRs (that lives in openspec/)
- Make decisions about what to remember (learning node decides)
- Run its own vector database (delegates to MCP server)
- Summarize or transform patterns (stores as-is)

## Key Files (planned)

- `client.py` — MCP protocol client for codebase-memory server
- `patterns.py` — pattern CRUD operations (create, read, search)
- `types.py` — pattern schema, search query, search result dataclasses

## Dependencies

- `mcp` (Model Context Protocol SDK)
- `factory.config` (MCP server connection settings)
