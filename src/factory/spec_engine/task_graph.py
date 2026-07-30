"""
Task Graph Generator.

Converts parsed specs into a dependency graph of executable tasks.
Each requirement becomes a task node with:
    - Priority (from keyword strength)
    - Dependencies (from references and ordering)
    - Acceptance criteria (from scenarios)

The graph supports topological ordering for sequential execution
and parallel detection for concurrent work.

Usage:
    generator = TaskGraphGenerator()
    graph = generator.from_spec(spec)
    graph = generator.from_specs(specs)
    order = graph.execution_order
    ready = graph.ready_tasks
"""

from __future__ import annotations

import re
from .types import (
    AcceptanceCriterion,
    CriterionSource,
    Priority,
    Requirement,
    Spec,
    TaskGraph,
    TaskNode,
    TaskStatus,
)


class TaskGraphGenerator:
    """
    Generates task dependency graphs from parsed specs.

    Strategies:
    - One task per requirement (default)
    - Dependencies inferred from references and spec ordering
    - Priority derived from keyword strength
    """

    def __init__(
        self,
        task_per_requirement: bool = True,
        infer_dependencies: bool = True,
        respect_order: bool = True,
    ):
        self.task_per_requirement = task_per_requirement
        self.infer_dependencies = infer_dependencies
        self.respect_order = respect_order

    def from_spec(self, spec: Spec) -> TaskGraph:
        """
        Generate a task graph from a single spec.

        Args:
            spec: Parsed Spec object.

        Returns:
            TaskGraph with nodes for each requirement.
        """
        graph = TaskGraph(spec_source=spec.name)

        previous_task_id: str | None = None

        for i, req in enumerate(spec.requirements):
            task_id = self._make_task_id(spec.name, req.name, i)
            node = self._requirement_to_task(task_id, req, spec)

            # Infer ordering dependency
            if self.respect_order and previous_task_id:
                # Only add order dependency if not already dependent
                if previous_task_id not in node.dependencies:
                    node.dependencies.append(previous_task_id)

            # Infer content-based dependencies
            if self.infer_dependencies:
                content_deps = self._infer_content_dependencies(req, spec, graph)
                for dep in content_deps:
                    if dep not in node.dependencies:
                        node.dependencies.append(dep)

            graph.add_node(node)
            previous_task_id = task_id

        return graph

    def from_specs(self, specs: list[Spec]) -> TaskGraph:
        """
        Generate a unified task graph from multiple specs.

        Cross-spec dependencies are inferred from references.

        Args:
            specs: List of parsed Spec objects.

        Returns:
            Combined TaskGraph.
        """
        graph = TaskGraph(spec_source=", ".join(s.name for s in specs))

        for spec in specs:
            spec_graph = self.from_spec(spec)
            for node in spec_graph.nodes.values():
                graph.add_node(node)

        # Resolve cross-spec dependencies
        if self.infer_dependencies:
            self._resolve_cross_spec_deps(graph, specs)

        return graph

    def _requirement_to_task(self, task_id: str, req: Requirement, spec: Spec) -> TaskNode:
        """Convert a requirement into a task node."""
        # Extract acceptance criteria from scenarios
        criteria = self._extract_criteria(req, spec.name)

        return TaskNode(
            id=task_id,
            title=f"Implement: {req.name}",
            requirement_name=req.name,
            spec_name=spec.name,
            priority=req.priority,
            status=TaskStatus.PENDING,
            dependencies=[],
            acceptance_criteria=[c.text for c in criteria],
            estimated_complexity=self._estimate_complexity(req),
            domain=self._infer_domain(spec.name),
        )

    def _extract_criteria(self, req: Requirement, spec_name: str) -> list[AcceptanceCriterion]:
        """Extract acceptance criteria from requirement scenarios."""
        criteria: list[AcceptanceCriterion] = []

        # From THEN clauses
        for scenario in req.scenarios:
            for step in scenario.steps:
                if step.keyword in ("THEN", "AND") and scenario.then_steps:
                    if step in scenario.then_steps:
                        criteria.append(AcceptanceCriterion(
                            text=step.text,
                            source=CriterionSource.THEN_CLAUSE,
                            requirement_name=req.name,
                            spec_name=spec_name,
                            scenario_name=scenario.name,
                        ))

        # From requirement description (SHALL statements)
        if "SHALL" in req.description.upper():
            criteria.append(AcceptanceCriterion(
                text=req.description,
                source=CriterionSource.SHALL_STATEMENT,
                requirement_name=req.name,
                spec_name=spec_name,
            ))

        return criteria

    def _infer_content_dependencies(
        self, req: Requirement, spec: Spec, graph: TaskGraph
    ) -> list[str]:
        """Infer dependencies from requirement text references."""
        deps: list[str] = []
        text = req.description.lower()

        # Check for dependency markers
        dependency_markers = ["depends on", "requires", "after", "builds upon", "extends"]
        for marker in dependency_markers:
            if marker in text:
                # Try to find which requirement is referenced
                for other_req in spec.requirements:
                    if other_req.name != req.name:
                        if other_req.name.lower() in text:
                            other_id = self._find_task_id(graph, other_req.name)
                            if other_id:
                                deps.append(other_id)

        return deps

    def _resolve_cross_spec_deps(self, graph: TaskGraph, specs: list[Spec]) -> None:
        """
        Resolve dependencies that cross spec boundaries.

        Strategy: If a requirement in spec B references spec A's domain
        (via keywords like "depends on [specA domain]"), add a dependency
        from B's first task to A's last task.
        """
        # Build map: spec_name → list of task IDs in that spec
        spec_tasks: dict[str, list[str]] = {}
        for node in graph.nodes.values():
            spec_tasks.setdefault(node.spec_name, []).append(node.id)

        # Check each requirement for references to other specs
        for spec in specs:
            for req in spec.requirements:
                desc_lower = req.description.lower()
                for other_spec in specs:
                    if other_spec.name == spec.name:
                        continue
                    # If requirement mentions another spec's domain name
                    if other_spec.name.replace("-", " ") in desc_lower or other_spec.name in desc_lower:
                        # Add dependency: this spec's first task depends on other spec's last task
                        this_tasks = spec_tasks.get(spec.name, [])
                        other_tasks = spec_tasks.get(other_spec.name, [])
                        if this_tasks and other_tasks:
                            first_of_this = this_tasks[0]
                            last_of_other = other_tasks[-1]
                            node = graph.nodes.get(first_of_this)
                            if node and last_of_other not in node.dependencies:
                                node.dependencies.append(last_of_other)

    def _find_task_id(self, graph: TaskGraph, requirement_name: str) -> str | None:
        """Find a task ID by requirement name."""
        for node in graph.nodes.values():
            if node.requirement_name == requirement_name:
                return node.id
        return None

    @staticmethod
    def _make_task_id(spec_name: str, req_name: str, index: int) -> str:
        """Generate a unique task ID."""
        slug = re.sub(r"[^a-z0-9]", "-", req_name.lower())[:30].strip("-")
        return f"{spec_name}--{slug}--{index:02d}"

    @staticmethod
    def _estimate_complexity(req: Requirement) -> str:
        """Estimate implementation complexity from requirement."""
        scenario_count = len(req.scenarios)
        if scenario_count >= 4:
            return "high"
        elif scenario_count >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _infer_domain(spec_name: str) -> str:
        """Infer domain from spec name."""
        if any(kw in spec_name for kw in ("firmware", "hal", "ecu", "display")):
            return "firmware"
        elif "mobile" in spec_name:
            return "mobile"
        elif "backend" in spec_name or "api" in spec_name:
            return "backend"
        return "firmware"  # Default
