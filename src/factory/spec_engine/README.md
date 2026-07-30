# Spec Engine

> Generates spec artifacts (proposal, design, tasks) from Brain and context via LLM.

## Responsibility

Generates OpenSpec-compliant artifacts by combining Brain documents and assembled context with Jinja2 templates, then sending to an LLM for content generation. Produces proposals, design documents, and task breakdowns. Validates generated output against OpenSpec format requirements before returning. Reads existing specs for context assembly.

## Does NOT

- Decide which model to use (Router decides)
- Make HTTP calls directly (Gateway handles)
- Store or manage specs (just generates and validates)
- Bypass the spec-first workflow (generates specs, not code)
- Select its own context (Context module provides)

## Key Files (planned)

- `generator.py` — orchestrates spec generation pipeline
- `reader.py` — reads and parses existing spec artifacts
- `validator.py` — validates output against OpenSpec format
- `templates/proposal.md.j2` — proposal template
- `templates/design.md.j2` — design document template
- `templates/tasks.md.j2` — task breakdown template

## Dependencies

- `jinja2` (template rendering)
- `factory.gateway` (LLM calls via OpenRouter)
- `factory.router` (model selection for generation)
- `factory.context` (assembled context bundles)
- `factory.config` (template paths, validation rules)
