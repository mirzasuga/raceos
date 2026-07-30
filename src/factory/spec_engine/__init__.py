# OpenSpec generation and reading.
"""
OpenSpec integration for the AI Software Factory.

Provides:
    - Parser: parse OpenSpec markdown into structured objects
    - Task Graph: generate dependency graph from requirements
    - Validator: check completeness and consistency
    - Acceptance: extract and track acceptance criteria
    - Generator: create new spec artifacts via LLM

OpenSpec is the Definition Layer — behavioral contracts that
implementation is verified against.

Usage:
    from factory.spec_engine import SpecParser, TaskGraphGenerator, SpecValidator

    parser = SpecParser()
    specs = parser.parse_directory("../openspec/specs/")

    graph_gen = TaskGraphGenerator()
    graph = graph_gen.from_specs(specs)

    validator = SpecValidator()
    report = validator.validate_all(specs)
"""

from .acceptance import AcceptanceConfig, AcceptanceCriteriaExtractor
from .generator import GeneratorConfig, SpecGenerator
from .parser import SpecParser
from .task_graph import TaskGraphGenerator
from .types import (
    AcceptanceCriterion,
    AcceptanceReport,
    KeywordStrength,
    Priority,
    Requirement,
    Scenario,
    ScenarioStep,
    Spec,
    TaskGraph,
    TaskNode,
    TaskStatus,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from .validator import SpecValidator, ValidatorConfig

__all__ = [
    # Parser
    "SpecParser",
    # Task Graph
    "TaskGraphGenerator",
    # Validator
    "SpecValidator",
    "ValidatorConfig",
    # Acceptance
    "AcceptanceCriteriaExtractor",
    "AcceptanceConfig",
    # Generator
    "SpecGenerator",
    "GeneratorConfig",
    # Types
    "Spec",
    "Requirement",
    "Scenario",
    "ScenarioStep",
    "KeywordStrength",
    "Priority",
    "TaskGraph",
    "TaskNode",
    "TaskStatus",
    "AcceptanceCriterion",
    "AcceptanceReport",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]
