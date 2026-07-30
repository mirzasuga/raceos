"""
OpenSpec Data Types.

Structured representations of parsed spec documents, requirements,
scenarios, acceptance criteria, and task graphs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# --- Enums ---


class KeywordStrength(Enum):
    """RFC 2119 keyword strength levels."""

    MANDATORY = "mandatory"        # SHALL, MUST, REQUIRED
    RECOMMENDED = "recommended"    # SHOULD, RECOMMENDED
    OPTIONAL = "optional"          # MAY, OPTIONAL
    NEGATIVE = "negative"          # SHALL NOT, MUST NOT


class Priority(Enum):
    """Task priority derived from keyword strength."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CRITICAL = "critical"


class ValidationSeverity(Enum):
    """Severity of a validation finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class TaskStatus(Enum):
    """Status of a task in the task graph."""

    PENDING = "pending"
    READY = "ready"          # All dependencies met
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"      # Dependency not met


class CriterionSource(Enum):
    """Where an acceptance criterion was extracted from."""

    THEN_CLAUSE = "then_clause"        # From scenario THEN/AND
    SHALL_STATEMENT = "shall_statement"  # From requirement text
    NEGATIVE = "negative"               # From SHALL NOT
    MANUAL = "manual"                   # Manually added


# --- Core Spec Types ---


@dataclass
class ScenarioStep:
    """A single step in a scenario (GIVEN/WHEN/THEN/AND)."""

    keyword: str              # GIVEN | WHEN | THEN | AND
    text: str                 # The step content
    line_number: int = 0


@dataclass
class Scenario:
    """A behavioral scenario (Given/When/Then structure)."""

    name: str
    steps: list[ScenarioStep] = field(default_factory=list)
    line_number: int = 0

    @property
    def given_steps(self) -> list[ScenarioStep]:
        return [s for s in self.steps if s.keyword in ("GIVEN", "AND") and self._is_after(s, "GIVEN")]

    @property
    def when_steps(self) -> list[ScenarioStep]:
        return [s for s in self.steps if s.keyword in ("WHEN", "AND") and self._is_after(s, "WHEN")]

    @property
    def then_steps(self) -> list[ScenarioStep]:
        return [s for s in self.steps if s.keyword in ("THEN", "AND") and self._is_after(s, "THEN")]

    def _is_after(self, step: ScenarioStep, keyword: str) -> bool:
        """Check if a step belongs to a keyword section."""
        # Simple heuristic: AND belongs to the most recent GIVEN/WHEN/THEN
        idx = self.steps.index(step)
        for i in range(idx, -1, -1):
            if self.steps[i].keyword in ("GIVEN", "WHEN", "THEN"):
                return self.steps[i].keyword == keyword
        return False

    @property
    def has_given_when_then(self) -> bool:
        """Check if scenario has valid G/W/T structure."""
        keywords = [s.keyword for s in self.steps if s.keyword in ("GIVEN", "WHEN", "THEN")]
        return "GIVEN" in keywords and "WHEN" in keywords and "THEN" in keywords


@dataclass
class Requirement:
    """A single requirement within a spec."""

    name: str
    description: str                          # The SHALL/SHOULD/MAY statement
    keyword_strength: KeywordStrength = KeywordStrength.MANDATORY
    scenarios: list[Scenario] = field(default_factory=list)
    line_number: int = 0
    references: list[str] = field(default_factory=list)  # ADRs, other specs

    @property
    def priority(self) -> Priority:
        """Derive priority from keyword strength."""
        mapping = {
            KeywordStrength.MANDATORY: Priority.HIGH,
            KeywordStrength.RECOMMENDED: Priority.MEDIUM,
            KeywordStrength.OPTIONAL: Priority.LOW,
            KeywordStrength.NEGATIVE: Priority.HIGH,
        }
        return mapping.get(self.keyword_strength, Priority.MEDIUM)


@dataclass
class Spec:
    """A complete OpenSpec document."""

    name: str                                 # Spec domain name (e.g., "firmware-core")
    file_path: str                            # Relative path to spec.md
    purpose: str = ""                         # Purpose section content
    requirements: list[Requirement] = field(default_factory=list)
    raw_content: str = ""                     # Full markdown content

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def scenario_count(self) -> int:
        return sum(len(r.scenarios) for r in self.requirements)


# --- Acceptance Criteria ---


@dataclass
class AcceptanceCriterion:
    """A single acceptance criterion derived from a spec."""

    text: str                                 # The criterion statement
    source: CriterionSource
    requirement_name: str                     # Parent requirement
    spec_name: str                            # Parent spec
    scenario_name: str = ""                   # Source scenario (if from THEN)
    testable: bool = True                     # Can be verified automatically
    test_file: str = ""                       # Corresponding test file (if found)
    satisfied: bool = False                   # Whether criterion is met


@dataclass
class AcceptanceReport:
    """Collection of acceptance criteria for a task."""

    criteria: list[AcceptanceCriterion] = field(default_factory=list)
    spec_name: str = ""
    total: int = 0
    satisfied: int = 0
    unsatisfied: int = 0

    def update_counts(self) -> None:
        self.total = len(self.criteria)
        self.satisfied = sum(1 for c in self.criteria if c.satisfied)
        self.unsatisfied = self.total - self.satisfied

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.satisfied / self.total


# --- Task Graph ---


@dataclass
class TaskNode:
    """A single task in the dependency graph."""

    id: str                                   # Unique task ID
    title: str                                # Human-readable title
    requirement_name: str                     # Source requirement
    spec_name: str                            # Source spec
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)  # Task IDs this depends on
    acceptance_criteria: list[str] = field(default_factory=list)
    estimated_complexity: str = "medium"      # low | medium | high
    domain: str = "firmware"
    target_files: list[str] = field(default_factory=list)


@dataclass
class TaskGraph:
    """Dependency graph of tasks derived from specs."""

    nodes: dict[str, TaskNode] = field(default_factory=dict)  # id → TaskNode
    spec_source: str = ""                     # Which spec(s) this graph was derived from

    def add_node(self, node: TaskNode) -> None:
        self.nodes[node.id] = node

    @property
    def ready_tasks(self) -> list[TaskNode]:
        """Tasks whose dependencies are all completed."""
        return [
            node for node in self.nodes.values()
            if node.status == TaskStatus.PENDING
            and all(
                self.nodes.get(dep, TaskNode(id="", title="", requirement_name="", spec_name="")).status == TaskStatus.COMPLETED
                for dep in node.dependencies
            )
        ]

    @property
    def execution_order(self) -> list[TaskNode]:
        """Topological sort of tasks (respecting dependencies)."""
        visited: set[str] = set()
        order: list[TaskNode] = []

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            node = self.nodes.get(node_id)
            if node:
                for dep in node.dependencies:
                    visit(dep)
                order.append(node)

        for node_id in self.nodes:
            visit(node_id)

        return order

    @property
    def total_tasks(self) -> int:
        return len(self.nodes)

    @property
    def completed_tasks(self) -> int:
        return sum(1 for n in self.nodes.values() if n.status == TaskStatus.COMPLETED)


# --- Validation ---


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: ValidationSeverity
    message: str
    spec_name: str
    requirement_name: str = ""
    scenario_name: str = ""
    line_number: int = 0
    suggestion: str = ""


@dataclass
class ValidationReport:
    """Complete validation report for a spec or set of specs."""

    issues: list[ValidationIssue] = field(default_factory=list)
    specs_checked: int = 0
    requirements_checked: int = 0
    scenarios_checked: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def is_valid(self) -> bool:
        """Spec is valid if there are no errors (warnings are OK)."""
        return len(self.errors) == 0
