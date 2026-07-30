"""
OpenSpec Parser.

Parses OpenSpec markdown documents into structured Spec objects.
Extracts requirements, scenarios, and keyword strengths.

Supports the RaceOS OpenSpec format:
    # [name] Specification
    ## Purpose
    ## Requirements
    ### Requirement: [name]
    #### Scenario: [name]
    - GIVEN ...
    - WHEN ...
    - THEN ...
    - AND ...

Usage:
    parser = SpecParser()
    spec = parser.parse_file("../openspec/specs/firmware-core/spec.md")
    specs = parser.parse_directory("../openspec/specs/")
"""

from __future__ import annotations

import re
from pathlib import Path

from .types import (
    KeywordStrength,
    Requirement,
    Scenario,
    ScenarioStep,
    Spec,
)


class SpecParser:
    """
    Parses OpenSpec markdown into structured Spec objects.

    The parser is line-based and stateful: it reads line by line,
    tracking which section it's currently in (purpose, requirement, scenario).
    """

    # Regex patterns for section detection
    _RE_SPEC_TITLE = re.compile(r"^#\s+(.+?)(?:\s+Specification)?$")
    _RE_PURPOSE = re.compile(r"^##\s+Purpose\s*$")
    _RE_REQUIREMENTS = re.compile(r"^##\s+Requirements\s*$")
    _RE_REQUIREMENT = re.compile(r"^###\s+Requirement:\s*(.+)$")
    _RE_SCENARIO = re.compile(r"^####\s+Scenario:\s*(.+)$")
    _RE_STEP = re.compile(r"^-\s+(GIVEN|WHEN|THEN|AND)\s+(.+)$")

    # Keyword detection
    _MANDATORY_KEYWORDS = ("SHALL", "MUST", "REQUIRED")
    _RECOMMENDED_KEYWORDS = ("SHOULD", "RECOMMENDED")
    _OPTIONAL_KEYWORDS = ("MAY", "OPTIONAL")
    _NEGATIVE_KEYWORDS = ("SHALL NOT", "MUST NOT")

    def parse_file(self, file_path: str | Path) -> Spec:
        """
        Parse a single spec file.

        Args:
            file_path: Path to spec.md file.

        Returns:
            Parsed Spec object with requirements and scenarios.

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Spec file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        return self.parse_content(content, str(file_path))

    def parse_directory(self, specs_dir: str | Path) -> list[Spec]:
        """
        Parse all specs in a directory.

        Expects structure: specs_dir/<domain>/spec.md

        Args:
            specs_dir: Path to specs root directory.

        Returns:
            List of parsed Spec objects.
        """
        specs_dir = Path(specs_dir)
        specs: list[Spec] = []

        if not specs_dir.exists():
            return specs

        for spec_file in sorted(specs_dir.rglob("spec.md")):
            try:
                spec = self.parse_file(spec_file)
                specs.append(spec)
            except Exception:
                continue  # Skip unparseable specs

        return specs

    def parse_content(self, content: str, file_path: str = "") -> Spec:
        """
        Parse spec content string into a Spec object.

        Args:
            content: Markdown content of the spec.
            file_path: Source file path (for reference).

        Returns:
            Parsed Spec object.
        """
        lines = content.splitlines()
        spec = Spec(name="", file_path=file_path, raw_content=content)

        # Parser state
        current_section = "none"  # none | purpose | requirements
        current_requirement: Requirement | None = None
        current_scenario: Scenario | None = None
        purpose_lines: list[str] = []

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Spec title
            match = self._RE_SPEC_TITLE.match(stripped)
            if match and not spec.name:
                spec.name = self._slugify(match.group(1))
                continue

            # Purpose section
            if self._RE_PURPOSE.match(stripped):
                current_section = "purpose"
                continue

            # Requirements section
            if self._RE_REQUIREMENTS.match(stripped):
                # Finalize purpose
                if purpose_lines:
                    spec.purpose = "\n".join(purpose_lines).strip()
                current_section = "requirements"
                continue

            # New requirement
            match = self._RE_REQUIREMENT.match(stripped)
            if match:
                # Save previous requirement
                if current_requirement:
                    if current_scenario:
                        current_requirement.scenarios.append(current_scenario)
                        current_scenario = None
                    spec.requirements.append(current_requirement)

                current_requirement = Requirement(
                    name=match.group(1).strip(),
                    description="",
                    line_number=line_num,
                )
                continue

            # New scenario
            match = self._RE_SCENARIO.match(stripped)
            if match:
                # Save previous scenario
                if current_scenario and current_requirement:
                    current_requirement.scenarios.append(current_scenario)

                current_scenario = Scenario(
                    name=match.group(1).strip(),
                    line_number=line_num,
                )
                continue

            # Scenario step (GIVEN/WHEN/THEN/AND)
            match = self._RE_STEP.match(stripped)
            if match and current_scenario:
                step = ScenarioStep(
                    keyword=match.group(1),
                    text=match.group(2).strip(),
                    line_number=line_num,
                )
                current_scenario.steps.append(step)
                continue

            # Collect content for current context
            if current_section == "purpose" and stripped:
                purpose_lines.append(stripped)
            elif current_requirement and not current_scenario and stripped:
                # This is requirement description text
                if current_requirement.description:
                    current_requirement.description += " " + stripped
                else:
                    current_requirement.description = stripped
                    current_requirement.keyword_strength = self._detect_keyword(stripped)

        # Finalize last elements
        if current_scenario and current_requirement:
            current_requirement.scenarios.append(current_scenario)
        if current_requirement:
            spec.requirements.append(current_requirement)
        if current_section == "purpose" and purpose_lines:
            spec.purpose = "\n".join(purpose_lines).strip()

        # Derive name from file path if not in content
        if not spec.name and file_path:
            spec.name = Path(file_path).parent.name

        return spec

    def _detect_keyword(self, text: str) -> KeywordStrength:
        """Detect the keyword strength in a requirement statement."""
        text_upper = text.upper()

        for kw in self._NEGATIVE_KEYWORDS:
            if kw in text_upper:
                return KeywordStrength.NEGATIVE

        for kw in self._MANDATORY_KEYWORDS:
            if kw in text_upper:
                return KeywordStrength.MANDATORY

        for kw in self._RECOMMENDED_KEYWORDS:
            if kw in text_upper:
                return KeywordStrength.RECOMMENDED

        for kw in self._OPTIONAL_KEYWORDS:
            if kw in text_upper:
                return KeywordStrength.OPTIONAL

        return KeywordStrength.MANDATORY  # Default if no keyword found

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a slug (lowercase, hyphens)."""
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        return slug.strip("-")
