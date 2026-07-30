# RaceOS AI Factory — Installation & Bootstrap Strategy

> **Goal:** Brand-new machine → working factory in under 10 minutes.

---

## Recommended Primary Method: `pipx install raceos-factory`

### Why pipx

| Method | Pros | Cons | Verdict |
|---|---|---|---|
| **pipx** | Isolated venv, one command, auto PATH, cross-platform | Needs Python pre-installed | **PRIMARY** |
| Homebrew | Native macOS feel | macOS/Linux only, slow tap updates | Secondary (macOS) |
| npm | Devs already have Node | Python dependency still needed | Not suitable (Python project) |
| Docker | Zero-install, reproducible | Heavy, can't access local files easily | CI/CD + isolated env |
| Standalone binary | Zero deps | Large binary (200MB+), hard to update | Future (v2.0) |

**Decision:** `pipx` is the primary method because:
1. Works on macOS (both Silicon + Intel), Linux, Windows (native + WSL)
2. Creates isolated environment (no conflict with system Python)
3. Single command install + automatic PATH setup
4. `pipx upgrade raceos-factory` for updates
5. Python 3.11+ is the only prerequisite (pre-installed on modern macOS/Linux)

---

## Installation Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                   INSTALLATION PATHS                              │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ Prerequisites│    │   Install    │    │   Post-Install   │  │
│  │              │    │              │    │                  │  │
│  │ Python 3.11+ │──►│ pipx install │──►│ raceos doctor    │  │
│  │ (or Docker)  │    │ raceos-factory│   │ raceos install   │  │
│  │              │    │              │    │ (optional deps)  │  │
│  └─────────────┘    └──────────────┘    └──────────────────┘  │
│                                                                 │
│  Alternative paths:                                             │
│    macOS:   brew install raceos                                 │
│    Docker:  docker run ghcr.io/raceos/factory                   │
│    Dev:     git clone + uv sync (contributor mode)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Platform Support

| Platform | Method | Prerequisites | Tested |
|---|---|---|---|
| macOS Apple Silicon (M1-M4) | pipx / brew | Python 3.11+ (via Xcode CLT or brew) | Primary |
| macOS Intel | pipx / brew | Python 3.11+ | Supported |
| Ubuntu 22.04+ | pipx | Python 3.11+ (system or deadsnakes PPA) | Supported |
| Fedora 38+ | pipx | Python 3.11+ (system) | Supported |
| Arch Linux | pipx | Python (always latest) | Supported |
| Windows (WSL2) | pipx inside WSL | Ubuntu on WSL2, Python 3.11+ | Supported |
| Windows (native) | pipx | Python 3.11+ from python.org | Best-effort |

---

## One-Line Install Scripts

### macOS / Linux (recommended)

```bash
# Option A: If Python 3.11+ exists
pipx install raceos-factory && raceos doctor

# Option B: Full bootstrap (installs Python if needed)
curl -fsSL https://get.raceos.dev | bash
```

### macOS (Homebrew alternative)

```bash
brew tap raceos/tap && brew install raceos
```

### Docker (isolated, no local install)

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  ghcr.io/raceos/factory:latest
```

### Developer Mode (contributors)

```bash
git clone https://github.com/raceos/raceos-factory.git
cd raceos-factory
uv sync --all-extras
uv run raceos doctor
```

---

## Bootstrap Script (`get.raceos.dev`)

```
#!/bin/bash — what it does (high-level, no implementation):

1. Detect OS + architecture (macOS-arm64, macOS-x86, linux-x64, WSL)
2. Check Python version (≥3.11 required)
   - If missing: suggest `brew install python@3.12` or system install
   - Do NOT auto-install Python (too invasive)
3. Check pipx installed
   - If missing: `pip install --user pipx && pipx ensurepath`
4. Install: `pipx install raceos-factory`
5. Run: `raceos doctor` (verify everything works)
6. Print: "Ready! Run `raceos` to start."

Total steps: ~4 commands, ~2 minutes
```

---

## Dependency Management

### Dependency Tiers

```
TIER 1: Required (installed by pipx automatically)
    Python packages: typer, rich, structlog, pyyaml, httpx, langgraph,
                     pydantic, jinja2, tiktoken, tenacity, filelock

TIER 2: Optional (installed by `raceos install`)
    - opencode CLI (npm package or binary)
    - platformio (firmware builds/tests)
    - Node.js 18+ (for MCP servers)

TIER 3: Development only (for contributors)
    - uv, ruff, pytest, pytest-cov, respx
```

### `raceos install` — Optional Dependency Installer

```
$ raceos install

  Checking optional dependencies...

  ┌──────────────────────────────────────────────────────────┐
  │ Component          │ Status  │ Action                    │
  ├──────────────────────────────────────────────────────────┤
  │ opencode           │ missing │ npm install -g opencode   │
  │ platformio         │ missing │ pipx install platformio   │
  │ node.js            │ v20.11  │ ✅ installed              │
  │ codebase-memory    │ missing │ (auto via npx on demand)  │
  └──────────────────────────────────────────────────────────┘

  Install all missing? [Y/n]: y

  Installing opencode...        ✅
  Installing platformio...      ✅

  All dependencies installed. Run `raceos doctor` to verify.
```

### Dependency Resolution Strategy

```
RULE 1: Core deps installed via pipx (Python ecosystem)
RULE 2: Optional deps installed on-demand by `raceos install`
RULE 3: MCP servers launched via npx (no global install needed)
RULE 4: Never auto-install system packages (Python, Node) without consent
RULE 5: Missing optional deps = graceful degradation (not crash)
         - No opencode → can't execute code tasks (error message explains)
         - No platformio → can't build/test firmware (skip validation)
         - No Node.js → can't run MCP servers (skip Tier 4 memory)
```

---

## Version Management

### Versioning Scheme

```
raceos-factory 1.2.3
               │ │ │
               │ │ └── Patch: bug fixes, no config changes
               │ └──── Minor: new features, backward-compatible config
               └────── Major: breaking changes, migration required
```

### Version Pinning

```toml
# pyproject.toml — dependencies pinned to compatible ranges
dependencies = [
    "langgraph>=0.2,<1.0",        # Pin major (pre-1.0 = breaking changes possible)
    "httpx>=0.27,<1.0",           # Pin major
    "pydantic>=2.0,<3.0",         # Pin major
    "tiktoken>=0.7,<1.0",         # Pin major
]
```

### Config Schema Versioning

```yaml
# Every config file includes schema version
# config/factory.yaml
_schema_version: "1.0"
factory:
  name: "raceos-factory"
  ...
```

Migration triggers when `_schema_version` in file < expected version.

---

## Update Strategy

### `raceos update`

```
$ raceos update

  Current: raceos-factory 1.2.3
  Latest:  raceos-factory 1.3.0

  Changes:
    • New command: raceos telemetry
    • Improved: budget tracking precision
    • Fixed: context cache invalidation bug

  Config migration: not required (backward compatible)

  [U]pdate  [S]kip  [V]iew changelog

> u
  Updating via pipx...
  ✅ Updated to 1.3.0
  Running post-update checks...
  ✅ raceos doctor — all healthy
```

### Update Flow

```
1. Check PyPI for latest version (GET https://pypi.org/pypi/raceos-factory/json)
2. Compare with installed version
3. If update available:
   a. Show changelog summary
   b. Check if config migration needed (schema_version comparison)
   c. If migration needed → run `raceos migrate` first
   d. Run: pipx upgrade raceos-factory
   e. Run: raceos doctor (verify post-update)
4. If migration fails → auto-rollback to previous version
```

### Auto-Update (opt-in)

```yaml
# ~/.raceos/preferences.yaml
updates:
  auto_check: true           # Check on startup (non-blocking)
  auto_install: false        # Never auto-install (human decides)
  check_interval_hours: 24   # Check once per day
  channel: "stable"          # stable | beta | nightly
```

---

## Rollback Strategy

### `raceos update --rollback`

```
$ raceos update --rollback

  Rollback options:
    1. 1.2.3 (previous, installed 3 days ago)
    2. 1.2.1 (2 versions ago)

  Select: 1

  Rolling back to 1.2.3...
  ✅ Rolled back successfully.
  ✅ Config compatible (no migration needed).
```

### Rollback Implementation

```
pipx stores previous versions. Rollback = pipx install raceos-factory==1.2.3

Config rollback:
  - data/backups/ contains timestamped config snapshots
  - Taken automatically before every update
  - `raceos restore --config` restores previous config
```

---

## Backup & Restore

### `raceos backup`

```
$ raceos backup

  Creating backup...

  Included:
    ✅ config/ (7 files)
    ✅ data/sessions/ (3 sessions)
    ✅ data/checkpoints.db (2 tasks)
    ✅ data/cost_ledger.jsonl (142 entries)
    ✅ .env (encrypted)

  Excluded:
    ⬜ Source code (in git)
    ⬜ node_modules / .venv (reinstallable)
    ⬜ Brain (.raceos/) — managed separately

  Saved: data/backups/backup-2026-07-30T08:00:00.tar.gz (12 KB)
```

### Backup Contents

```
backup-{timestamp}.tar.gz
├── config/           All YAML/JSON config files
├── data/
│   ├── sessions/     Session state (resumable tasks)
│   ├── checkpoints.db  Crash recovery state
│   ├── cost_ledger.jsonl  Spending history
│   └── patterns.jsonl  Codebase memory patterns
├── .env.encrypted    API keys (encrypted with machine key)
└── manifest.json     Backup metadata (version, timestamp, checksums)
```

### `raceos restore`

```
$ raceos restore data/backups/backup-2026-07-30T08:00:00.tar.gz

  Restoring from backup...

  ✅ config/ restored (7 files)
  ✅ data/sessions/ restored (3 sessions)
  ✅ data/checkpoints.db restored
  ⚠️ .env: decrypt with machine key? [Y/n]: y
  ✅ .env restored

  Running health check...
  ✅ raceos doctor — all healthy
```

---

## Migration Strategy

### `raceos migrate`

```
$ raceos migrate

  Checking configuration versions...

  ┌─────────────────────────────────┬──────────┬──────────┐
  │ File                            │ Current  │ Expected │
  ├─────────────────────────────────┼──────────┼──────────┤
  │ config/factory.yaml             │ 1.0      │ 1.1      │
  │ config/router.yaml              │ 1.0      │ 1.0      │
  │ config/opencode.json            │ 1.0      │ 1.0      │
  └─────────────────────────────────┴──────────┴──────────┘

  1 file needs migration:
    factory.yaml 1.0 → 1.1:
      + Added: factory.metrics.enabled (default: true)
      + Added: factory.metrics.endpoint (default: null)
      ~ Changed: factory.logging.format default "text" → "json"

  [M]igrate  [S]kip  [D]iff

> m
  Backing up current config...  ✅
  Migrating factory.yaml...     ✅
  Verifying...                  ✅

  Migration complete. Previous config saved to data/backups/pre-migrate-{timestamp}/
```

### Migration Rules

```
RULE 1: Additive changes (new fields with defaults) = auto-migrate
RULE 2: Destructive changes (field removed/renamed) = manual confirmation
RULE 3: Always backup before migrate
RULE 4: Migration is idempotent (running twice = same result)
RULE 5: Each migration is a named, versioned script:
         migrations/
           001_factory_add_metrics.py
           002_router_add_deepseek_v4.py
```

---

## Health Check

### `raceos doctor`

```
$ raceos doctor

╔══════════════════════════════════════════════════════════════╗
║  RaceOS Factory — System Health                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                             ║
║  Runtime Environment                                        ║
║    ✅ Python 3.12.4 (≥3.11 required)                        ║
║    ✅ pipx 1.7.0                                            ║
║    ✅ raceos-factory 1.3.0 (latest)                         ║
║    ✅ Platform: macOS 15.0 arm64                            ║
║                                                             ║
║  Configuration                                              ║
║    ✅ config/factory.yaml (schema 1.1, valid)               ║
║    ✅ config/router.yaml (14 routing rules, valid)          ║
║    ✅ config/opencode.json (valid)                          ║
║    ✅ .env (OPENROUTER_API_KEY set, 48 chars)               ║
║                                                             ║
║  Project Brain                                              ║
║    ✅ .raceos/ accessible (43 documents)                    ║
║    ✅ openspec/specs/ (6 specs)                             ║
║    ✅ adr/ (25 ADRs)                                       ║
║                                                             ║
║  Optional Tools                                             ║
║    ✅ opencode v1.2.0                                       ║
║    ✅ platformio v6.1.0                                     ║
║    ✅ node v20.11.0 + npx                                   ║
║    ⚠️ codebase-memory-mcp (available via npx, not tested)   ║
║                                                             ║
║  Connectivity                                               ║
║    ✅ OpenRouter API reachable (ping)                       ║
║    ✅ API key valid (authenticated)                         ║
║                                                             ║
║  Budget                                                     ║
║    ✅ $3.42 / $50.00 (6.8% used today)                     ║
║                                                             ║
║  Persistence                                                ║
║    ✅ data/checkpoints.db (0 incomplete tasks)              ║
║    ✅ data/cost_ledger.jsonl (142 entries, 18 KB)           ║
║                                                             ║
╠══════════════════════════════════════════════════════════════╣
║  Status: HEALTHY (0 errors, 1 warning)                      ║
║  Warning: codebase-memory-mcp not verified                  ║
║    Fix: npx -y @anthropic/codebase-memory-mcp --version    ║
╚══════════════════════════════════════════════════════════════╝
```

### `raceos repair`

```
$ raceos repair

  Diagnosing issues...

  Found 2 fixable issues:

  1. data/checkpoints.db is locked (stale lock from crash)
     Fix: Remove stale lock file
     [F]ix  [S]kip

  2. config/router.yaml references model "gpt-4-turbo" (deprecated)
     Fix: Replace with "gpt-5"
     [F]ix  [S]kip

  > f

  ✅ Fixed: removed stale lock
  ✅ Fixed: updated model reference

  Running doctor...
  ✅ All healthy.
```

---

## Release Strategy

### Release Cadence

```
Stable releases:  Every 2 weeks (even weeks)
Patch releases:   As needed (critical bugs)
Beta releases:    Weekly (odd weeks, opt-in)
```

### Release Pipeline

```
1. Developer merges to main
2. GitHub Actions triggers:
   a. Run full test suite (unit + integration)
   b. Build package (sdist + wheel)
   c. Run `raceos doctor` in CI (smoke test)
   d. Tag release (vX.Y.Z)
3. Publish:
   a. PyPI: `twine upload dist/*`
   b. GitHub Release: changelog + binaries
   c. Docker: `docker push ghcr.io/raceos/factory:X.Y.Z`
   d. Homebrew: update formula in raceos/homebrew-tap
4. Post-release:
   a. Announce in CHANGELOG.md
   b. Update docs/getting-started.md
```

### Distribution Channels

| Channel | Method | Audience | Latency |
|---|---|---|---|
| **PyPI** (primary) | `pipx install raceos-factory` | All users | Immediate |
| **GitHub Releases** | Download `.whl` or `.tar.gz` | Manual installers | Immediate |
| **Docker Hub / GHCR** | `docker pull ghcr.io/raceos/factory` | CI/CD, isolated env | ~5 min post-release |
| **Homebrew** | `brew install raceos` | macOS users | ~1 hour (PR merge) |
| **Standalone binary** | Download from releases (PyInstaller) | Zero-dep users | Future (v2.0) |

### Version Channels

```
stable:    pipx install raceos-factory              (default)
beta:      pipx install raceos-factory --pre
nightly:   pipx install raceos-factory==0.0.dev*    (from TestPyPI)
pinned:    pipx install raceos-factory==1.2.3       (specific version)
```

---

## Uninstall

### `raceos uninstall`

```
$ raceos uninstall

  This will remove:
    ✅ raceos-factory package (pipx)
    ⬜ Configuration (config/) — keep? [Y/n]: y
    ⬜ Data (data/) — keep? [Y/n]: y
    ⬜ History (.raceos_history) — keep? [Y/n]: n

  Uninstalling...
  ✅ Package removed: pipx uninstall raceos-factory
  ✅ History removed
  ℹ️ Config and data preserved at: ~/raceos-factory-backup/

  To fully remove: rm -rf ~/raceos-factory-backup/
```

---

## Security Considerations

| Concern | Mitigation |
|---|---|
| API keys in backup | Encrypted with machine-specific key |
| Supply chain (pip packages) | Pin versions, use hashes in lockfile |
| Auto-update installs malware | Auto-check only, never auto-install |
| Homebrew formula tampering | Signed taps, checksum verification |
| Docker image vulnerabilities | Base image pinned, weekly rebuild |

---

## Timeline to Production

```
Week 1: PyPI package (pip install works)
Week 2: GitHub Actions CI/CD (auto-publish on tag)
Week 3: Docker image + bootstrap script (get.raceos.dev)
Week 4: Homebrew formula + documentation
Week 5: Standalone binary (PyInstaller, experimental)
```

---

## Command Summary

| Command | Does | Prerequisites |
|---|---|---|
| `raceos install` | Install optional deps (opencode, pio) | Core already installed |
| `raceos doctor` | Check everything works | None |
| `raceos repair` | Auto-fix common issues | None |
| `raceos update` | Upgrade to latest version | pipx |
| `raceos migrate` | Update config schemas | After update |
| `raceos backup` | Snapshot config + data | None |
| `raceos restore` | Restore from backup | Backup file |
| `raceos uninstall` | Clean removal | None |

---

*End of Installation Strategy*
