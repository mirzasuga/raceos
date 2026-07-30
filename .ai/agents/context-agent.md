# Context Agent

## Purpose

Resolve, compose, and inject the correct context for any given task. The Context Agent is the single authority on what documents, specs, and patterns are relevant to a task. It ensures every specialist agent receives precisely the information it needs — nothing more, nothing less.

## Responsibilities

- Determine which Brain documents are relevant per task type
- Load and compose tiered context bundles (Tier 1-4)
- Enforce token budgets per tier
- Truncate gracefully when content exceeds budget
- Query Codebase Memory for relevant implementation patterns (Tier 4)
- Provide read-only access to Project Brain
- Reject requests that would modify Brain content
- Prevent path traversal attacks on file access

## Inputs

| Input | Source | Format |
|---|---|---|
| Task type | Orchestrator | `firmware` / `mobile` / `backend` / `spec` / `architecture` |
| Task description | Orchestrator | Natural language string |
| Target files | Orchestrator (optional) | File path list |
| Domain | Orchestrator | String |

## Outputs

| Output | Destination | Format |
|---|---|---|
| Context bundle | Requesting agent | `ContextBundle` (Tier 1-4, token-counted) |
| System prompt section | Execution node | Formatted markdown string |
| Token usage report | Orchestrator | `{tier1: N, tier2: N, tier3: N, tier4: N, total: N}` |

## Rules

1. **Deterministic resolution** — same task type + domain always produces same document list. No LLM for context selection.
2. **Budget enforcement is absolute** — never exceed 12K total tokens. Trim Tier 3 first, Tier 1 last.
3. **Brain is read-only** — reject any write attempt. No exceptions.
4. **Path-safe** — reject any path that escapes the configured root directory.
5. **No fabrication** — if a document doesn't exist, return empty tier. Never synthesize content.
6. **Tier priority** — Tier 1 (principles) always loaded. Tier 2-4 conditional on task type.
7. **Deduplication** — if same content appears in multiple tiers, include it only once (highest tier).

## Allowed Tools

- Brain reader (read-only filesystem access to `.raceos/`)
- Spec reader (read-only access to `openspec/specs/`)
- ADR reader (read-only access to `adr/`)
- Source file reader (read-only, for Tier 3)
- Codebase Memory MCP client (query only, for Tier 4)
- Token counter (tiktoken)

## Forbidden Actions

- Writing to any file or directory
- Modifying Brain content
- Making LLM calls (context resolution is rule-based)
- Querying external APIs or services
- Caching context beyond configured TTL
- Exposing secrets or sensitive data in context bundles
- Loading documents outside configured root paths

## Success Criteria

- [ ] Context resolution completes in < 500ms (no LLM, pure file I/O)
- [ ] Token budget never exceeded (hard cap: 12K)
- [ ] Tier 1 always present in every bundle (principles always injected)
- [ ] Correct domain spec loaded for task domain
- [ ] Path traversal attempts rejected with clear error
- [ ] Write attempts rejected with clear error
- [ ] Empty tier returned (not error) when document doesn't exist
- [ ] Deterministic: same input → same output on repeated calls
