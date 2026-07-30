# Config

> Pydantic schemas for all YAML configs with validation on startup.

## Responsibility

Defines Pydantic models for every configuration surface (routing rules, model catalog, budget limits, context tiers, MCP settings, OpenCode paths). Provides loader functions that read YAML files and validate them into typed config objects. Validates all configuration on application startup — fails fast with clear error messages on misconfiguration.

## Does NOT

- Define default behavior or business logic
- Make runtime decisions based on config (other modules do that)
- Watch for config changes (load once on startup)
- Store secrets directly (references environment variables)

## Key Files (planned)

- `schemas.py` — Pydantic models for all config sections
- `loader.py` — YAML file loading and validation
- `defaults.py` — default config values and paths
- `types.py` — shared config type aliases

## Dependencies

- `pydantic` (schema validation)
- `pyyaml` (YAML parsing)
- `pathlib` (file path handling)
