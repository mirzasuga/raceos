# AI Agents

> Agent definitions for the RaceOS AI Software Factory.

## Agent Roster

| Agent | File | Single Responsibility |
|---|---|---|
| Orchestrator | `orchestrator.md` | Route tasks, coordinate handoffs, enforce gates |
| Context Agent | `context-agent.md` | Resolve and inject context per task |
| Research Analyst | `research-analyst.md` | Gather and synthesize market/user evidence |
| Product Strategist | `product-strategist.md` | Define problems, scope MVPs, prioritize |
| Systems Architect | `systems-architect.md` | Design systems, write specs, draft ADRs |
| Hardware Engineer | `hardware-engineer.md` | Hardware design, BOM, pinout, power |
| Engineering Agent | `engineering-agent.md` | Implement code from approved specs |
| Data/Telemetry Agent | `data-telemetry-agent.md` | Data pipelines, analytics, insight |
| Review Agent | `review-agent.md` | Independent code/spec review |
| Validation Agent | `validation-agent.md` | Test planning, acceptance verification |
| Knowledge Agent | `knowledge-agent.md` | Index, sync, conflict detection |

## Rules (All Agents)

1. Read context before acting.
2. Cite sources — never fabricate.
3. Flag assumptions explicitly.
4. AI suggests, human decides on critical matters.
5. Output is always draft until human-validated.
6. Single responsibility — do not absorb another agent's job.

## Handoff Contract

Every agent-to-agent handoff includes:
- Task ID
- Objective
- Source context (documents read)
- Constraints
- Expected artifacts
- Evidence required
- Assumptions
- Risks
- Human approval required (yes/no)
