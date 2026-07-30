# Deployment Audit Report

> **Auditor:** Principal DevOps
> **Date:** 2026-07-30
> **Scope:** Deployment plan for public v1.0.0 release
> **Target:** Zero operational blockers before first public release

---

## Executive Summary

The deployment plan is **85% complete**. 7 blockers remain before public release can proceed safely. All are operational/account setup tasks — no architecture changes needed.

---

## Findings

### 1. Missing External Services

| # | Service | Purpose | Status | Severity |
|---|---|---|---|---|
| 1 | PyPI account `raceos` | Package publishing | ❌ Not created | **CRITICAL** |
| 2 | GitHub org `raceos` | Source control home | ❌ Not created | **CRITICAL** |
| 3 | Domain `raceos.dev` | Professional URL, docs, bootstrap script | ❌ Not registered | MEDIUM |
| 4 | Codecov account | Coverage tracking + badge | ❌ Not connected | LOW |
| 5 | GitHub Discussions | Community Q&A | ❌ Not enabled | LOW |

### 2. Missing Accounts

| # | Account | Platform | Required For | Severity |
|---|---|---|---|---|
| 6 | PyPI user (2FA enabled) | pypi.org | Publishing releases | **CRITICAL** |
| 7 | TestPyPI user | test.pypi.org | Pre-release validation | HIGH |
| 8 | npm account (if publishing opencode) | npmjs.com | Not needed (using npx) | N/A |
| 9 | Docker Hub (optional) | hub.docker.com | Mirror GHCR (redundancy) | LOW |

### 3. Missing Secrets

| # | Secret | Where Needed | Current Status | Severity |
|---|---|---|---|---|
| 10 | `PYPI_API_TOKEN` | release.yaml | ❌ Not generated | **CRITICAL** |
| 11 | `HOMEBREW_TAP_TOKEN` | release.yaml | ❌ Not generated | MEDIUM |
| 12 | `CODECOV_TOKEN` | ci.yaml | ❌ Not generated | LOW |
| 13 | `NINE_ROUTER_API_KEY` (CI) | Integration tests | ❌ Not configured in GitHub | HIGH |

### 4. Missing Automations

| # | Automation | Purpose | Status | Severity |
|---|---|---|---|---|
| 14 | Stale issue bot | Close inactive issues after 30d | ❌ Not configured | LOW |
| 15 | Auto-label PRs (by path) | Route to correct reviewer | ❌ Not configured | LOW |
| 16 | Release draft automation | Auto-draft release notes on tag | ❌ Partially (in release.yaml) | LOW |
| 17 | PyPI publish verification | Post-publish check that install works | ❌ Not in pipeline | HIGH |
| 18 | Homebrew tap repo | Separate repo for formula | ❌ Not created | MEDIUM |

### 5. Security Risks

| # | Risk | Impact | Likelihood | Severity |
|---|---|---|---|---|
| 19 | No GitHub environment protection configured yet | Accidental publish to PyPI | Medium | **CRITICAL** |
| 20 | Actions use tag refs not SHA pins | Supply chain attack via tag reassignment | Low | HIGH |
| 21 | No SBOM generation in release pipeline | Can't audit shipped dependencies | Low | MEDIUM |
| 22 | No signed releases (GPG/sigstore) | Can't verify release authenticity | Low | MEDIUM |
| 23 | `.env.example` contains placeholder patterns | Users might commit real keys by accident | Low | LOW |

### 6. Single Points of Failure

| # | SPOF | Impact if Failed | Mitigation | Severity |
|---|---|---|---|---|
| 24 | GitHub (sole host) | No source, no CI, no releases, no packages | Mirror to GitLab (optional) | MEDIUM |
| 25 | 9Router (sole LLM gateway) | Factory can't make LLM calls | Direct provider fallback (future) | MEDIUM |
| 26 | PyPI (sole package host) | Users can't install | GitHub Releases has .whl files too | LOW |
| 27 | Single maintainer bus factor | Project stalls if maintainer unavailable | Add 2nd maintainer with admin access | HIGH |

### 7. Vendor Lock-in

| # | Dependency | Lock-in Level | Exit Strategy | Severity |
|---|---|---|---|---|
| 28 | GitHub Actions | Medium | Workflows are YAML — portable to GitLab CI | LOW |
| 29 | 9Router | Low | Gateway client is thin HTTP — swap to direct APIs | LOW |
| 30 | LangGraph | Medium | Node pattern is generic — could swap to custom DAG | MEDIUM |
| 31 | GHCR (container registry) | Low | Standard OCI images — push to any registry | LOW |

### 8. Cost Risks

| # | Risk | Scenario | Max Exposure | Severity |
|---|---|---|---|---|
| 32 | CI integration test burns API budget | Scheduled daily test runs uncapped | $30/month if unchecked | MEDIUM |
| 33 | Dependabot creates many PRs | Each PR triggers full CI (5 jobs) | GitHub Actions minutes exhausted | LOW |
| 34 | Docker layer caching disabled | Rebuild from scratch each time | Slow CI, no $ cost (free) | LOW |

### 9. Operational Risks

| # | Risk | Impact | Severity |
|---|---|---|---|
| 35 | No runbook for PyPI emergency (yank) | Slow response to bad release | HIGH |
| 36 | No rollback procedure tested | Can't verify rollback works under pressure | HIGH |
| 37 | No post-release smoke test | Broken release not detected until user reports | HIGH |
| 38 | No on-call rotation defined | Nobody owns incident response | MEDIUM |
| 39 | No SLA for issue triage | Community frustration | LOW |

### 10. Maintenance Risks

| # | Risk | Impact | Severity |
|---|---|---|---|
| 40 | LangGraph pre-1.0 (breaking changes) | Update may break nodes | HIGH |
| 41 | 9Router deprecates model IDs | Routing config breaks silently | MEDIUM |
| 42 | tiktoken encoding changes | Token counting becomes inaccurate | LOW |
| 43 | Python 3.11 EOL (Oct 2027) | Need to update minimum version | LOW |

---

## Risk Matrix

```
                    LIKELIHOOD
            Low         Medium        High
         ┌───────────┬───────────┬───────────┐
   High  │ 20,22     │ 19,27     │ 10,6      │
IMPACT   │ 30        │ 35,36,37  │           │
         ├───────────┼───────────┼───────────┤
  Medium │ 21,24,25  │ 32,40,41  │ 13,17     │
         │ 31        │ 38        │ 18        │
         ├───────────┼───────────┼───────────┤
   Low   │ 23,26,28  │ 33,34     │ 14,15,16  │
         │ 29,42,43  │ 39        │ 4,5,9,12  │
         └───────────┴───────────┴───────────┘
```

---

## Priority Matrix

### CRITICAL (must fix before release) — 4 items

| # | Issue | Action | Owner | ETA |
|---|---|---|---|---|
| 1+6 | No PyPI account | Create account, enable 2FA, generate token | Maintainer | 15 min |
| 2 | No GitHub org | Create `raceos` org, transfer repo | Maintainer | 10 min |
| 10 | No PYPI_API_TOKEN | Generate after account created, add to GitHub | Maintainer | 5 min |
| 19 | No environment protection | Configure "release" environment with approval | Maintainer | 10 min |

**Total: ~40 minutes to clear all CRITICAL items.**

### HIGH (fix within 24h of release) — 8 items

| # | Issue | Action | Owner | ETA |
|---|---|---|---|---|
| 7 | No TestPyPI account | Create + test publish before real release | Maintainer | 15 min |
| 13 | No CI API key | Create budget-limited key ($1/day), add to GitHub env | Maintainer | 10 min |
| 17 | No post-publish verification | Add job to release.yaml: `pip install raceos-factory==$VERSION && raceos --version` | DevOps | 30 min |
| 20 | Actions use tag refs | Pin all actions to commit SHA | DevOps | 1 hour |
| 27 | Single maintainer | Invite 2nd person with admin access | Maintainer | 5 min |
| 35 | No emergency runbook | Document: how to yank PyPI release | DevOps | 30 min |
| 36 | No rollback test | Test: `pipx install raceos-factory==0.9.0` after 1.0.0 | DevOps | 15 min |
| 37 | No post-release smoke | Add to release.yaml: install + doctor after publish | DevOps | 30 min |
| 40 | LangGraph pre-1.0 | Pin to exact working version in lockfile | DevOps | 10 min |

**Total: ~3 hours to clear all HIGH items.**

### MEDIUM (fix within 1 week) — 9 items

| # | Issue | Action | ETA |
|---|---|---|---|
| 3 | No domain | Register raceos.dev | 10 min + $12 |
| 11 | No HOMEBREW_TAP_TOKEN | Create PAT, add to secrets | 10 min |
| 18 | No homebrew-tap repo | Create raceos/homebrew-tap, push formula | 30 min |
| 21 | No SBOM | Add `syft` to release pipeline | 30 min |
| 22 | No signed releases | Setup sigstore/cosign in release | 1 hour |
| 24 | GitHub SPOF | Mirror to GitLab (push mirror) | 30 min |
| 25 | 9Router SPOF | Document direct-API fallback in config | 30 min |
| 32 | CI cost risk | Set budget cap on integration test key | 10 min |
| 38 | No on-call | Define who responds to critical issues | 15 min |
| 41 | Model ID deprecation | Add quarterly model review to calendar | 5 min |

### LOW (fix when convenient) — 12 items

| # | Issue | Action |
|---|---|---|
| 4 | Codecov | Connect after repo public |
| 5 | Discussions | Enable in repo settings |
| 9 | Docker Hub mirror | Optional redundancy |
| 12 | CODECOV_TOKEN | Generate after Codecov setup |
| 14 | Stale bot | Add `.github/workflows/stale.yaml` |
| 15 | Auto-label | Add `.github/labeler.yml` |
| 16 | Release draft | Already partially covered |
| 23 | .env patterns | Add pre-commit hook to block .env commit |
| 26 | PyPI SPOF | GitHub Releases already has .whl |
| 28-31 | Vendor lock-in | Low risk, exit strategies documented |
| 33-34 | CI costs | Free tier, no real risk |
| 39,42,43 | Maintenance | Schedule quarterly review |

---

## Action Plan: Pre-Release Sprint

### Day 1 (Release Day -1): Clear CRITICAL + HIGH

```
Hour 1:
  □ Create GitHub org "raceos" (or use personal account for v1)
  □ Create PyPI account, enable 2FA
  □ Generate PYPI_API_TOKEN (scoped to project)
  □ Create TestPyPI account + token
  □ Add secrets to GitHub (release environment)
  □ Configure environment protection (require approval)

Hour 2:
  □ Pin all GitHub Actions to commit SHA
  □ Add post-publish verification step to release.yaml
  □ Add post-release smoke test (install + doctor)
  □ Create budget-limited 9Router key for CI ($1/day)
  □ Add NINE_ROUTER_API_KEY to integration-test environment

Hour 3:
  □ Test publish to TestPyPI: uv build && twine upload --repository testpypi dist/*
  □ Test install from TestPyPI: pipx install --pip-args="--index-url https://test.pypi.org/simple/" raceos-factory
  □ Verify: raceos --version shows 1.0.0
  □ Pin LangGraph to exact version in pyproject.toml
  □ Invite 2nd maintainer with admin access
  □ Write emergency runbook (1-page: how to yank, rollback, hotfix)
```

### Day 2 (Release Day): Ship

```
  □ Final CI pass on main (all green)
  □ Tag: git tag -s v1.0.0 -m "Release v1.0.0"
  □ Push: git push origin v1.0.0
  □ Watch pipeline:
    □ PyPI publish ✅
    □ Docker push ✅
    □ GitHub Release created ✅
  □ Verify: pipx install raceos-factory && raceos --version
  □ Verify: docker run ghcr.io/raceos/raceos-factory:1.0.0 --version
  □ Post announcement
```

### Day 3-7: Clear MEDIUM

```
  □ Register raceos.dev
  □ Create homebrew-tap repo
  □ Setup SBOM generation
  □ Setup GitLab mirror
  □ Define on-call rotation
  □ Schedule quarterly model review
```

---

## Pre-Release Gate Checklist

**Release CANNOT proceed until ALL CRITICAL items are resolved:**

```
□ PyPI account exists with 2FA
□ PYPI_API_TOKEN in GitHub Secrets (release environment)
□ GitHub environment "release" has required reviewers
□ GitHub org/repo is public
□ CI pipeline green on tagged commit
□ TestPyPI test-publish succeeded
□ Post-publish verification step exists in pipeline
```

**7 checkboxes. All must be checked. No exceptions.**

---

## Verdict

```
╔══════════════════════════════════════════════════════════╗
║  DEPLOYMENT READINESS AUDIT                              ║
║                                                         ║
║  Total findings:        43                               ║
║  CRITICAL blockers:     4  (40 min to fix)              ║
║  HIGH priority:         8  (3 hours to fix)             ║
║  MEDIUM priority:       9  (1 week)                     ║
║  LOW priority:          12 (whenever)                   ║
║                                                         ║
║  Time to unblock release: ~4 hours of focused work      ║
║  Cost to unblock: $0 (all free services)                ║
║                                                         ║
║  Application architecture: NO CHANGES NEEDED            ║
║  All issues are operational/account setup tasks          ║
║                                                         ║
║  RECOMMENDATION:                                        ║
║  Execute Day 1 action plan → ship on Day 2              ║
╚══════════════════════════════════════════════════════════╝
```
