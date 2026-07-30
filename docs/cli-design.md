# RaceOS CLI — Production Design

> Staff DX Engineer specification for the `raceos` command-line interface.

---

## Overview

```
raceos                    → Interactive shell (default)
raceos <command>          → Single command mode
raceos chat               → Conversational AI session
raceos feature "..."      → Orchestrated feature implementation
raceos doctor             → System health check
```

The CLI is the human's primary interface to the AI Software Factory.
It must feel fast, informative, and recoverable.

---

## CLI Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        raceos CLI                                 │
│                                                                 │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │   Parser     │  │   Router      │  │   Shell (REPL)    │   │
│  │              │  │               │  │                   │   │
│  │  args/flags  │  │  command →    │  │  readline +       │   │
│  │  slash cmds  │  │  handler      │  │  completion +     │   │
│  │  intent      │  │  plugin       │  │  history          │   │
│  └──────┬───────┘  └───────┬───────┘  └─────────┬─────────┘   │
│         │                   │                    │              │
│         ▼                   ▼                    ▼              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Command Handlers                       │   │
│  │                                                         │   │
│  │  feature │ review │ firmware │ chat │ docs │ doctor │.. │   │
│  └─────────────────────────────┬───────────────────────────┘   │
│                                │                                │
│                                ▼                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Session Manager                        │   │
│  │                                                         │   │
│  │  state │ history │ resume │ checkpoint │ approval queue │   │
│  └─────────────────────────────┬───────────────────────────┘   │
│                                │                                │
│                                ▼                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Output Layer                           │   │
│  │                                                         │   │
│  │  streaming │ progress │ panels │ tables │ spinners      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Plugin System                          │   │
│  │                                                         │   │
│  │  discovery │ registration │ hooks │ extensions          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
src/factory/cli/
├── __init__.py
├── app.py                    # Typer app root + global options
├── shell.py                  # Interactive REPL shell
├── parser.py                 # Argument parsing + slash command detection
├── router.py                 # Command → handler routing
├── intent.py                 # Natural language intent detection
│
├── commands/                 # Command handlers (one file per command)
│   ├── __init__.py
│   ├── chat.py               # raceos chat
│   ├── feature.py            # raceos feature "..."
│   ├── review.py             # raceos review
│   ├── hardware.py           # raceos hardware
│   ├── firmware.py           # raceos firmware
│   ├── mobile.py             # raceos mobile
│   ├── docs.py               # raceos docs
│   ├── research.py           # raceos research
│   ├── telemetry.py          # raceos telemetry
│   ├── doctor.py             # raceos doctor
│   ├── update.py             # raceos update
│   ├── logs.py               # raceos logs
│   ├── status.py             # raceos status
│   ├── config.py             # raceos config
│   ├── install.py            # raceos install
│   ├── repair.py             # raceos repair
│   ├── migrate.py            # raceos migrate
│   ├── backup.py             # raceos backup
│   └── restore.py            # raceos restore
│
├── session/                  # Session management
│   ├── __init__.py
│   ├── manager.py            # Session lifecycle (create/resume/end)
│   ├── state.py              # Session state persistence
│   ├── history.py            # Command history (per-session + global)
│   └── approval.py           # Human approval queue + prompts
│
├── output/                   # Output rendering
│   ├── __init__.py
│   ├── stream.py             # Streaming token-by-token output
│   ├── progress.py           # Progress bars + spinners + phases
│   ├── panels.py             # Rich panels (results, errors, diffs)
│   ├── tables.py             # Rich tables (status, budget, tasks)
│   └── theme.py              # Color scheme + styling constants
│
├── plugins/                  # Plugin system
│   ├── __init__.py
│   ├── loader.py             # Plugin discovery + loading
│   ├── registry.py           # Plugin registration + hooks
│   ├── base.py               # Plugin base class (extension API)
│   └── hooks.py              # Hook points (pre/post command, etc.)
│
├── config/                   # CLI-specific config
│   ├── __init__.py
│   └── manager.py            # Config get/set/list/reset
│
└── sanitize.py               # Output sanitization (existing)
```

---

## Startup Flow

```
$ raceos

1. Parse args/flags                              [< 1ms]
   └── No args? → enter interactive shell
   └── Args? → single command mode

2. Load configuration                            [< 10ms]
   ├── Read config/factory.yaml
   ├── Read .env (API keys)
   └── Merge with CLI flags (flags override)

3. Check system health (fast)                    [< 50ms]
   ├── Python version OK?
   ├── Config files exist?
   ├── API key set?
   └── (Skip if --no-check flag)

4. Initialize session                            [< 10ms]
   ├── Load/create session state
   ├── Check for incomplete tasks (resume?)
   └── Load command history

5. Load plugins                                  [< 20ms]
   ├── Scan plugins/ directory
   ├── Register hooks
   └── Validate plugin compatibility

6. Ready                                         [< 100ms total]
   ├── Single command? → execute → exit
   └── Interactive? → show prompt → wait

TOTAL STARTUP: < 100ms (perceived instant)
```

### Resume Flow (crash recovery)

```
$ raceos

⚠️  Found 1 incomplete task from previous session:
    TASK-A1B2C3: "implement watchdog timer HAL" (paused at: execute)

  [R]esume  [D]ismiss  [S]kip

> r
Resuming TASK-A1B2C3 from checkpoint: execute node...
```

---

## Command Parser

### Modes

```
┌─────────────────────────────────────────────────┐
│ MODE 1: Direct Command                           │
│                                                 │
│ $ raceos feature "add BLE support"              │
│ $ raceos doctor                                 │
│ $ raceos status                                 │
│                                                 │
│ → Parse subcommand + args → route → execute     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ MODE 2: Interactive Shell                        │
│                                                 │
│ raceos> add BLE support                         │
│ raceos> /status                                 │
│ raceos> /approve TASK-001                       │
│                                                 │
│ → Detect: slash command OR natural language      │
│ → Slash? → route to command handler             │
│ → Natural? → intent detection → route           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ MODE 3: Piped Input                              │
│                                                 │
│ $ echo "fix typo" | raceos firmware             │
│ $ cat tasks.txt | raceos feature --batch        │
│                                                 │
│ → Detect stdin pipe → non-interactive mode      │
│ → No spinners, no color (unless --color=always) │
└─────────────────────────────────────────────────┘
```

### Slash Commands (Interactive Shell)

```
/help                 Show all commands
/status               Show active/pending tasks
/approve <id>         Approve a pending task
/reject <id> [reason] Reject a pending task
/resume <id>          Resume a paused task
/cancel <id>          Cancel a running task
/budget               Show cost status
/history              Show session history
/clear                Clear screen
/config <key> [value] Get/set config
/plugin list          List loaded plugins
/quit                 Exit shell
```

### Argument Schema (per command)

```
raceos feature <description> [--domain firmware|mobile|backend]
                             [--file <path>...]
                             [--priority low|normal|high]
                             [--dry-run]
                             [--no-plan]
                             [--auto-approve]

raceos review [--last]
              [--file <path>...]
              [--diff]

raceos config get <key>
raceos config set <key> <value>
raceos config list
raceos config reset

raceos logs [--tail N]
            [--task <id>]
            [--level error|warn|info|debug]
            [--since <duration>]
```

---

## Intent Detection

For interactive shell mode: natural language → command routing.

```python
# Intent detection is lightweight (no LLM needed for most inputs):

INTENT_PATTERNS = {
    # Direct matches (regex)
    r"^(implement|add|create|build)\s+": "feature",
    r"^(fix|bug|debug|why)\s+": "firmware",      # debugging
    r"^(review|check|audit)\s+": "review",
    r"^(how|what|explain|describe)\s+": "docs",   # documentation question
    r"^(wire|pin|schematic|bom)\s+": "hardware",
    r"^(research|interview|market)\s+": "research",
    r"^(status|budget|task)\s*$": "status",

    # Slash commands (exact match)
    r"^/": "slash_command",
}

# Fallback: if no pattern matches → send to "chat" (general AI)
```

### Detection Priority

```
1. Slash command (/...) → route to command directly
2. Explicit domain flag (--domain) → route to domain handler
3. Keyword pattern match → route to inferred handler
4. Fallback → "chat" handler (general AI conversation)
```

---

## Session Management

### Session Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CREATE    │────►│   ACTIVE    │────►│    END      │
│             │     │             │     │             │
│ new session │     │ commands    │     │ save state  │
│ load config │     │ tasks run   │     │ flush logs  │
│ check crash │     │ approvals   │     │ cleanup     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │   SUSPEND   │
                    │             │
                    │ checkpoint  │
                    │ resumable   │
                    └─────────────┘
```

### Session State (persisted to data/sessions/)

```yaml
session:
  id: "sess-20260730-001"
  started_at: "2026-07-30T02:30:00+07:00"
  status: "active"              # active | suspended | ended
  tasks:
    - id: "TASK-A1B2C3"
      status: "completed"
    - id: "TASK-D4E5F6"
      status: "awaiting_approval"
  history:
    - "raceos feature 'add BLE support' --domain firmware"
    - "/approve TASK-A1B2C3"
  config_overrides: {}          # Per-session config (flags)
```

### Approval Queue

```
raceos> implement engine load gauge

📋 Plan generated for TASK-A1B2C3:
   ├── 1. Add threshold constants to display_tokens.h
   ├── 2. Implement LoadGaugeView in middleware/
   ├── 3. Integrate into DashboardView
   ├── 4. Write Unity tests
   └── 5. Verify build + test

   Estimated: ~58s, $0.56
   Domain: firmware
   Complexity: HIGH

   [A]pprove  [R]eject  [E]dit plan  [V]iew details

> a
✅ Approved. Executing...
```

---

## Streaming Output

### Token Streaming (LLM responses)

```
raceos> explain layered architecture

  Layered architecture organizes sof▌
  Layered architecture organizes software into▌
  Layered architecture organizes software into unidirectional▌
  ...
  (streaming token-by-token with cursor)
```

Implementation:
```python
# Use rich.live + streaming iterator
async for token in stream_completion(request):
    live.update(buffer + token)
    buffer += token
```

### Phase Progress (task execution)

```
raceos> implement engine load gauge

  ┌─ Task TASK-A1B2C3 ─────────────────────────────────┐
  │                                                     │
  │  ✅ classify      2s    DeepSeek    $0.0001         │
  │  ✅ context       0.3s  (cached)    $0.00           │
  │  ✅ plan          8s    GPT-5       $0.30           │
  │  ✅ approve       human             $0.00           │
  │  ⏳ execute       ...   Claude      estimating...   │
  │  ○ review                                           │
  │  ○ validate                                         │
  │  ○ learn                                            │
  │                                                     │
  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   62%    │
  │  Elapsed: 34s │ Est. remaining: 24s │ $0.48         │
  └─────────────────────────────────────────────────────┘
```

### Progress States

```
○  pending (not started)
⏳ running (in progress, spinner)
✅ passed (completed successfully)
❌ failed (error)
⚠️ warning (completed with issues)
⏸️ paused (waiting for human)
🔄 retrying (attempt N)
```

---

## Logging

### Log Levels

```
DEBUG   → verbose internal state (hidden by default)
INFO    → user-relevant progress ("Task completed")
WARN    → non-fatal issues ("Budget at 80%")
ERROR   → failures ("Build failed", "API timeout")
```

### Log Destinations

```
Terminal  → INFO+ shown to user (via rich output layer)
File      → ALL levels written to data/logs/raceos.log
Struct    → JSON Lines for machine parsing (data/logs/structured.jsonl)
```

### Log Format

```json
{
  "ts": "2026-07-30T02:30:00.123Z",
  "level": "info",
  "event": "task.completed",
  "task_id": "TASK-A1B2C3",
  "duration_s": 58.2,
  "cost_usd": 0.56,
  "model": "anthropic/claude-sonnet-4.6",
  "session_id": "sess-20260730-001"
}
```

### `raceos logs` command

```
$ raceos logs --tail 20
$ raceos logs --task TASK-A1B2C3
$ raceos logs --level error --since 1h
$ raceos logs --json  # Raw structured output
```

---

## Configuration Management

### Hierarchy (highest priority wins)

```
1. CLI flags              (--model claude-opus-4)
2. Environment variables  (OPENROUTER_API_KEY)
3. Session overrides      (/config set model claude-opus-4)
4. User config            (~/.raceos/config.yaml)
5. Project config         (config/factory.yaml + router.yaml)
6. Defaults               (hardcoded in schemas)
```

### `raceos config` command

```
$ raceos config list
┌──────────────────────────┬──────────────────────────┬────────┐
│ Key                      │ Value                    │ Source │
├──────────────────────────┼──────────────────────────┼────────┤
│ model.default            │ anthropic/claude-sonnet-4│ router │
│ budget.daily_limit_usd   │ 50.00                   │ router │
│ brain.root               │ ../.raceos/             │ factory│
│ logging.level            │ INFO                    │ factory│
└──────────────────────────┴──────────────────────────┴────────┘

$ raceos config set budget.daily_limit_usd 100
✅ Set budget.daily_limit_usd = 100 (session override, not persisted)
   To persist: raceos config set budget.daily_limit_usd 100 --persist

$ raceos config get model.default
anthropic/claude-sonnet-4
```

---

## Plugin System

### Plugin Discovery

```
Scan order:
1. Built-in plugins:  src/factory/cli/plugins/builtin/
2. Project plugins:   raceos-factory/plugins/
3. User plugins:      ~/.raceos/plugins/
4. Installed (pip):   entry_points["raceos.plugins"]
```

### Extension API (Plugin Base Class)

```python
from factory.cli.plugins.base import RaceOSPlugin, hook


class MyPlugin(RaceOSPlugin):
    """Plugin metadata."""
    name = "my-plugin"
    version = "1.0.0"
    description = "Adds custom command"

    def register(self, app):
        """Called on plugin load. Register commands/hooks."""
        app.add_command("my-command", self.handle)

    @hook("pre_execute")
    def before_task(self, state):
        """Hook: called before any task execution."""
        print("About to execute!")

    @hook("post_execute")
    def after_task(self, state, result):
        """Hook: called after task execution."""
        if result.status == "success":
            self.notify("Task done!")

    def handle(self, args):
        """Custom command handler."""
        ...
```

### Hook Points

```
pre_startup       → Before config load
post_startup      → After ready, before prompt
pre_command       → Before any command executes
post_command      → After any command completes
pre_execute       → Before factory task dispatched
post_execute      → After factory task result received
pre_approve       → Before human approval shown
post_approve      → After human approves/rejects
on_error          → When any error occurs
on_stream_token   → Each streaming token received
on_shutdown       → Before CLI exits
```

### Plugin Configuration

```yaml
# ~/.raceos/plugins.yaml
plugins:
  enabled:
    - "slack-notify"      # Post to Slack on task completion
    - "github-pr"         # Auto-create PR after success
    - "cost-alert"        # Alert when budget threshold hit

  disabled:
    - "telemetry-upload"  # Opt-out of usage telemetry

  config:
    slack-notify:
      webhook_url_env: "SLACK_WEBHOOK_URL"
      channel: "#raceos-factory"
      notify_on: ["success", "failure"]

    github-pr:
      auto_create: true
      reviewers: ["mirza"]
      draft: false
```

---

## Command Reference

| Command | Purpose | Domain Agent |
|---|---|---|
| `raceos` | Interactive shell | — |
| `raceos chat` | General AI conversation | Orchestrator |
| `raceos feature "..."` | Implement a feature (full pipeline) | Engineer |
| `raceos review` | Review code changes | Review Agent |
| `raceos hardware "..."` | Hardware design questions/tasks | Hardware Engineer |
| `raceos firmware "..."` | Firmware implementation/debug | Engineer (firmware) |
| `raceos mobile "..."` | Mobile implementation | Engineer (mobile) |
| `raceos docs "..."` | Documentation generation | Gemini (docs) |
| `raceos research "..."` | Market/user research | Research Analyst |
| `raceos telemetry "..."` | Data pipeline design | Data/Telemetry Agent |
| `raceos doctor` | System health check | — (local) |
| `raceos update` | Update factory + dependencies | — (local) |
| `raceos logs` | View logs | — (local) |
| `raceos status` | Task status + budget | — (local) |
| `raceos config` | Configuration management | — (local) |
| `raceos install` | Install MCP servers + tools | — (local) |
| `raceos repair` | Repair broken state/config | — (local) |
| `raceos migrate` | Migrate config between versions | — (local) |
| `raceos backup` | Backup factory state | — (local) |
| `raceos restore` | Restore from backup | — (local) |

### Command Categories

```
AI-Powered (call LLMs):
  chat, feature, review, hardware, firmware, mobile, docs, research, telemetry

Local Operations (no LLM):
  doctor, update, logs, status, config, install, repair, migrate, backup, restore
```

---

## `raceos doctor` Output

```
$ raceos doctor

╔══════════════════════════════════════════════════════════╗
║  RaceOS Factory — System Health Check                    ║
╚══════════════════════════════════════════════════════════╝

  Runtime:
    ✅ Python 3.12.4
    ✅ uv 0.5.1
    ✅ Node.js 20.11.0
    ✅ npx available

  Configuration:
    ✅ config/factory.yaml — valid
    ✅ config/router.yaml — valid (14 routing rules)
    ✅ config/opencode.json — valid
    ✅ .env — OPENROUTER_API_KEY set

  Project Brain:
    ✅ ../.raceos/ — accessible (43 documents)
    ✅ ../openspec/specs/ — 6 specs found
    ✅ ../adr/ — 25 ADRs found

  Tools:
    ✅ opencode — v1.2.0
    ✅ codebase-memory-mcp — available
    ⚠️ platformio — not installed (firmware builds will fail)

  Budget:
    ✅ Daily: $3.42 / $50.00 (6.8% used)
    ✅ No degradation active

  Pending:
    ℹ️ 0 tasks awaiting approval
    ℹ️ 0 incomplete checkpoints

  ──────────────────────────────────────────────────────
  Status: HEALTHY (1 warning)
  Fix: pip install platformio
```

---

## Streaming UI Implementation Notes

### Technology

```
rich          → Panels, tables, progress bars, spinners, markdown
prompt_toolkit→ Interactive shell (readline, completion, history)
asyncio       → Non-blocking streaming + concurrent status updates
```

### Streaming Architecture

```
LLM API (SSE/streaming) 
    ↓ token
OutputBuffer (accumulates)
    ↓ render
rich.Live (updates terminal in-place)
    ↓ final
Console.print (final static output)
```

### Progress Architecture

```
FactoryState.history (list of completed nodes)
    ↓ observe
ProgressTracker (maps nodes to phases)
    ↓ render
rich.Progress (multi-bar with phases)
    ↓ update
Terminal (live refresh every 100ms)
```

---

*End of CLI Design*
