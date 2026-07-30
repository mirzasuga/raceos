"""
Configuration Manager.

Loads, merges, and provides access to factory configuration.
Supports the config hierarchy:
    1. CLI flags (highest)
    2. Environment variables
    3. Session overrides (/config set)
    4. Project config (config/*.yaml)
    5. Defaults (lowest)

Also provides the `raceos config` command implementation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table


# --- Session Overrides (in-memory, per-session) ---
_session_overrides: dict[str, str] = {}


# --- Config Loading ---

def load_config(config_dir: str = "config") -> dict[str, Any]:
    """
    Load and merge all configuration files.

    Returns a flat dict with dot-notation keys:
        "brain.root" → "../.raceos/"
        "budget.daily_limit_usd" → 50.0
    """
    config_path = Path(config_dir)
    merged: dict[str, Any] = {}

    # Load each config file
    for yaml_file in sorted(config_path.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text()) or {}
            flat = _flatten(data, prefix="")
            merged.update(flat)
        except (yaml.YAMLError, OSError):
            continue

    # Load opencode.json
    json_path = config_path / "opencode.json"
    if json_path.exists():
        import json
        try:
            data = json.loads(json_path.read_text())
            flat = _flatten({"opencode": data}, prefix="")
            merged.update(flat)
        except (json.JSONDecodeError, OSError):
            pass

    return merged


def get_config(key: str, default: Any = None) -> Any:
    """
    Get a config value respecting the hierarchy.

    Priority: session override > env > project config > default
    """
    # 1. Session override
    if key in _session_overrides:
        return _session_overrides[key]

    # 2. Environment variable (convert dots to underscores, uppercase)
    env_key = key.upper().replace(".", "_")
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val

    # 3. Project config
    config = load_config()
    if key in config:
        return config[key]

    # 4. Default
    return default


def set_config(key: str, value: str, persist: bool = False) -> None:
    """
    Set a config value.

    Args:
        key: Dot-notation config key.
        value: Value to set.
        persist: If True, write to project config. If False, session only.
    """
    if persist:
        # Write back to the appropriate YAML file
        _persist_to_yaml(key, value)
    else:
        _session_overrides[key] = value


def reset_config(key: str | None = None) -> None:
    """Reset session overrides. If key=None, reset all."""
    if key is None:
        _session_overrides.clear()
    elif key in _session_overrides:
        del _session_overrides[key]


# --- CLI Command Handler ---

def handle_config(action: str, key: str | None, value: str | None, console: Console) -> None:
    """Handle `raceos config` and `/config` commands."""

    if action == "list":
        _show_config_table(console)

    elif action == "get":
        if not key:
            console.print("[red]Usage: config get <key>[/red]")
            return
        val = get_config(key, default="[not set]")
        console.print(f"  {key} = {val}")

    elif action == "set":
        if not key or value is None:
            console.print("[red]Usage: config set <key> <value>[/red]")
            return
        set_config(key, value)
        console.print(f"  [green]✅ {key} = {value}[/green] [dim](session only)[/dim]")

    elif action == "reset":
        reset_config(key)
        target = key or "all overrides"
        console.print(f"  [yellow]↺ Reset: {target}[/yellow]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Usage: config [list|get|set|reset] [key] [value][/dim]")


# --- Internal ---

def _persist_to_yaml(key: str, value: str) -> None:
    """
    Persist a config value to the appropriate YAML file.

    Determines which file owns the key by prefix matching,
    then updates that file in-place.
    """
    config_dir = Path("config")

    # Map key prefix to file
    file_map = {
        "factory": "factory.yaml",
        "router": "router.yaml",
        "catalog": "router.yaml",
        "policy": "router.yaml",
        "fallback": "router.yaml",
        "retry": "router.yaml",
        "timeout": "router.yaml",
        "cost": "router.yaml",
        "gateway": "router.yaml",
        "context": "context-tiers.yaml",
        "memory": "memory.yaml",
        "openspec": "openspec.yaml",
        "mcp_servers": "mcp-servers.yaml",
    }

    # Find target file
    prefix = key.split(".")[0]
    target_file = file_map.get(prefix)

    if not target_file:
        # Can't determine file — store as session override
        _session_overrides[key] = value
        return

    target_path = config_dir / target_file
    if not target_path.exists():
        _session_overrides[key] = value
        return

    # Load, modify, save
    try:
        data = yaml.safe_load(target_path.read_text()) or {}

        # Navigate to the nested key and set value
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        # Try to preserve type (int, float, bool)
        typed_value: Any = value
        if value.lower() in ("true", "false"):
            typed_value = value.lower() == "true"
        else:
            try:
                typed_value = int(value)
            except ValueError:
                try:
                    typed_value = float(value)
                except ValueError:
                    pass

        current[parts[-1]] = typed_value

        # Write back
        target_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    except (yaml.YAMLError, OSError, KeyError):
        # Failed to persist — fall back to session override
        _session_overrides[key] = value


def _show_config_table(console: Console) -> None:
    """Display all config as a rich table."""
    config = load_config()

    table = Table(title="Configuration", show_lines=False)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")

    # Show overrides first
    for key, val in sorted(_session_overrides.items()):
        table.add_row(key, str(val), "override")

    # Show project config (skip overridden keys)
    for key, val in sorted(config.items()):
        if key in _session_overrides:
            continue
        # Skip overly verbose keys
        if len(str(val)) > 80:
            val = str(val)[:77] + "..."
        table.add_row(key, str(val), "config")

    console.print(table)


def _flatten(data: dict, prefix: str) -> dict[str, Any]:
    """Flatten nested dict to dot-notation keys."""
    items: dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flatten(value, full_key))
        else:
            items[full_key] = value
    return items
