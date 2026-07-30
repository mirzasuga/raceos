# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.x (latest minor) | ✅ Security updates |
| 1.x (previous minor) | ✅ Critical security only (3 months) |
| < 1.0 | ❌ No support |

## Reporting a Vulnerability

**DO NOT open a public issue for security vulnerabilities.**

### Contact

Email: security@raceos.dev

### Process

1. **You report** → we acknowledge within 48 hours
2. **We assess** → initial severity within 7 days
3. **We fix** → patch released within 30 days (critical: 7 days)
4. **We credit** → you're acknowledged in the advisory (unless you prefer not)

### Scope

**In scope:**
- API key exposure in logs/output
- Command injection via CLI input
- Path traversal in file operations
- Privilege escalation in MCP tool execution
- Dependency vulnerabilities (when exploitable)
- Secrets leaked in error messages

**Out of scope:**
- Vulnerabilities in LLM providers (report to them directly)
- Social engineering attacks
- Physical access attacks
- Denial of service via excessive API calls (budget-limited by design)

## Security Design

The factory implements defense-in-depth:
- Environment filtering (subprocess gets minimal env vars)
- Path-safe file access (traversal protection in BrainReader)
- Command allowlists (terminal MCP tool)
- Output sanitization (ANSI/injection stripping)
- Secret isolation (.env only, never in config or logs)
