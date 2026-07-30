# OpenCode Configuration Reference

> Every option in `config/opencode.json` explained.

---

## `model` — LLM Model Selection

| Key | Value | Why |
|---|---|---|
| `default` | `anthropic/claude-sonnet-4.6` | Primary model for code generation. Best balance of quality and speed. |
| `fast` | `anthropic/claude-sonnet-4` | Used for simple tasks (typo fixes, comments). Cheaper, faster. |
| `reasoning` | `anthropic/claude-opus-4` | Used for complex tasks after retry escalation. Most capable. |

Model is selected by 9Router before OpenCode is invoked. OpenCode receives the chosen model.

---

## `provider` — LLM API Gateway

| Key | Value | Why |
|---|---|---|
| `name` | `9router` | Gateway that provides access to all models via single API. |
| `baseUrl` | `https://9router.ai/api/v1` | OpenAI-compatible endpoint. |
| `apiKeyEnv` | `NINE_ROUTER_API_KEY` | Environment variable name (never hardcode keys). |
| `headers.X-Title` | `RaceOS Factory` | Identifies our app in 9Router dashboard. |
| `headers.HTTP-Referer` | `https://github.com/raceos` | Required by 9Router for attribution. |

---

## `session` — Execution Session Defaults

| Key | Value | Why |
|---|---|---|
| `nonInteractive` | `true` | Factory runs headless. No human at terminal during execution. |
| `maxTokens` | `8192` | Default output limit per LLM call. Override per-task via 9Router. |
| `temperature` | `0.1` | Low temperature = deterministic code generation. |
| `timeout` | `300` | Kill session after 5 minutes. Prevents runaway execution. |
| `outputFormat` | `json` | Structured output for programmatic parsing by factory. |

---

## `tools.file` — File System Operations

| Key | Value | Why |
|---|---|---|
| `enabled` | `true` | OpenCode needs to read/write project files. |
| `rootDir` | `..` | Points to RaceOS repo root (factory is a subdirectory). |
| `allowedPaths` | `firmware/**`, `mobile/**`, etc. | Whitelist of directories OpenCode can touch. |
| `blockedPaths` | `.raceos/**`, `.ai/**`, `.env` | Brain is immutable. Secrets are off-limits. Factory config is protected. |
| `operations` | `read`, `write`, `create`, `list` | All file operations needed for implementation. |

**Security principle**: Allowlist + blocklist. If a path isn't explicitly allowed AND isn't blocked, behavior depends on whether it's under `rootDir`.

---

## `tools.terminal` — Command Execution

| Key | Value | Why |
|---|---|---|
| `enabled` | `true` | Needed for build (`pio build`) and test (`pio test`) execution. |
| `shell` | `/bin/bash` | Standard shell. Consistent across macOS/Linux. |
| `workingDir` | `..` | Commands run from RaceOS repo root. |
| `timeout` | `120` | Kill command after 2 minutes. Builds should be fast. |
| `allowedCommands` | `pio *`, `pytest *`, `npm *`, etc. | Whitelist of safe commands. Glob matching. |
| `blockedCommands` | `rm -rf *`, `sudo *`, `curl *`, etc. | Dangerous commands that could destroy data or exfiltrate. |
| `maxOutputLines` | `500` | Truncate long output to prevent context bloat. |

**Security principle**: Commands must match allowlist. Anything not matching is rejected before execution.

---

## `tools.git` — Version Control

| Key | Value | Why |
|---|---|---|
| `enabled` | `true` | OpenCode creates branches and commits for its changes. |
| `workingDir` | `..` | Git operations on RaceOS repo. |
| `operations` | `status`, `diff`, `log`, `branch`, `checkout`, `add`, `commit`, `stash` | Safe git operations. |
| `blockedOperations` | `push --force`, `reset --hard`, `clean -f`, `branch -D` | Destructive operations require human. |
| `branchPrefix` | `factory/` | All factory branches start with `factory/` for identification. |
| `requireBranch` | `true` | OpenCode must be on a branch (not detached HEAD). |
| `blockMainCommit` | `true` | NEVER commit directly to `main`. Always branch first. |
| `commitMessagePrefix` | `[factory]` | All factory commits are tagged for filtering. |
| `maxDiffLines` | `1000` | Limit diff output to prevent context overflow. |

**Safety principle**: OpenCode can create branches and commit, but cannot push or destroy history. Human reviews and pushes.

---

## `tools.patch` — Unified Diff Patching

| Key | Value | Why |
|---|---|---|
| `enabled` | `true` | Patch-based editing is precise and auditable. |
| `rootDir` | `..` | Patches applied relative to repo root. |
| `operations` | `apply`, `create`, `preview` | Can apply patches, create them, or preview what would change. |
| `maxPatchSize` | `50000` | Reject patches larger than 50KB (likely wrong). |
| `validateBeforeApply` | `true` | Check patch applies cleanly before modifying files. |
| `backupBeforeApply` | `true` | Create backup before applying (recoverable). |
| `allowedExtensions` | `.cpp`, `.h`, `.py`, `.ts`, etc. | Only patch known code/config files. No binaries. |

**Why patches**: Patches are atomic, reviewable, and reversible. Unlike full file rewrites, they show exactly what changed. Better for auditing.

---

## `context` — Context Window Management

| Key | Value | Why |
|---|---|---|
| `systemPromptFile` | `null` | System prompt is injected by factory (not from file). |
| `maxContextTokens` | `100000` | Hard limit on total context sent to model. |
| `includeFileTree` | `true` | Send directory tree to help model navigate project. |
| `fileTreeDepth` | `3` | How deep to show tree (avoid overwhelming). |
| `fileTreeExclude` | `node_modules`, `.git`, etc. | Skip irrelevant directories in tree. |

---

## `safety` — Guardrails

| Key | Value | Why |
|---|---|---|
| `confirmDestructive` | `true` | Pause before destructive operations (even in non-interactive). |
| `maxFilesPerSession` | `20` | Prevent runaway sessions from modifying entire codebase. |
| `maxLinesPerFile` | `5000` | Reject edits to files larger than 5K lines (likely wrong target). |
| `dryRunDefault` | `false` | Execute for real by default (dry-run is opt-in per task). |
| `auditLog` | `true` | Log every tool invocation for post-mortem debugging. |
| `auditLogPath` | `./data/opencode-audit.jsonl` | JSON Lines format for easy parsing. |

---

## `retry` — Failure Recovery

| Key | Value | Why |
|---|---|---|
| `maxAttempts` | `3` | Try up to 3 times before giving up. |
| `backoffMs` | `[1000, 2000, 4000]` | Wait 1s, 2s, 4s between retries. Exponential. |
| `retryOnBuildFail` | `true` | If build fails, feed errors to model and try again. |
| `retryOnTestFail` | `true` | If tests fail, feed test output and try again. |
| `escalateModel` | `true` | On 2nd failure, upgrade to `reasoning` model. |

**Escalation path**: `fast` → `default` → `reasoning` → human escalation.

