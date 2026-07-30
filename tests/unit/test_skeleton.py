"""Skeleton test — verifies project structure is correct."""

from pathlib import Path

import factory


def test_version():
    """Package version is set."""
    assert factory.__version__ == "0.1.0"


def test_config_files_exist(config_dir: Path):
    """All required config files exist."""
    required = ["factory.yaml", "router.yaml", "context-tiers.yaml", "mcp-servers.yaml", "opencode.json", "memory.yaml", "openspec.yaml"]
    for filename in required:
        assert (config_dir / filename).exists(), f"Missing config: {filename}"


def test_source_packages_exist(factory_root: Path):
    """All source packages have __init__.py."""
    packages = [
        "src/factory",
        "src/factory/gateway",
        "src/factory/router",
        "src/factory/context",
        "src/factory/orchestrator",
        "src/factory/orchestrator/nodes",
        "src/factory/executor",
        "src/factory/executor/adapters",
        "src/factory/memory",
        "src/factory/spec_engine",
        "src/factory/cli",
        "src/factory/cli/commands",
        "src/factory/config",
    ]
    for pkg in packages:
        init_file = factory_root / pkg / "__init__.py"
        assert init_file.exists(), f"Missing __init__.py in {pkg}"
