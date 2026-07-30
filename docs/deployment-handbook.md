# RaceOS AI Factory — Production Deployment Handbook

> **Purpose:** Complete operational guide for deploying, maintaining, and scaling the RaceOS AI Factory as a public open-source project.
> **Audience:** DevOps engineers, release managers, project maintainers.
> **Status:** Ready for execution.

---

## Table of Contents

1. [Source Control](#1-source-control)
2. [Package Distribution](#2-package-distribution)
3. [CI/CD](#3-cicd)
4. [Secrets Management](#4-secrets-management)
5. [Domain](#5-domain)
6. [Documentation](#6-documentation)
7. [Open Source](#7-open-source)
8. [Monitoring](#8-monitoring)
9. [Versioning](#9-versioning)
10. [Security](#10-security)
11. [Release Checklist](#11-release-checklist)
12. [Bootstrap](#12-bootstrap)
13. [Disaster Recovery](#13-disaster-recovery)
14. [Future Scaling](#14-future-scaling)

---

## 1. Source Control

### GitHub Repository

| Setting | Value | Why |
|---|---|---|
| Repository | `raceos/raceos-factory` | Primary source of truth |
| Visibility | Public | Open-source project |
| Default branch | `main` | Industry standard |
| Purpose | Source control, CI/CD, releases, issues, discussions |
| Mandatory | YES |
| Cost | Free (public repo) |

### Branch Protection Rules (main)

```
Settings → Branches → Add rule: main

✅ Require pull request before merging
  ✅ Require 1 approval
  ✅ Dismiss stale reviews on new pushes
✅ Require status checks to pass
  ✅ Required: lint, test (3.11, 3.12, 3.13), build
✅ Require conversation resolution
✅ Require signed commits (optional, recommended)
✅ Do not allow bypassing the above settings
❌ Allow force pushes (never)
❌ Allow deletions (never)
```

### CODEOWNERS

```
# .github/CODEOWNERS
* @raceos/core-maintainers
/src/factory/orchestrator/ @raceos/architecture
/src/factory/gateway/ @raceos/infrastructure
/src/factory/executor/ @raceos/infrastructure
/config/ @raceos/core-maintainers
/.github/ @raceos/devops
```

### Issue Templates

Create `.github/ISSUE_TEMPLATE/`:

| Template | Purpose |
|---|---|
| `bug_report.md` | Bug reports with repro steps |
| `feature_request.md` | Feature proposals |
| `question.md` | Usage questions |
| `config.yml` | Template chooser configuration |

### PR Template

`.github/pull_request_template.md`:
- Summary of changes
- Type (feature/fix/docs/refactor)
- Related issue
- Testing performed
- Checklist (lint, tests, docs)

### Labels

| Label | Color | Use |
|---|---|---|
| `bug` | red | Bug reports |
| `feature` | green | Feature requests |
| `docs` | blue | Documentation |
| `good first issue` | purple | Onboarding |
| `breaking` | orange | Breaking changes |
| `security` | dark red | Security issues |
| `P1-critical` | red | Must fix immediately |
| `P2-high` | orange | Fix this sprint |
| `P3-medium` | yellow | Fix eventually |
| `agent:orchestrator` | teal | Affects orchestrator |
| `agent:engineer` | teal | Affects engineer |
| `component:cli` | cyan | Affects CLI |
| `component:router` | cyan | Affects router |

### Milestones

| Milestone | Target |
|---|---|
| v1.0.0 — Public Release | Week 1 |
| v1.1.0 — Team Features | Week 4 |
| v1.2.0 — CI Integration | Week 8 |
| v2.0.0 — Multi-user | Q3 |

---

## 2. Package Distribution

### PyPI (Primary)

| Setting | Value |
|---|---|
| Package name | `raceos-factory` |
| Purpose | `pip install raceos-factory` / `pipx install raceos-factory` |
| Mandatory | YES |
| Cost | Free |
| Owner | PyPI account `raceos` |
| URL | https://pypi.org/project/raceos-factory/ |

**Setup steps:**
1. Create account at https://pypi.org/account/register/
2. Enable 2FA (mandatory for PyPI)
3. Create API token: Account Settings → API Tokens → "raceos-factory (upload)"
4. Scope token to `raceos-factory` project only
5. Add to GitHub: Settings → Secrets → `PYPI_API_TOKEN`
6. Verify: `pip install raceos-factory && raceos --version`

### TestPyPI (Pre-release testing)

| Setting | Value |
|---|---|
| Purpose | Test package before real release |
| Mandatory | Recommended |
| Cost | Free |
| URL | https://test.pypi.org/project/raceos-factory/ |

**Setup:** Same as PyPI but at test.pypi.org. Token stored as `TEST_PYPI_TOKEN`.

### GitHub Container Registry (Docker)

| Setting | Value |
|---|---|
| Image | `ghcr.io/raceos/raceos-factory` |
| Purpose | Docker distribution |
| Mandatory | Yes |
| Cost | Free (public images) |
| Auth | `GITHUB_TOKEN` (automatic in Actions) |

**Verification:** `docker pull ghcr.io/raceos/raceos-factory:1.0.0 && docker run --rm ghcr.io/raceos/raceos-factory --version`

### Homebrew Tap

| Setting | Value |
|---|---|
| Repository | `raceos/homebrew-tap` |
| Purpose | `brew install raceos` |
| Mandatory | No (convenience for macOS) |
| Cost | Free |

**Setup:**
1. Create repo `raceos/homebrew-tap`
2. Add formula from `Formula/raceos.rb`
3. Create Personal Access Token with repo scope → `HOMEBREW_TAP_TOKEN`
4. Release workflow auto-updates formula on new version

**Verification:** `brew tap raceos/tap && brew install raceos && raceos --version`

---

## 3. CI/CD

### GitHub Actions Pipelines

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yaml` | push to main, PRs | lint → test (matrix) → build → docker |
| `release.yaml` | tag `v*` pushed | publish-pypi → publish-docker → github-release → homebrew-notify |
| `security.yaml` | weekly schedule | dependabot, CodeQL, license scan |
| `docs.yaml` | push to main (docs/) | Build + deploy docs site |

### Required Status Checks

| Check | Must Pass | Why |
|---|---|---|
| `lint` | YES | Code style enforcement |
| `test (3.11)` | YES | Minimum supported Python |
| `test (3.12)` | YES | Primary target |
| `test (3.13)` | YES | Forward compatibility |
| `build` | YES | Package builds correctly |

### Scheduled Jobs

| Job | Schedule | Purpose |
|---|---|---|
| Dependency audit | Weekly (Mon 9am) | Check for vulnerabilities |
| Integration test | Daily (2am) | Verify E2E with real API (budget: $1/day) |
| Stale issue cleanup | Weekly | Close inactive issues after 30 days |

---

## 4. Secrets Management

### Complete Secrets Inventory

| Secret | Stored In | Purpose | Required |
|---|---|---|---|
| `OPENROUTER_API_KEY` | GitHub Secrets (env: `integration-test`) | E2E tests + scheduled integration | Yes |
| `PYPI_API_TOKEN` | GitHub Secrets (env: `release`) | Publish to PyPI | Yes |
| `TEST_PYPI_TOKEN` | GitHub Secrets | Publish to TestPyPI | Recommended |
| `HOMEBREW_TAP_TOKEN` | GitHub Secrets | Update Homebrew formula | If Homebrew supported |
| `CODECOV_TOKEN` | GitHub Secrets | Upload coverage reports | Recommended |
| `GITHUB_TOKEN` | Automatic (GitHub provides) | GHCR push, release creation | Automatic |

### Secret Rotation Policy

| Secret | Rotation | Process |
|---|---|---|
| OPENROUTER_API_KEY | Every 90 days | Regenerate at openrouter.ai, update GitHub |
| PYPI_API_TOKEN | Every 6 months | Regenerate, scope to project |
| HOMEBREW_TAP_TOKEN | Never expires (fine-grained PAT) | Revoke if compromised |

### Environment Protection

```
GitHub Settings → Environments:

"release" environment:
  ✅ Required reviewers: @raceos/core-maintainers
  ✅ Wait timer: 5 minutes (cancel window)
  ✅ Deployment branches: tags only (v*)
  Secrets: PYPI_API_TOKEN

"integration-test" environment:
  ✅ Deployment branches: main only
  Secrets: OPENROUTER_API_KEY (budget-limited key, $1/day max)
```

---

## 5. Domain

### Recommendation: `raceos.dev`

| Domain | Available | Recommendation | Why |
|---|---|---|---|
| `raceos.dev` | Check | **PRIMARY** | `.dev` signals developer tool. Enforces HTTPS. Modern. |
| `raceos.ai` | Check | REDIRECT | AI association, but `.ai` is expensive ($50+/year) |
| `raceos.io` | Check | SKIP | Generic, no strong signal |

**Why `.dev`:**
1. HSTS preloaded (forced HTTPS — security)
2. Signals "this is a developer tool" (audience match)
3. Google-managed TLD (reliable)
4. $12-15/year (affordable)
5. Short, memorable: `docs.raceos.dev`, `get.raceos.dev`

### DNS Structure

| Subdomain | Points To | Purpose |
|---|---|---|
| `raceos.dev` | GitHub Pages or landing page | Project homepage |
| `docs.raceos.dev` | GitHub Pages (docs/) | Documentation site |
| `get.raceos.dev` | Raw script hosted on GH Pages | Bootstrap installer script |
| `api.raceos.dev` | (future) API endpoint | When SaaS mode added |

### Setup Steps

1. Register `raceos.dev` at Google Domains or Cloudflare
2. Configure DNS: CNAME `docs` → `raceos.github.io`
3. Enable GitHub Pages with custom domain
4. Add `CNAME` file to docs deployment

**Cost:** ~$12-15/year
**Mandatory:** No (GitHub URLs work fine for v1.0). Recommended for professional presence.


---

## 6. Documentation

### Documentation Sites

| Doc | Location | Audience |
|---|---|---|
| Quick Start | README.md + docs/getting-started.md | New users |
| Architecture | docs/architecture/ | Contributors |
| CLI Reference | docs/cli-design.md | Daily users |
| Configuration | config/CONFIG_INDEX.md | Operators |
| Contribution | CONTRIBUTING.md | Contributors |
| Release Guide | docs/release-guide.md | Maintainers |
| Migration Guide | (per-version) | Upgraders |
| Troubleshooting | docs/troubleshooting.md | Users with issues |
| Security Policy | SECURITY.md | Security researchers |
| Code of Conduct | CODE_OF_CONDUCT.md | Community |

### Documentation Deployment

Host on GitHub Pages from `docs/` directory. Auto-deploy via `docs.yaml` workflow on push to main.

---

## 7. Open Source

### License: MIT

**Chosen: MIT License** (already in LICENSE file)

| License | Pros | Cons | Verdict |
|---|---|---|---|
| MIT | Maximum adoption, minimal friction, enterprise-friendly | No copyleft protection | **CHOSEN** |
| Apache 2.0 | Patent protection, enterprise-friendly | More complex, patent clause scares some | Alternative |
| GPL-3.0 | Ensures derivatives stay open | Blocks enterprise adoption, viral | Rejected |
| AGPL-3.0 | Covers SaaS use | Maximum restriction, kills adoption | Rejected |

**Why MIT:** RaceOS is an embedded motorsport platform. Maximum adoption matters more than copyleft protection. Enterprise teams (racing teams) need to use this without legal friction. MIT is the standard for developer tools (same as React, Vue, Next.js).

### CONTRIBUTING.md

```markdown
# Contributing to RaceOS AI Factory

## Quick Start

1. Fork + clone: `git clone https://github.com/YOUR_USER/raceos-factory.git`
2. Install: `cd raceos-factory && uv sync --all-extras`
3. Test: `uv run pytest tests/ -v`
4. Branch: `git checkout -b feature/my-change`
5. Code + test + commit
6. PR: `gh pr create`

## Development Setup

- Python 3.11+ required
- uv (package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Run tests: `make test`
- Format: `make fmt`
- Lint: `make lint`

## What to Contribute

- 🐛 Bug fixes (always welcome)
- 📝 Documentation improvements
- 🧪 Test coverage improvements
- 🔌 New domain adapters
- 🤖 Agent improvements

## Commit Convention

Format: `type(scope): description`

Types: feat, fix, docs, refactor, test, chore
Scopes: cli, orchestrator, router, gateway, executor, memory, spec_engine

Examples:
- `feat(cli): add raceos chat command`
- `fix(router): correct budget threshold calculation`
- `docs(architecture): update sequence diagram`

## PR Requirements

- [ ] Tests pass (`make test`)
- [ ] Lint passes (`make lint`)
- [ ] No TODOs in new code
- [ ] Documentation updated (if behavior changes)
- [ ] Commit messages follow convention

## Architecture Rules

- No circular dependencies
- Single responsibility per module
- Config over code (deploy-time decisions in YAML)
- Dependency injection for testability
- Graceful degradation (never crash on optional failure)

## Code of Conduct

See CODE_OF_CONDUCT.md. Be respectful, constructive, and inclusive.
```

### SECURITY.md

```markdown
# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.x | ✅ Security updates |
| < 1.0 | ❌ No support |

## Reporting a Vulnerability

**DO NOT open a public issue for security vulnerabilities.**

Email: security@raceos.dev
PGP Key: (publish key on keyserver)

We will:
1. Acknowledge within 48 hours
2. Provide an initial assessment within 7 days
3. Release a fix within 30 days (critical: 7 days)

## Scope

In scope:
- API key exposure
- Command injection via CLI
- Path traversal in BrainReader/file operations
- Privilege escalation in MCP tools
- Supply chain vulnerabilities in dependencies

Out of scope:
- Vulnerabilities in LLM providers (OpenRouter, Anthropic, OpenAI)
- Social engineering attacks
- Physical access attacks
```

### CODE_OF_CONDUCT.md

Use [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) — industry standard for open-source projects.

---

## 8. Monitoring

### Release Metrics

| Metric | Source | Dashboard |
|---|---|---|
| PyPI downloads | pypistats.org | Badge in README |
| Docker pulls | ghcr.io | GitHub Packages page |
| GitHub stars | GitHub API | Repository page |
| Open issues | GitHub | Issues tab |
| PR merge time | GitHub | Insights → Pulse |
| CI pass rate | GitHub Actions | Actions tab |
| Coverage % | Codecov | Badge in README |

### CLI Analytics (Privacy-First)

**Approach:** Opt-in only. No tracking by default.

If user opts in (`raceos config set telemetry.enabled true`):
- Report: command used, duration, success/failure, Python version, OS
- DO NOT report: task descriptions, file contents, API keys, error details
- Endpoint: `https://telemetry.raceos.dev/v1/event` (future)
- Storage: aggregated only, no PII, 30-day retention

**For v1.0:** No telemetry. Use PyPI download stats + GitHub stars as proxy.

### Update Check

On CLI startup (non-blocking, cached 24h):
- GET `https://pypi.org/pypi/raceos-factory/json` → check `info.version`
- If newer available: show one-line notice (suppressible via config)
- Never auto-install

### Error Reporting

**For v1.0:** Structured logs only (`data/logs/`).
**Future (v1.2+):** Opt-in Sentry integration for crash reports.

---

## 9. Versioning

### Semantic Versioning (SemVer)

```
MAJOR.MINOR.PATCH

1.0.0 → 1.0.1 (bug fix, no behavior change)
1.0.1 → 1.1.0 (new feature, backward compatible)
1.1.0 → 2.0.0 (breaking change: config format, removed command, API change)
```

### What Constitutes Breaking

| Change | Breaking? |
|---|---|
| New CLI command | No (additive) |
| New config field with default | No (backward compatible) |
| Remove CLI command | YES |
| Rename config field | YES |
| Change default model routing | No (behavior, not API) |
| Change state schema (TypedDict) | YES (if used programmatically) |
| Change node output shape | No (internal, not public API) |

### Release Branch Strategy

```
main (development) ← PRs merge here
  │
  ├── tag v1.0.0 (release)
  ├── tag v1.0.1 (hotfix)
  ├── tag v1.1.0 (feature release)
  │
  └── release/1.x (if long-term support needed)
```

**No release branches for v1.x.** Tags on main are sufficient.
Release branches only needed when v2.x development starts while v1.x still gets fixes.

### Hotfix Strategy

```
1. Critical bug found in v1.2.0
2. Create branch: hotfix/critical-fix from tag v1.2.0
3. Fix, test, merge to main
4. Tag: v1.2.1
5. Release workflow publishes automatically
```

### Support Policy

| Version | Support | Duration |
|---|---|---|
| Latest minor (e.g., 1.3.x) | Full (features + fixes + security) | Until next minor |
| Previous minor (e.g., 1.2.x) | Security fixes only | 3 months after next minor |
| Major-1 (e.g., 0.x) | No support | — |


---

## 10. Security

### Supply Chain Security

| Tool | Purpose | Setup |
|---|---|---|
| **Dependabot** | Auto-PR for vulnerable deps | `.github/dependabot.yml` |
| **Secret Scanning** | Detect leaked secrets in commits | Settings → Security → Enable |
| **CodeQL** | Static analysis for vulnerabilities | `.github/workflows/security.yaml` |
| **SBOM** | Software Bill of Materials | Generate via `syft` in release pipeline |
| **License scan** | Ensure dep licenses compatible with MIT | `pip-licenses` in CI |
| **Signed commits** | Verify commit authenticity | Recommend GPG signing for maintainers |

### Dependabot Configuration

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    labels: ["dependencies"]
    commit-message:
      prefix: "chore(deps):"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels: ["ci"]
```

### Pin Actions to SHA

All GitHub Actions in workflows should use commit SHA, not tags:
```yaml
# Instead of: uses: actions/checkout@v4
# Use: uses: actions/checkout@b4ffde65f...
```

This prevents supply-chain attacks via tag reassignment.

---

## 11. Release Checklist

### Pre-Release (before tagging)

```
□ All tests pass on main (CI green)
□ CHANGELOG.md updated with new version entry
□ Version bumped in src/factory/__init__.py
□ No TODO/FIXME in changed files
□ Documentation updated for new features
□ Breaking changes documented in CHANGELOG
□ Migration guide written (if breaking)
□ Security audit: no new vulnerabilities in deps
□ Coverage ≥ 60% (target: 80%)
□ Manual smoke test: raceos doctor passes
□ Manual smoke test: raceos feature works (with API key)
```

### Release (tag + publish)

```
□ Create tag: git tag -s v1.X.Y -m "Release v1.X.Y"
□ Push tag: git push origin v1.X.Y
□ Watch release.yaml pipeline:
  □ PyPI publish succeeds
  □ Docker push succeeds
  □ GitHub Release created with changelog
  □ Homebrew tap updated (if applicable)
□ Verify install: pipx install raceos-factory==1.X.Y
□ Verify CLI: raceos --version shows new version
□ Verify Docker: docker run ghcr.io/raceos/raceos-factory:1.X.Y --version
```

### Post-Release

```
□ Announce: GitHub Discussions / social media
□ Monitor: PyPI downloads for first 24h
□ Monitor: GitHub Issues for regression reports
□ Update roadmap milestone (close completed)
□ Begin next version development on main
```

---

## 12. Bootstrap (New Developer, 15 Minutes)

### Minute 0-2: Prerequisites

```bash
# Verify Python (macOS/Linux usually has it)
python3 --version  # Need ≥ 3.11

# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Minute 2-5: Clone + Setup

```bash
git clone https://github.com/raceos/raceos-factory.git
cd raceos-factory
uv sync --all-extras
```

### Minute 5-7: Verify

```bash
make test          # All unit tests pass
make lint          # Code style clean
uv run raceos --version   # CLI works
uv run raceos doctor      # Health check
```

### Minute 7-10: Configuration

```bash
cp .env.example .env
# Edit .env: add OPENROUTER_API_KEY (get from https://openrouter.ai/keys)
```

### Minute 10-13: First Task

```bash
# Test the factory (requires API key)
uv run raceos firmware "explain what layered architecture means"
```

### Minute 13-15: Explore

```bash
uv run raceos              # Enter interactive shell
# Type: /help
# Type: /status
# Type: /budget
# Type: how to wire display to stm32
# Type: /quit
```

### Verification

Developer is productive when:
- [ ] `make test` passes (can verify changes)
- [ ] `raceos doctor` shows ≥8 checks green
- [ ] `raceos firmware "explain X"` returns an answer (API connected)
- [ ] Interactive shell starts and responds to /help

---

## 13. Disaster Recovery

### What to Back Up

| Data | Location | Frequency | Method |
|---|---|---|---|
| Source code | GitHub | Every commit | Git (automatic) |
| Config | `config/` | Every change | Git (committed) |
| Secrets | GitHub Secrets | On rotation | Manual document (encrypted) |
| PyPI releases | pypi.org | Every release | PyPI retains all versions |
| Docker images | ghcr.io | Every release | GHCR retains all tags |
| User data | `data/` (local) | User responsibility | `raceos backup` command |

### Recovery Scenarios

| Scenario | Recovery |
|---|---|
| GitHub repo deleted | Restore from maintainer local clone (all have full history) |
| PyPI token compromised | Revoke → regenerate → update GitHub secret → no published damage (PyPI is immutable) |
| GHCR image compromised | Delete tag → re-push from source → users re-pull |
| Homebrew formula broken | Revert PR in homebrew-tap repo |
| API key leaked | Revoke at openrouter.ai → regenerate → update .env |
| User loses local data | `raceos restore` from backup (if they ran `raceos backup`) |
| CI pipeline broken | Revert workflow file to last known good (git history) |

### Recovery Procedures

**PyPI emergency (malicious release):**
1. Contact PyPI support immediately (security@pypi.org)
2. Yank the affected version: `pip install twine && twine yank raceos-factory==X.Y.Z`
3. Publish fixed version with bumped patch number
4. Announce on GitHub Discussions + README banner

**GitHub compromise:**
1. Enable branch protection (prevents force-push)
2. Require signed commits (prevents impersonation)
3. Enable audit log (tracks admin actions)
4. 2FA mandatory for all org members

---

## 14. Future Scaling

### 10 Developers

| Change | Why | Effort |
|---|---|---|
| Branch protection (1 approval) | Prevent accidental main breaks | 5 min (already configured) |
| CODEOWNERS | Route reviews to domain experts | 10 min |
| Issue templates | Standardize bug/feature reports | 30 min |
| Dev container (`.devcontainer/`) | Consistent dev environment | 2 hours |
| Shared test API key (budget-limited) | Avoid individual key management | 30 min |

### 100 Developers

| Change | Why | Effort |
|---|---|---|
| Monorepo tooling (Turborepo/Nx) | If multi-package structure | 1 week |
| Branch protection (2 approvals) | Higher quality bar | 5 min |
| CI caching (aggressive) | Reduce CI cost/time | 2 hours |
| Bot accounts for automation | Separate from human accounts | 1 hour |
| Release committee (3 approvers) | Release governance | Process change |
| SLA for PR review (48h) | Prevent contributor frustration | Process change |
| Automated changelog (from commits) | Scale release notes | 2 hours |
| Feature flags | Gradual rollout | 1 day |

### 1000 Community Contributors

| Change | Why | Effort |
|---|---|---|
| Contributor License Agreement (CLA) | Legal protection | Setup CLA bot |
| Triage team (volunteers) | Scale issue management | Community building |
| Good First Issues program | Onboard new contributors | Curation |
| Monthly community calls | Alignment + engagement | Recurring |
| GitHub Sponsors | Fund maintainer time | Setup |
| Multiple maintainer timezones | 24h coverage | Recruitment |
| Governance document | Decision-making transparency | 1 day |
| RFC process | Major changes require community input | Process |
| Plugin marketplace | Community extensions | Architecture (v3.0) |
| Separate repos per component | If mono-repo becomes unwieldy | Migration |

---

## External Services Summary

| Service | Purpose | Cost | Required |
|---|---|---|---|
| GitHub | Source, CI, Releases, Issues | Free (public) | YES |
| PyPI | Python package distribution | Free | YES |
| GitHub Container Registry | Docker images | Free (public) | YES |
| Codecov | Coverage tracking | Free (open source) | Recommended |
| raceos.dev domain | Professional presence | $12-15/year | Recommended |
| OpenRouter | LLM API (integration tests) | $1/day budget | For CI only |
| Homebrew tap | macOS distribution | Free | Optional |
| Sentry | Error tracking (future) | Free tier | Optional (v1.2+) |

### Total Mandatory Cost: $0/month (all free tier)
### Total Recommended Cost: ~$15/year (domain only)

---

## Final Operational Readiness Checklist

```
Before public announcement:

□ GitHub repo public with README + LICENSE
□ Branch protection enabled on main
□ CODEOWNERS file committed
□ Issue + PR templates committed
□ CI pipeline green (all checks pass)
□ PyPI package published (v1.0.0)
□ Docker image pushed (ghcr.io)
□ CHANGELOG.md reflects v1.0.0
□ CONTRIBUTING.md committed
□ SECURITY.md committed
□ CODE_OF_CONDUCT.md committed
□ Dependabot configured
□ Secret scanning enabled
□ All secrets in GitHub Environments (not plain settings)
□ raceos doctor passes on fresh machine
□ pipx install raceos-factory works
□ Documentation accessible (README or docs site)
□ First GitHub Release created with changelog
□ Announcement prepared (GitHub Discussions post)
```

---

*End of Deployment Handbook*
