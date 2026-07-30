"""
Context Cache.

TTL-based in-memory cache for Tier 1 and Tier 2 context.
Avoids re-reading the same Brain files and specs for every task.

Tier 1 (principles) and Tier 2 (domain specs) change rarely.
Caching them with a 5-minute TTL eliminates redundant file I/O
for sequential tasks in the same domain.

PROMPT CACHING (P2-4):
    OpenRouter/Anthropic support automatic prompt caching when the
    system prompt prefix is stable across calls. Tier 1 is identical
    for all tasks in a domain → it qualifies for prompt caching
    (~50% discount on cached input tokens).

    To enable this, Tier 1 is ALWAYS placed first in the system prompt
    and its content is stable (never randomized, no timestamps).
    The gateway sends it as a separate system message or uses the
    `cache_control` parameter when available.

Cache is:
    - In-memory (lost on restart — that's fine, files are local)
    - TTL-based (default 300s from config/factory.yaml)
    - Key-based (domain + tier level as key)
    - Thread-safe (not needed in v1 single-threaded, but prepared)

What IS cached:
    - Tier 1 content (steering + principles) — domain-independent, CACHEABLE PREFIX
    - Tier 2 content (domain spec + ADR) — per-domain

What is NEVER cached:
    - Tier 3 (target files) — changes between tasks
    - Tier 4 (memory patterns) — query-specific

Usage:
    cache = ContextCache(ttl_seconds=300)
    cached = cache.get("tier1", domain="firmware")
    if cached is None:
        content = load_tier1_from_disk()
        cache.set("tier1", domain="firmware", content=content, tokens=1850)
    else:
        content = cached.content  # Fast path!
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A single cached context tier."""

    content: str
    token_count: int
    sources: list[str]
    cached_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0

    @property
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        return (time.time() - self.cached_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """How old this cache entry is."""
        return time.time() - self.cached_at


class ContextCache:
    """
    TTL-based cache for Tier 1 and Tier 2 context.

    Keys are composed as: "{tier_level}:{domain}"
    Examples:
        "tier1:global"      — principles (same for all domains)
        "tier2:firmware"    — firmware domain spec
        "tier2:mobile"      — mobile domain spec
    """

    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 20):
        """
        Args:
            ttl_seconds: Time-to-live for cache entries (default: 5 minutes).
            max_entries: Maximum entries before LRU eviction.
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0

    def get(self, tier: str, domain: str = "global") -> CacheEntry | None:
        """
        Retrieve a cached context tier.

        Args:
            tier: Tier level ("tier1" or "tier2").
            domain: Domain key ("global", "firmware", "mobile", "backend").

        Returns:
            CacheEntry if found and not expired, None otherwise.
        """
        key = self._make_key(tier, domain)
        entry = self._store.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            # Expired — remove and return miss
            del self._store[key]
            self._misses += 1
            return None

        self._hits += 1
        return entry

    def set(
        self,
        tier: str,
        domain: str = "global",
        content: str = "",
        token_count: int = 0,
        sources: list[str] | None = None,
    ) -> None:
        """
        Store a context tier in cache.

        Args:
            tier: Tier level.
            domain: Domain key.
            content: Context text content.
            token_count: Token count for budget tracking.
            sources: Source file paths.
        """
        # Evict if at capacity
        if len(self._store) >= self.max_entries:
            self._evict_oldest()

        key = self._make_key(tier, domain)
        self._store[key] = CacheEntry(
            content=content,
            token_count=token_count,
            sources=sources or [],
            ttl_seconds=self.ttl_seconds,
        )

    def invalidate(self, tier: str | None = None, domain: str | None = None) -> int:
        """
        Invalidate cache entries.

        Args:
            tier: If provided, only invalidate this tier.
            domain: If provided, only invalidate this domain.
            Both None = clear all.

        Returns:
            Number of entries invalidated.
        """
        if tier is None and domain is None:
            count = len(self._store)
            self._store.clear()
            return count

        keys_to_remove = []
        for key in self._store:
            parts = key.split(":", 1)
            if tier and parts[0] != tier:
                continue
            if domain and (len(parts) < 2 or parts[1] != domain):
                continue
            keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._store[key]

        return len(keys_to_remove)

    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        self._store.clear()

    @property
    def stats(self) -> dict:
        """Cache statistics for monitoring."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds,
        }

    # --- Internal ---

    def _make_key(self, tier: str, domain: str) -> str:
        return f"{tier}:{domain}"

    def _evict_oldest(self) -> None:
        """Remove the oldest (least recently cached) entry."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k].cached_at)
        del self._store[oldest_key]
