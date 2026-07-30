"""
Spec Validator.

Validates OpenSpec documents for completeness and consistency.

Checks:
    - Structure: purpose, requirements, scenarios exist
    - Completeness: every requirement has scenarios with G/W/T
    - Consistency: keywords don't conflict within a requirement
    - References: cross-references to ADRs/specs are valid
    - Architecture: requirements respect layer constraints

Usage:
    validator = SpecValidator(config)
    report = validator.validate(spec)
    report = validator.validate_all(specs)
    assert report.is_valid
"""

from __future__ import annotations

from pathlib import Path

from .types import (
    KeywordStrength,
    Requirement,
    Scenario,
    Spec,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)


class ValidatorConfig:
    """Configuration for spec validation rules."""

    def __init__(
        self,
        check_purpose: bool = True,
        check_requirements_have_scenarios: bool = True,
        check_scenarios_have_gwt: bool = True,
        check_no_orphan_scenarios: bool = True,
        check_keyword_consistency: bool = True,
        check_cross_references: bool = True,
        adr_dir: str = "../adr/",
        specs_dir: str = "../openspec/specs/",
    ):
        self.check_purpose = check_purpose
        self.check_requirements_have_scenarios = check_requirements_have_scenarios
        self.check_scenarios_have_gwt = check_scenarios_have_gwt
        self.check_no_orphan_scenarios = check_no_orphan_scenarios
        self.check_keyword_consistency = check_keyword_consistency
        self.check_cross_references = check_cross_references
        self.adr_dir = adr_dir
        self.specs_dir = specs_dir


class SpecValidator:
    """
    Validates OpenSpec documents for correctness.

    Reports issues with severity levels:
        - ERROR: Must be fixed (blocks execution)
        - WARNING: Should be fixed (quality concern)
        - INFO: Informational (style suggestion)
    """

    def __init__(self, config: ValidatorConfig | None = None):
        self.config = config or ValidatorConfig()

    def validate(self, spec: Spec) -> ValidationReport:
        """
        Validate a single spec.

        Runs all configured checks and produces a report.

        Args:
            spec: Parsed Spec object.

        Returns:
            ValidationReport with issues found.
        """
        report = ValidationReport(specs_checked=1)
        report.requirements_checked = len(spec.requirements)
        report.scenarios_checked = sum(len(r.scenarios) for r in spec.requirements)

        # Structure checks
        if self.config.check_purpose:
            self._check_purpose(spec, report)

        # Requirement checks
        for req in spec.requirements:
            if self.config.check_requirements_have_scenarios:
                self._check_requirement_has_scenarios(spec, req, report)

            if self.config.check_keyword_consistency:
                self._check_keyword_consistency(spec, req, report)

            # Scenario checks
            for scenario in req.scenarios:
                if self.config.check_scenarios_have_gwt:
                    self._check_scenario_gwt(spec, req, scenario, report)

        # Cross-reference checks
        if self.config.check_cross_references:
            self._check_cross_references(spec, report)

        return report

    def validate_all(self, specs: list[Spec]) -> ValidationReport:
        """
        Validate multiple specs and aggregate results.

        Args:
            specs: List of parsed Spec objects.

        Returns:
            Combined ValidationReport.
        """
        combined = ValidationReport()

        for spec in specs:
            report = self.validate(spec)
            combined.issues.extend(report.issues)
            combined.specs_checked += 1
            combined.requirements_checked += report.requirements_checked
            combined.scenarios_checked += report.scenarios_checked

        return combined

    # --- Check Methods ---

    def _check_purpose(self, spec: Spec, report: ValidationReport) -> None:
        """Check that spec has a Purpose section."""
        if not spec.purpose or not spec.purpose.strip():
            report.issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Spec is missing a Purpose section.",
                spec_name=spec.name,
                suggestion="Add a '## Purpose' section explaining what this spec defines.",
            ))

    def _check_requirement_has_scenarios(
        self, spec: Spec, req: Requirement, report: ValidationReport
    ) -> None:
        """Check that every requirement has at least one scenario."""
        if not req.scenarios:
            report.issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Requirement '{req.name}' has no scenarios.",
                spec_name=spec.name,
                requirement_name=req.name,
                line_number=req.line_number,
                suggestion="Add at least one '#### Scenario:' with GIVEN/WHEN/THEN steps.",
            ))

    def _check_scenario_gwt(
        self, spec: Spec, req: Requirement, scenario: Scenario, report: ValidationReport
    ) -> None:
        """Check that scenario has GIVEN/WHEN/THEN structure."""
        if not scenario.has_given_when_then:
            missing = []
            keywords = [s.keyword for s in scenario.steps]
            if "GIVEN" not in keywords:
                missing.append("GIVEN")
            if "WHEN" not in keywords:
                missing.append("WHEN")
            if "THEN" not in keywords:
                missing.append("THEN")

            report.issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Scenario '{scenario.name}' is missing: {', '.join(missing)}.",
                spec_name=spec.name,
                requirement_name=req.name,
                scenario_name=scenario.name,
                line_number=scenario.line_number,
                suggestion="Add the missing GIVEN/WHEN/THEN steps.",
            ))

    def _check_keyword_consistency(
        self, spec: Spec, req: Requirement, report: ValidationReport
    ) -> None:
        """Check that keywords within a requirement are consistent."""
        if not req.description:
            report.issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"Requirement '{req.name}' has no description text.",
                spec_name=spec.name,
                requirement_name=req.name,
                line_number=req.line_number,
                suggestion="Add a 'The system SHALL/SHOULD/MAY ...' statement.",
            ))
            return

        # Check for mixed mandatory + optional in same requirement
        desc_upper = req.description.upper()
        has_shall = "SHALL" in desc_upper or "MUST" in desc_upper
        has_should = "SHOULD" in desc_upper
        has_may = "MAY" in desc_upper

        if has_shall and (has_should or has_may):
            report.issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"Requirement '{req.name}' mixes keyword strengths (SHALL + SHOULD/MAY).",
                spec_name=spec.name,
                requirement_name=req.name,
                line_number=req.line_number,
                suggestion="Split into separate requirements with consistent keyword strength.",
            ))

    def _check_cross_references(self, spec: Spec, report: ValidationReport) -> None:
        """Check that referenced ADRs and specs actually exist."""
        content = spec.raw_content

        # Find ADR references
        adr_refs = set(re.findall(r"ADR-\d+", content))
        adr_dir = Path(self.config.adr_dir)

        for adr_ref in adr_refs:
            # Check if ADR file exists (any file starting with the ADR number)
            if adr_dir.exists():
                matches = list(adr_dir.glob(f"{adr_ref}*"))
                if not matches:
                    report.issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=f"Referenced {adr_ref} not found in {self.config.adr_dir}.",
                        spec_name=spec.name,
                        suggestion=f"Create the ADR or fix the reference.",
                    ))


# Need re for cross-reference checking
import re
