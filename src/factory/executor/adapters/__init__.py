# Domain-specific adapters.
"""
Adapter registry — maps domain names to adapter instances.

Usage:
    from factory.executor.adapters import get_adapter
    adapter = get_adapter("firmware")
    config = adapter.get_config()
"""

from .backend import BackendAdapter
from .base import AdapterConfig, BaseAdapter
from .firmware import FirmwareAdapter
from .mobile import MobileAdapter

# Adapter registry — add new domains here
_ADAPTERS: dict[str, BaseAdapter] = {
    "firmware": FirmwareAdapter(),
    "mobile": MobileAdapter(),
    "backend": BackendAdapter(),
}


def get_adapter(domain: str) -> BaseAdapter:
    """
    Get the adapter for a domain.

    Args:
        domain: Target domain name.

    Returns:
        Domain-specific adapter instance.

    Raises:
        ValueError: If domain is not registered.
    """
    if domain not in _ADAPTERS:
        available = ", ".join(_ADAPTERS.keys())
        raise ValueError(f"Unknown domain '{domain}'. Available: {available}")
    return _ADAPTERS[domain]


def list_domains() -> list[str]:
    """Return all registered domain names."""
    return list(_ADAPTERS.keys())


__all__ = [
    "BaseAdapter",
    "AdapterConfig",
    "FirmwareAdapter",
    "MobileAdapter",
    "BackendAdapter",
    "get_adapter",
    "list_domains",
]
