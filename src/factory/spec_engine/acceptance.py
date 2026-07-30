"""
Acceptance Criteria Manager.

Extracts, manages, and tracks acceptance criteria from OpenSpec documents.

Sources of criteria:
    1. THEN clauses in scenarios → direct acceptance conditions
    2. SHALL statements in requirements → required behavior
    3. SHALL NOT statements → negative criteria (must not happen)

Criteria are mapped to test files when possible, enabling
automated verification of spec compliance.

Usage:
    extractor = AcceptanceCriteriaExtractor(config)
    report = extractor.extract_from_spec(spec)
    criteria = extractor.extract_from_requirement(requirement, spec_name)
    checklist = extractor.format_checklist(report)
"""

from __future__ import annotations

import re
from pathlib import Path

from .types import (
    AcceptanceCriterion,
    AcceptanceReport,
    CriterionSource,
    Requirement,
    Scenario,
    Spec,
)


class AcceptanceConfig:
    """Configuration for acceptance criteria extraction."""

    def __init__(
        self,
        extract_from_scenarios: bool = True,
        extract_from_requirements: bool = True,
        include_negative: bool = True,
        output_format: str = "checklist",
        test_path_pattern: str = "firmware/tests/test_{slug}.cpp",
        test_dir: str = "../firmware/tests/",
    ):
        self.extract_from_scenarios = extract_from_scenarios
        self.extract_from_requirements = extract_from_requirements
        self.include_negative = include_negative
        self.output_format = output_format
        self.test_path_pattern = test_path_pattern
        self.test_dir = test_dir


class AcceptanceCriteriaExtractor:
    """
    Extracts acceptance criteria from parsed specs.

    Produces a structured report that can be used by:
    - Validation Agent: to verify implementation
    - Engineering Agent: to know what "done" means
    - Human reviewers: as a review checklist
    """

    def __init__(self, config: AcceptanceConfig | None = None):
        self.config = config or AcceptanceConfig()

    def extract_from_spec(self, spec: Spec) -> AcceptanceReport:
        """
        Extract all acceptance criteria from a spec.

        Args:
            spec: Parsed Spec object.

        Returns:
            AcceptanceReport with all criteria.
        """
        report = AcceptanceReport(spec_name=spec.name)

        for req in spec.requirements:
            criteria = self.extract_from_requirement(req, spec.name)
            report.criteria.extend(criteria)

        report.update_counts()
        return report

    def extract_from_requirement(
        self, req: Requirement, spec_name: str
    ) -> list[AcceptanceCriterion]:
        """
        Extract criteria from a single requirement.

        Args:
            req: Parsed Requirement object.
            spec_name: Parent spec name.

        Returns:
            List of acceptance criteria.
        """
        criteria: list[AcceptanceCriterion] = []

        # 1. From THEN clauses in scenarios
        if self.config.extract_from_scenarios:
            for scenario in req.scenarios:
                criteria.extend(
                    self._extract_from_scenario(scenario, req.name, spec_name)
                )

        # 2. From requirement description (SHALL statements)
        if self.config.extract_from_requirements:
            criteria.extend(
                self._extract_from_description(req, spec_name)
            )

        # 3. Try to map to test files
        for criterion in criteria:
            criterion.test_file = self._find_test_file(req.name)

        return criteria

    def format_checklist(self, report: AcceptanceReport) -> str:
        """
        Format acceptance criteria as a markdown checklist.

        Args:
            report: AcceptanceReport to format.

        Returns:
            Markdown string with checkbox items.
        """
        lines: list[str] = [f"# Acceptance Criteria: {report.spec_name}", ""]

        current_requirement = ""
        for criterion in report.criteria:
            if criterion.requirement_name != current_requirement:
                current_requirement = criterion.requirement_name
                lines.append(f"\n## {current_requirement}\n")

            prefix = "- [x]" if criterion.satisfied else "- [ ]"
            source_tag = f"[{criterion.source.value}]"
            lines.append(f"{prefix} {criterion.text} {source_tag}")

            if criterion.test_file:
                lines.append(f"  _Test: `{criterion.test_file}`_")

        lines.append(f"\n---\n**Total: {report.total} | "
                     f"Satisfied: {report.satisfied} | "
                     f"Remaining: {report.unsatisfied}**")

        return "\n".join(lines)

    def format_for_prompt(self, report: AcceptanceReport) -> str:
        """
        Format criteria for injection into LLM prompt.

        Compact format optimized for token efficiency.

        Args:
            report: AcceptanceReport to format.

        Returns:
            Concise criteria text for prompt injection.
        """
        lines: list[str] = ["Acceptance Criteria:"]
        for i, criterion in enumerate(report.criteria, 1):
            lines.append(f"{i}. {criterion.text}")
        return "\n".join(lines)

    # --- Internal: Extraction ---

    def _extract_from_scenario(
        self, scenario: Scenario, req_name: str, spec_name: str
    ) -> list[AcceptanceCriterion]:
        """Extract criteria from THEN/AND steps in a scenario."""
        criteria: list[AcceptanceCriterion] = []

        in_then = False
        for step in scenario.steps:
            if step.keyword == "THEN":
                in_then = True
                criteria.append(AcceptanceCriterion(
                    text=step.text,
                    source=CriterionSource.THEN_CLAUSE,
                    requirement_name=req_name,
                    spec_name=spec_name,
                    scenario_name=scenario.name,
                ))
            elif step.keyword == "AND" and in_then:
                criteria.append(AcceptanceCriterion(
                    text=step.text,
                    source=CriterionSource.THEN_CLAUSE,
                    requirement_name=req_name,
                    spec_name=spec_name,
                    scenario_name=scenario.name,
                ))
            elif step.keyword in ("GIVEN", "WHEN"):
                in_then = False

        return criteria

    def _extract_from_description(
        self, req: Requirement, spec_name: str
    ) -> list[AcceptanceCriterion]:
        """Extract criteria from SHALL/SHALL NOT in requirement description."""
        criteria: list[AcceptanceCriterion] = []
        desc = req.description

        if not desc:
            return criteria

        # SHALL NOT (negative criteria)
        if self.config.include_negative and "SHALL NOT" in desc.upper():
            criteria.append(AcceptanceCriterion(
                text=desc,
                source=CriterionSource.NEGATIVE,
                requirement_name=req.name,
                spec_name=spec_name,
            ))
        elif "SHALL" in desc.upper():
            criteria.append(AcceptanceCriterion(
                text=desc,
                source=CriterionSource.SHALL_STATEMENT,
                requirement_name=req.name,
                spec_name=spec_name,
            ))

        return criteria

    # --- Internal: Test Mapping ---

    def _find_test_file(self, requirement_name: str) -> str:
        """Try to find a corresponding test file for a requirement."""
        slug = self._slugify(requirement_name)
        test_path = self.config.test_path_pattern.format(slug=slug)

        # Check if test file exists
        full_path = Path(self.config.test_dir) / Path(test_path).name
        if full_path.exists():
            return test_path

        # Try alternative patterns
        alternatives = [
            f"test_{slug}.cpp",
            f"test_{slug}.py",
            f"test_{slug}.ts",
        ]
        test_dir = Path(self.config.test_dir)
        if test_dir.exists():
            for alt in alternatives:
                if (test_dir / alt).exists():
                    return str(test_dir / alt)

        return ""  # No test file found

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert requirement name to test-friendly slug."""
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9\s]", "", slug)
        slug = re.sub(r"\s+", "_", slug)
        return slug[:50]
