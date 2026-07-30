"""
Tests for OpenSpec engine: parser, task graph, validator, acceptance.

Tests use the real firmware-core spec as a fixture to validate
parsing against actual RaceOS spec format.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.spec_engine.acceptance import AcceptanceCriteriaExtractor
from factory.spec_engine.parser import SpecParser
from factory.spec_engine.task_graph import TaskGraphGenerator
from factory.spec_engine.types import (
    AcceptanceReport,
    KeywordStrength,
    Priority,
    Spec,
    TaskGraph,
    TaskStatus,
    ValidationSeverity,
)
from factory.spec_engine.validator import SpecValidator


# --- Fixtures ---

SAMPLE_SPEC = """# sample-domain Specification

## Purpose

This spec defines the sample domain behavior.

## Requirements

### Requirement: Data Validation

The system SHALL validate all incoming data before processing.

#### Scenario: Valid data accepted

- GIVEN valid ECU data frame
- WHEN the frame is received by the parser
- THEN the parser SHALL accept the frame
- AND SHALL return parsed telemetry values

#### Scenario: Invalid data rejected

- GIVEN a malformed data frame with incorrect checksum
- WHEN the frame is received by the parser
- THEN the parser SHALL reject the frame
- AND SHALL log a warning

---

### Requirement: Error Recovery

The system SHOULD recover from transient communication errors within 5 seconds.

#### Scenario: Reconnect after timeout

- GIVEN an active ECU connection
- WHEN communication times out for more than 3 seconds
- THEN the system SHOULD attempt reconnection
- AND SHOULD NOT lose previously received data
"""


@pytest.fixture
def sample_spec_content() -> str:
    return SAMPLE_SPEC


@pytest.fixture
def parsed_spec(sample_spec_content: str) -> Spec:
    parser = SpecParser()
    return parser.parse_content(sample_spec_content, "test/spec.md")


# --- Parser Tests ---


class TestParser:
    def test_parse_spec_name(self, parsed_spec: Spec):
        assert parsed_spec.name == "sample-domain"

    def test_parse_purpose(self, parsed_spec: Spec):
        assert "sample domain behavior" in parsed_spec.purpose

    def test_parse_requirements_count(self, parsed_spec: Spec):
        assert parsed_spec.requirement_count == 2

    def test_parse_requirement_names(self, parsed_spec: Spec):
        names = [r.name for r in parsed_spec.requirements]
        assert "Data Validation" in names
        assert "Error Recovery" in names

    def test_parse_keyword_strength_mandatory(self, parsed_spec: Spec):
        req = parsed_spec.requirements[0]  # Data Validation
        assert req.keyword_strength == KeywordStrength.MANDATORY

    def test_parse_keyword_strength_recommended(self, parsed_spec: Spec):
        req = parsed_spec.requirements[1]  # Error Recovery
        assert req.keyword_strength == KeywordStrength.RECOMMENDED

    def test_parse_scenarios(self, parsed_spec: Spec):
        req = parsed_spec.requirements[0]
        assert len(req.scenarios) == 2
        assert req.scenarios[0].name == "Valid data accepted"
        assert req.scenarios[1].name == "Invalid data rejected"

    def test_parse_scenario_steps(self, parsed_spec: Spec):
        scenario = parsed_spec.requirements[0].scenarios[0]
        keywords = [s.keyword for s in scenario.steps]
        assert "GIVEN" in keywords
        assert "WHEN" in keywords
        assert "THEN" in keywords
        assert "AND" in keywords

    def test_parse_scenario_has_gwt(self, parsed_spec: Spec):
        for req in parsed_spec.requirements:
            for scenario in req.scenarios:
                assert scenario.has_given_when_then

    def test_parse_total_scenarios(self, parsed_spec: Spec):
        assert parsed_spec.scenario_count == 3  # 2 + 1

    def test_parse_file_with_real_spec(self):
        """Test with actual RaceOS spec if available."""
        spec_path = Path("../openspec/specs/firmware-core/spec.md")
        if not spec_path.exists():
            pytest.skip("Real spec not available")

        parser = SpecParser()
        spec = parser.parse_file(spec_path)
        assert spec.requirement_count >= 5  # firmware-core has 7 requirements
        assert spec.scenario_count >= 5

    def test_parse_directory(self):
        """Test directory parsing with fixtures."""
        fixtures = Path("tests/fixtures/sample_specs")
        if not fixtures.exists():
            pytest.skip("Fixtures not available")

        parser = SpecParser()
        specs = parser.parse_directory(fixtures)
        assert len(specs) >= 1


# --- Task Graph Tests ---


class TestTaskGraph:
    def test_generate_from_spec(self, parsed_spec: Spec):
        gen = TaskGraphGenerator()
        graph = gen.from_spec(parsed_spec)

        assert graph.total_tasks == 2
        assert graph.spec_source == "sample-domain"

    def test_task_has_id(self, parsed_spec: Spec):
        gen = TaskGraphGenerator()
        graph = gen.from_spec(parsed_spec)

        for node in graph.nodes.values():
            assert node.id != ""
            assert "sample-domain" in node.id

    def test_task_priority_from_keyword(self, parsed_spec: Spec):
        gen = TaskGraphGenerator()
        graph = gen.from_spec(parsed_spec)

        nodes = list(graph.nodes.values())
        # First req (SHALL) → HIGH priority
        assert nodes[0].priority == Priority.HIGH
        # Second req (SHOULD) → MEDIUM priority
        assert nodes[1].priority == Priority.MEDIUM

    def test_task_has_acceptance_criteria(self, parsed_spec: Spec):
        gen = TaskGraphGenerator()
        graph = gen.from_spec(parsed_spec)

        nodes = list(graph.nodes.values())
        # Data Validation has THEN clauses → criteria
        assert len(nodes[0].acceptance_criteria) > 0

    def test_execution_order_respects_dependencies(self, parsed_spec: Spec):
        gen = TaskGraphGenerator(respect_order=True)
        graph = gen.from_spec(parsed_spec)

        order = graph.execution_order
        # First task should come before second
        assert order[0].requirement_name == "Data Validation"
        assert order[1].requirement_name == "Error Recovery"

    def test_ready_tasks_when_no_deps(self, parsed_spec: Spec):
        gen = TaskGraphGenerator(respect_order=False)
        graph = gen.from_spec(parsed_spec)

        # Without order deps, all tasks should be ready
        ready = graph.ready_tasks
        assert len(ready) == 2

    def test_domain_inference(self, parsed_spec: Spec):
        gen = TaskGraphGenerator()
        # sample-domain doesn't match firmware keywords
        graph = gen.from_spec(parsed_spec)
        nodes = list(graph.nodes.values())
        assert nodes[0].domain == "firmware"  # Default


# --- Validator Tests ---


class TestValidator:
    def test_valid_spec_passes(self, parsed_spec: Spec):
        validator = SpecValidator()
        report = validator.validate(parsed_spec)
        assert report.is_valid

    def test_missing_purpose_is_error(self):
        spec = Spec(name="test", file_path="test.md", purpose="")
        spec.requirements = [
            _make_requirement("Foo", scenarios=[_make_scenario("Bar")])
        ]
        validator = SpecValidator()
        report = validator.validate(spec)
        assert not report.is_valid
        assert any("Purpose" in i.message for i in report.errors)

    def test_requirement_without_scenario_is_error(self):
        spec = Spec(name="test", file_path="test.md", purpose="Test purpose")
        spec.requirements = [
            _make_requirement("Foo", scenarios=[]),  # No scenarios!
        ]
        validator = SpecValidator()
        report = validator.validate(spec)
        assert not report.is_valid
        assert any("no scenarios" in i.message for i in report.errors)

    def test_scenario_without_then_is_error(self):
        from factory.spec_engine.types import Scenario, ScenarioStep
        bad_scenario = Scenario(name="Bad", steps=[
            ScenarioStep(keyword="GIVEN", text="something"),
            ScenarioStep(keyword="WHEN", text="something"),
            # Missing THEN!
        ])
        spec = Spec(name="test", file_path="test.md", purpose="Purpose")
        spec.requirements = [_make_requirement("Foo", scenarios=[bad_scenario])]

        validator = SpecValidator()
        report = validator.validate(spec)
        assert not report.is_valid
        assert any("THEN" in i.message for i in report.errors)


# --- Acceptance Tests ---


class TestAcceptanceCriteria:
    def test_extract_from_spec(self, parsed_spec: Spec):
        extractor = AcceptanceCriteriaExtractor()
        report = extractor.extract_from_spec(parsed_spec)

        assert isinstance(report, AcceptanceReport)
        assert report.total > 0
        # Should have criteria from THEN clauses + SHALL statements
        assert report.total >= 4  # At least from THEN clauses

    def test_criteria_have_source(self, parsed_spec: Spec):
        extractor = AcceptanceCriteriaExtractor()
        report = extractor.extract_from_spec(parsed_spec)

        for criterion in report.criteria:
            assert criterion.source is not None
            assert criterion.requirement_name != ""
            assert criterion.spec_name != ""

    def test_format_checklist(self, parsed_spec: Spec):
        extractor = AcceptanceCriteriaExtractor()
        report = extractor.extract_from_spec(parsed_spec)
        checklist = extractor.format_checklist(report)

        assert "- [ ]" in checklist  # Has unchecked items
        assert "Data Validation" in checklist
        assert "Total:" in checklist

    def test_format_for_prompt(self, parsed_spec: Spec):
        extractor = AcceptanceCriteriaExtractor()
        report = extractor.extract_from_spec(parsed_spec)
        prompt_text = extractor.format_for_prompt(report)

        assert "Acceptance Criteria:" in prompt_text
        assert "1." in prompt_text  # Numbered


# --- Helpers ---


def _make_requirement(name: str, scenarios: list = None):
    from factory.spec_engine.types import Requirement, Scenario, ScenarioStep
    if scenarios is None:
        scenarios = [_make_scenario("Default")]
    return Requirement(
        name=name,
        description=f"The system SHALL {name.lower()}.",
        scenarios=scenarios,
    )


def _make_scenario(name: str):
    from factory.spec_engine.types import Scenario, ScenarioStep
    return Scenario(name=name, steps=[
        ScenarioStep(keyword="GIVEN", text="precondition"),
        ScenarioStep(keyword="WHEN", text="action"),
        ScenarioStep(keyword="THEN", text="expected result"),
    ])
