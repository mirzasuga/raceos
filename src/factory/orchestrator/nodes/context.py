"""
Context Node — Tiered Context Resolution.

Resolves and composes the context bundle injected into all downstream nodes.
NO LLM calls — purely deterministic file I/O + codebase memory query.

Tiers:
    Tier 1 (always): steering.md + engineering-principles.md (~2K tokens)
    Tier 2 (domain): relevant spec + ADR (~3K tokens)
    Tier 3 (files):  target source files (~5K tokens)
    Tier 4 (memory): codebase-memory patterns (~1K tokens)

Total budget: ≤ 12K tokens. Truncation priority: T3 > T4 > T2 > T1 (never trim T1).

READS from state:
    - task.description
    - task.domain
    - task.target_files
    - classification.task_type
    - plan.refined_target_files (if available, from planner)

WRITES to state:
    - context: { tier1_content, tier1_tokens, tier2_content, tier2_tokens, ... total_tokens, sources }
    - status: updated
    - current_node: "context"
    - history: append "context"

DEPENDENCIES (injected):
    - brain_reader: BrainReader (read-only .raceos/ access)
    - memory_client: MemoryClient (codebase-memory MCP)
    - cache: ContextCache (TTL-based tier caching)
"""

from __future__ import annotations

from pathlib import Path

import structlog

from factory.cli.sanitize import sanitize_output
from factory.context.cache import ContextCache
from factory.orchestrator.state import FactoryState

log = structlog.get_logger()

# --- Configuration ---

TOTAL_BUDGET = 12000
TIER1_BUDGET = 2000
TIER2_BUDGET = 3000
TIER3_BUDGET = 5000
TIER4_BUDGET = 1000

# Tier 1 always-load documents (relative to brain root)
TIER1_DOCS = [
    "03-engineering/engineering-principles.md",
]

# Tier 2 domain → spec paths (relative to specs root)
TIER2_MAP = {
    "firmware": ["firmware-core/spec.md", "ecu-protocol/spec.md"],
    "mobile": ["mobile-app/spec.md"],
    "backend": ["backend-api/spec.md"],
    "hardware": ["firmware-core/spec.md"],  # Hardware still needs firmware constraints
}

# Global cache instance (shared across invocations within same process)
_cache = ContextCache(ttl_seconds=300)


def context_node(
    state: FactoryState,
    brain_reader=None,
    memory_client=None,
    cache: ContextCache | None = None,
) -> dict:
    """
    Resolve tiered context bundle for the current task.

    No LLM calls. Pure file I/O + memory query + token counting.
    Uses cache for Tier 1+2 (stable across tasks in same domain).

    Args:
        state: Current workflow state.
        brain_reader: BrainReader instance (injected for testing).
        memory_client: MemoryClient instance (injected for testing).
        cache: ContextCache instance (injected for testing).

    Returns:
        Partial state update with context bundle.
    """
    task = state.get("task", {})
    classification = state.get("classification", {})
    plan = state.get("plan", {})

    domain = task.get("domain", "firmware")
    description = task.get("description", "")
    target_files = plan.get("refined_target_files") or task.get("target_files", [])
    task_type = classification.get("task_type", "coding")

    if cache is None:
        cache = _cache

    log.info("context.resolving", domain=domain, target_files=len(target_files))

    # --- Tier 1: Principles (always, cached) ---
    tier1_content, tier1_tokens, tier1_sources = _load_tier1(brain_reader, cache, domain)

    # --- Tier 2: Domain specs (cached per domain) ---
    tier2_content, tier2_tokens, tier2_sources = _load_tier2(domain, cache)

    # --- Tier 3: Target files ---
    tier3_content, tier3_tokens, tier3_sources = _load_tier3(target_files)

    # --- Tier 4: Codebase memory ---
    tier4_content, tier4_tokens, tier4_sources = _load_tier4(description, target_files, domain, memory_client)

    # --- Compose bundle ---
    total_tokens = tier1_tokens + tier2_tokens + tier3_tokens + tier4_tokens
    all_sources = tier1_sources + tier2_sources + tier3_sources + tier4_sources

    log.info(
        "context.resolved",
        tier1=tier1_tokens,
        tier2=tier2_tokens,
        tier3=tier3_tokens,
        tier4=tier4_tokens,
        total=total_tokens,
        sources=len(all_sources),
    )

    return {
        "context": {
            "tier1_content": tier1_content,
            "tier1_tokens": tier1_tokens,
            "tier2_content": tier2_content,
            "tier2_tokens": tier2_tokens,
            "tier3_content": tier3_content,
            "tier3_tokens": tier3_tokens,
            "tier4_content": tier4_content,
            "tier4_tokens": tier4_tokens,
            "total_tokens": total_tokens,
            "sources": all_sources,
        },
        "status": "context_resolved",
        "current_node": "context",
        "history": state.get("history", []) + ["context"],
    }


# --- Tier Loading ---


def _load_tier1(brain_reader, cache: ContextCache, domain: str) -> tuple[str, int, list[str]]:
    """Load Tier 1: always-on principles. Cached."""
    cached = cache.get("tier1", "global")
    if cached:
        return cached.content, cached.token_count, cached.sources

    parts: list[str] = []
    sources: list[str] = []

    # Try reading steering.md from .ai/ (sibling to brain)
    steering_path = Path("../.ai/steering.md")
    if steering_path.exists():
        content = steering_path.read_text(encoding="utf-8", errors="ignore")
        parts.append(content)
        sources.append(".ai/steering.md")

    # Brain documents
    if brain_reader:
        for doc_path in TIER1_DOCS:
            try:
                content = brain_reader.read(doc_path)
                parts.append(content)
                sources.append(doc_path)
            except (FileNotFoundError, PermissionError):
                continue
    else:
        # Fallback: read directly
        brain_root = Path("../.raceos")
        for doc_path in TIER1_DOCS:
            full = brain_root / doc_path
            if full.exists():
                content = full.read_text(encoding="utf-8", errors="ignore")
                parts.append(content)
                sources.append(doc_path)

    full_content = "\n\n---\n\n".join(parts)
    tokens = _estimate_tokens(full_content)

    # Truncate if over budget
    if tokens > TIER1_BUDGET:
        full_content = _truncate(full_content, TIER1_BUDGET)
        tokens = TIER1_BUDGET

    # Cache
    cache.set("tier1", "global", content=full_content, token_count=tokens, sources=sources)

    return full_content, tokens, sources


def _load_tier2(domain: str, cache: ContextCache) -> tuple[str, int, list[str]]:
    """Load Tier 2: domain-specific specs. Cached per domain."""
    cached = cache.get("tier2", domain)
    if cached:
        return cached.content, cached.token_count, cached.sources

    parts: list[str] = []
    sources: list[str] = []

    specs_root = Path("../openspec/specs")
    spec_paths = TIER2_MAP.get(domain, TIER2_MAP.get("firmware", []))

    for spec_path in spec_paths:
        full = specs_root / spec_path
        if full.exists():
            content = full.read_text(encoding="utf-8", errors="ignore")
            parts.append(content)
            sources.append(f"openspec/specs/{spec_path}")

    full_content = "\n\n---\n\n".join(parts)
    tokens = _estimate_tokens(full_content)

    if tokens > TIER2_BUDGET:
        full_content = _truncate(full_content, TIER2_BUDGET)
        tokens = TIER2_BUDGET

    cache.set("tier2", domain, content=full_content, token_count=tokens, sources=sources)

    return full_content, tokens, sources


def _load_tier3(target_files: list[str]) -> tuple[str, int, list[str]]:
    """Load Tier 3: target source files. Never cached (task-specific)."""
    if not target_files:
        return "", 0, []

    parts: list[str] = []
    sources: list[str] = []
    tokens_used = 0

    repo_root = Path("..")

    for file_path in target_files[:5]:  # Max 5 files
        full = repo_root / file_path
        if not full.exists() or not full.is_file():
            continue

        try:
            content = full.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue

        file_tokens = _estimate_tokens(content)

        # Check budget
        if tokens_used + file_tokens > TIER3_BUDGET:
            remaining = TIER3_BUDGET - tokens_used
            if remaining > 200:
                content = _truncate(content, remaining)
                parts.append(f"### {file_path}\n```\n{content}\n```")
                sources.append(file_path)
            break

        parts.append(f"### {file_path}\n```\n{content}\n```")
        sources.append(file_path)
        tokens_used += file_tokens

    full_content = "\n\n".join(parts)
    tokens = _estimate_tokens(full_content)

    return full_content, tokens, sources


def _load_tier4(
    description: str,
    target_files: list[str],
    domain: str,
    memory_client,
) -> tuple[str, int, list[str]]:
    """Load Tier 4: codebase memory patterns. Never cached (query-specific)."""
    if memory_client is None:
        # Try to load real client
        try:
            from factory.memory.context_builder import ContextBuilder, ContextBuilderConfig
            from factory.memory.client import MemoryClient

            client = MemoryClient()
            if not client.is_available():
                return "", 0, []

            client.connect()
            builder = ContextBuilder(client, ContextBuilderConfig(budget_tokens=TIER4_BUDGET))
            ctx = builder.build(description, target_files, domain)
            client.disconnect()

            return ctx.content, ctx.token_count, ctx.sources

        except Exception as e:
            log.debug("context.tier4_failed", error=str(e))
            return "", 0, []

    # Injected mock/test client
    try:
        from factory.memory.context_builder import ContextBuilder, ContextBuilderConfig
        builder = ContextBuilder(memory_client, ContextBuilderConfig(budget_tokens=TIER4_BUDGET))
        ctx = builder.build(description, target_files, domain)
        return ctx.content, ctx.token_count, ctx.sources
    except Exception:
        return "", 0, []


# --- Utilities ---


def _estimate_tokens(text: str) -> int:
    """Estimate token count (~4 chars per token for English/code)."""
    if not text:
        return 0
    # Try tiktoken if available
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4


def _truncate(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token budget, preserving line boundaries."""
    max_chars = max_tokens * 4  # Rough estimate
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars // 2:
        truncated = truncated[:last_newline]
    return truncated + "\n\n[... truncated to fit context budget ...]"
