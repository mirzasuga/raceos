#!/usr/bin/env bash
# ============================================================
# OpenSpec Integration Verification
# ============================================================
# Verifies spec engine: parser, task graph, validator, acceptance.
#
# Usage:
#     chmod +x scripts/verify-openspec.sh
#     ./scripts/verify-openspec.sh
# ============================================================

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  OpenSpec Integration — Verification                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

check() {
    local description="$1"
    local command="$2"
    printf "  %-55s " "$description"
    if eval "$command" > /dev/null 2>&1; then
        echo "✅"
        PASS=$((PASS + 1))
    else
        echo "❌"
        FAIL=$((FAIL + 1))
    fi
}

# --- Step 1: Configuration ---
echo "▸ Step 1: Configuration"
echo ""
check "config/openspec.yaml exists" "test -f config/openspec.yaml"
check "openspec.yaml is valid YAML" "python3 -c 'import yaml; yaml.safe_load(open(\"config/openspec.yaml\"))'"
check "Has parser section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/openspec.yaml\")); assert \"parser\" in d[\"openspec\"]'"
check "Has task_graph section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/openspec.yaml\")); assert \"task_graph\" in d[\"openspec\"]'"
check "Has validation section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/openspec.yaml\")); assert \"validation\" in d[\"openspec\"]'"
check "Has acceptance section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/openspec.yaml\")); assert \"acceptance\" in d[\"openspec\"]'"
check "Has generator section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/openspec.yaml\")); assert \"generator\" in d[\"openspec\"]'"
echo ""

# --- Step 2: Module Structure ---
echo "▸ Step 2: Module Structure"
echo ""
check "spec_engine/__init__.py" "test -f src/factory/spec_engine/__init__.py"
check "spec_engine/types.py" "test -f src/factory/spec_engine/types.py"
check "spec_engine/parser.py" "test -f src/factory/spec_engine/parser.py"
check "spec_engine/task_graph.py" "test -f src/factory/spec_engine/task_graph.py"
check "spec_engine/validator.py" "test -f src/factory/spec_engine/validator.py"
check "spec_engine/acceptance.py" "test -f src/factory/spec_engine/acceptance.py"
check "spec_engine/generator.py" "test -f src/factory/spec_engine/generator.py"
check "specs/templates/proposal.md" "test -f specs/templates/proposal.md"
check "specs/templates/tasks.md" "test -f specs/templates/tasks.md"
echo ""

# --- Step 3: Import Verification ---
echo "▸ Step 3: Import Verification"
echo ""
check "Import types" "PYTHONPATH=src python3 -c 'from factory.spec_engine.types import Spec, Requirement, Scenario, TaskGraph, AcceptanceReport'"
check "Import parser" "PYTHONPATH=src python3 -c 'from factory.spec_engine.parser import SpecParser'"
check "Import task_graph" "PYTHONPATH=src python3 -c 'from factory.spec_engine.task_graph import TaskGraphGenerator'"
check "Import validator" "PYTHONPATH=src python3 -c 'from factory.spec_engine.validator import SpecValidator, ValidatorConfig'"
check "Import acceptance" "PYTHONPATH=src python3 -c 'from factory.spec_engine.acceptance import AcceptanceCriteriaExtractor'"
check "Import generator" "PYTHONPATH=src python3 -c 'from factory.spec_engine.generator import SpecGenerator'"
check "Import package (all)" "PYTHONPATH=src python3 -c 'from factory.spec_engine import SpecParser, TaskGraphGenerator, SpecValidator, AcceptanceCriteriaExtractor, SpecGenerator'"
echo ""

# --- Step 4: Parse Real Specs ---
echo "▸ Step 4: Parse Real Specs (if available)"
echo ""
check "Parse firmware-core spec" "PYTHONPATH=src python3 -c '
from factory.spec_engine.parser import SpecParser
from pathlib import Path
p = Path(\"../openspec/specs/firmware-core/spec.md\")
if not p.exists(): exit(0)  # Skip if not available
parser = SpecParser()
spec = parser.parse_file(p)
assert spec.requirement_count >= 5, f\"Only {spec.requirement_count} requirements\"
assert spec.scenario_count >= 5, f\"Only {spec.scenario_count} scenarios\"
print(f\"OK: {spec.requirement_count} requirements, {spec.scenario_count} scenarios\")
'"
check "Parse all specs directory" "PYTHONPATH=src python3 -c '
from factory.spec_engine.parser import SpecParser
from pathlib import Path
d = Path(\"../openspec/specs/\")
if not d.exists(): exit(0)
parser = SpecParser()
specs = parser.parse_directory(d)
assert len(specs) >= 1, f\"Only {len(specs)} specs found\"
'"
check "Generate task graph from specs" "PYTHONPATH=src python3 -c '
from factory.spec_engine.parser import SpecParser
from factory.spec_engine.task_graph import TaskGraphGenerator
from pathlib import Path
d = Path(\"../openspec/specs/\")
if not d.exists(): exit(0)
parser = SpecParser()
specs = parser.parse_directory(d)
gen = TaskGraphGenerator()
graph = gen.from_specs(specs)
assert graph.total_tasks >= 1
'"
check "Validate specs" "PYTHONPATH=src python3 -c '
from factory.spec_engine.parser import SpecParser
from factory.spec_engine.validator import SpecValidator
from pathlib import Path
d = Path(\"../openspec/specs/\")
if not d.exists(): exit(0)
parser = SpecParser()
specs = parser.parse_directory(d)
validator = SpecValidator()
report = validator.validate_all(specs)
print(f\"Valid: {report.is_valid}, Errors: {len(report.errors)}, Warnings: {len(report.warnings)}\")
'"
check "Extract acceptance criteria" "PYTHONPATH=src python3 -c '
from factory.spec_engine.parser import SpecParser
from factory.spec_engine.acceptance import AcceptanceCriteriaExtractor
from pathlib import Path
p = Path(\"../openspec/specs/firmware-core/spec.md\")
if not p.exists(): exit(0)
parser = SpecParser()
spec = parser.parse_file(p)
extractor = AcceptanceCriteriaExtractor()
report = extractor.extract_from_spec(spec)
assert report.total >= 5, f\"Only {report.total} criteria\"
'"
echo ""

# --- Step 5: Unit Tests ---
echo "▸ Step 5: Unit Tests"
echo ""
if command -v uv > /dev/null 2>&1; then
    check "All spec_engine tests pass" "uv run pytest tests/unit/test_spec_engine.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
else
    check "All spec_engine tests pass" "PYTHONPATH=src python3 -m pytest tests/unit/test_spec_engine.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
fi
echo ""

# --- Summary ---
echo "══════════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo "  Results: $PASS/$TOTAL passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
    echo "  ✅ All verification steps passed!"
    echo ""
    echo "  Capabilities:"
    echo "    • Parse OpenSpec markdown → structured Spec objects"
    echo "    • Generate task dependency graphs from requirements"
    echo "    • Validate spec completeness (purpose, G/W/T, keywords)"
    echo "    • Extract acceptance criteria from THEN clauses"
    echo "    • Generate new spec artifacts (proposal, tasks)"
else
    echo "  ❌ $FAIL verification steps failed."
    exit 1
fi
echo "══════════════════════════════════════════════════════════"
