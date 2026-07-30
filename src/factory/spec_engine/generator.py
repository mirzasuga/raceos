"""
Spec Generator.

Generates new OpenSpec artifacts (proposals, designs, task breakdowns)
via LLM, using Brain context and existing specs as input.

Generated artifacts follow the OpenSpec format and are written
to openspec/changes/<task-name>/ for human review.

Usage:
    generator = SpecGenerator(config)
    proposal = generator.generate_proposal(task_description, context)
    tasks = generator.generate_task_breakdown(proposal, context)
    generator.write_artifacts(task_name, proposal, tasks)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from jinja2 import Environment, FileSystemLoader

log = structlog.get_logger()


class GeneratorConfig:
    """Configuration for spec generation."""

    def __init__(
        self,
        templates_dir: str = "./specs/templates/",
        output_dir: str = "../openspec/changes/",
        model: str = "anthropic/claude-sonnet-4.6",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        max_requirements: int = 10,
        max_scenarios: int = 5,
    ):
        self.templates_dir = templates_dir
        self.output_dir = output_dir
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_requirements = max_requirements
        self.max_scenarios = max_scenarios


class SpecGenerator:
    """
    Generates OpenSpec artifacts using LLM + templates.

    Generation flow:
    1. Receive task description + Brain context
    2. Generate structured proposal (problem + scope + criteria)
    3. Generate task breakdown (ordered steps + acceptance)
    4. Render via Jinja2 templates
    5. Write to openspec/changes/<task>/
    """

    def __init__(self, config: GeneratorConfig | None = None, gateway=None, router=None):
        self.config = config or GeneratorConfig()
        self._gateway = gateway
        self._router = router
        templates_path = Path(self.config.templates_dir)
        if templates_path.exists():
            self._env = Environment(loader=FileSystemLoader(str(templates_path)))
        else:
            self._env = None

    def generate_proposal(
        self,
        task_description: str,
        context: str,
        model: str | None = None,
    ) -> str:
        """
        Generate a change proposal document.

        The proposal answers: WHY are we doing this?
        - Problem statement
        - Scope (in/out)
        - Success criteria
        - Constraints from Brain
        """
        prompt = f"""Generate an OpenSpec change proposal for a motorsport embedded platform (RaceOS).

## Context
{context[:3000]}

## Task
{task_description}

## Instructions
Produce a markdown proposal with these sections:
# Proposal: [title]
## Problem Statement
(What problem are we solving? Evidence?)
## Scope
### In Scope
(What will be delivered)
### Out of Scope
(What will NOT be delivered)
## Success Criteria
(Measurable criteria — use checkboxes)
## Constraints
(From architecture principles)
## Estimated Complexity
(low | medium | high)
"""

        response = self._call_llm(prompt, model)
        if response:
            return response

        # Fallback: render from template
        return self._render_proposal_template(task_description)

    def generate_task_breakdown(
        self,
        task_description: str,
        proposal: str,
        context: str,
        model: str | None = None,
    ) -> str:
        """
        Generate a task breakdown document.

        The breakdown answers: WHAT steps to take?
        """
        prompt = f"""Break down this proposal into implementation tasks.

## Proposal
{proposal[:2000]}

## Context
{context[:2000]}

## Task
{task_description}

## Instructions
Produce a markdown task breakdown:
# Task Breakdown: [title]
## Task 1: [title]
**Files:** [file paths]
**Complexity:** low|medium|high
[description]
**Acceptance Criteria:**
- [ ] criterion 1
- [ ] criterion 2

(Repeat for 3-7 tasks, ordered by dependency)
"""

        response = self._call_llm(prompt, model)
        if response:
            return response

        return self._render_tasks_template(task_description)

    def generate_spec(
        self,
        domain: str,
        requirements_text: str,
        context: str,
        model: str | None = None,
    ) -> str:
        """
        Generate a new spec document in OpenSpec format.

        Produces:
        - Purpose section
        - Requirements with SHALL statements
        - Scenarios with GIVEN/WHEN/THEN
        """
        prompt = f"""Generate an OpenSpec specification for the RaceOS project.

## Context
{context[:2000]}

## Domain
{domain}

## Requirements (natural language)
{requirements_text}

## Instructions
Produce a spec in this exact format:

# {domain} Specification

## Purpose
[One paragraph explaining what this spec defines]

## Requirements

### Requirement: [Name]
The system SHALL [requirement statement].

#### Scenario: [Name]
- GIVEN [precondition]
- WHEN [action]
- THEN [expected result]
- AND [additional result]

(Use SHALL for mandatory, SHOULD for recommended, MAY for optional)
(Include 2-4 requirements with 1-2 scenarios each)
"""

        response = self._call_llm(prompt, model)
        if response:
            return response

        # Minimal fallback
        return f"""# {domain} Specification

## Purpose

Specification for {domain} domain.

## Requirements

### Requirement: Core Behavior

The system SHALL implement {requirements_text[:100]}.

#### Scenario: Basic operation

- GIVEN the system is initialized
- WHEN the primary operation is triggered
- THEN the system SHALL produce the expected output
"""

    def write_artifacts(
        self,
        task_name: str,
        proposal: str,
        tasks: str,
        design: str = "",
    ) -> Path:
        """Write generated artifacts to openspec/changes/<task_name>/."""
        slug = self._slugify(task_name)
        output_dir = Path(self.config.output_dir) / slug
        output_dir.mkdir(parents=True, exist_ok=True)

        (output_dir / "proposal.md").write_text(proposal, encoding="utf-8")
        (output_dir / "tasks.md").write_text(tasks, encoding="utf-8")

        if design:
            (output_dir / "design.md").write_text(design, encoding="utf-8")

        return output_dir

    # --- LLM Integration ---

    def _call_llm(self, prompt: str, model: str | None = None) -> str | None:
        """Call LLM for generation. Returns None on failure."""
        try:
            gateway = self._gateway
            router = self._router

            if gateway is None or router is None:
                from factory.router.router import NineRouter
                from factory.gateway.client import GatewayClient
                router = NineRouter.from_config("config/router.yaml")
                gateway = GatewayClient()

            route = router.route(task_type="spec_writing")
            use_model = model or route.model_id

            from factory.gateway.models import CompletionRequest, Message
            response = gateway.complete(CompletionRequest(
                model=use_model,
                messages=[Message(role="user", content=prompt)],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            ))

            router.record_usage(
                model_key=route.model_key,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                task_type="spec_writing",
            )

            if self._gateway is None:
                gateway.close()

            return response.content

        except Exception as e:
            log.warning("spec_generator.llm_failed", error=str(e))
            return None

    # --- Template Rendering (fallback when LLM unavailable) ---

    def _render_proposal_template(self, task_description: str) -> str:
        """Render proposal from Jinja2 template (fallback)."""
        if self._env and "proposal.md" in self._env.list_templates():
            template = self._env.get_template("proposal.md")
            return template.render(
                title=task_description[:80],
                problem=f"Problem to solve: {task_description}",
                scope="To be defined during planning.",
                criteria=["Implementation compiles without errors", "Tests pass"],
                out_of_scope=["Out of scope items TBD"],
                complexity="medium",
                constraints=["No dynamic allocation", "Host-native testable"],
            )
        return f"# Proposal: {task_description}\n\n## Problem\n\n{task_description}\n\n## Scope\n\nTBD\n"

    def _render_tasks_template(self, task_description: str) -> str:
        """Render tasks from Jinja2 template (fallback)."""
        if self._env and "tasks.md" in self._env.list_templates():
            template = self._env.get_template("tasks.md")
            return template.render(
                title=task_description[:80],
                summary=f"Task breakdown for: {task_description}",
                tasks=[{
                    "title": "Implementation",
                    "domain": "firmware",
                    "files": ["TBD"],
                    "description": task_description,
                    "complexity": "medium",
                    "acceptance_criteria": ["Build passes", "Tests pass"],
                }],
            )
        return f"# Tasks: {task_description}\n\n## Task 1: Implement\n\n- [ ] Build passes\n- [ ] Tests pass\n"

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert task name to directory-safe slug."""
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        return slug[:50].strip("-") or "unnamed"
