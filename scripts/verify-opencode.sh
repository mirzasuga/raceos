#!/usr/bin/env bash
# ============================================================
# OpenCode Integration Verification Script
# ============================================================
# Run this after implementing the executor to verify everything
# is connected correctly.
#
# Usage:
#     chmod +x scripts/verify-opencode.sh
#     ./scripts/verify-opencode.sh
# ============================================================

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  OpenCode Integration Verification                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

check() {
    local description="$1"
    local command="$2"

    printf "  %-50s " "$description"
    if eval "$command" > /dev/null 2>&1; then
        echo "✅ PASS"
        PASS=$((PASS + 1))
    else
        echo "❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
}

# --- Step 1: Prerequisites ---
echo "▸ Step 1: Prerequisites"
echo ""
check "Python ≥ 3.11 available" "python3 -c 'import sys; assert sys.version_info >= (3, 11)'"
check "uv available" "uv --version"
check "Node.js available" "node --version"
echo ""

# --- Step 2: Configuration ---
echo "▸ Step 2: Configuration Files"
echo ""
check "config/opencode.json exists" "test -f config/opencode.json"
check "config/opencode.json is valid JSON" "python3 -c 'import json; json.load(open(\"config/opencode.json\"))'"
check "config/models.yaml exists" "test -f config/models.yaml"
check "config/factory.yaml exists" "test -f config/factory.yaml"
check "config/mcp-servers.yaml exists" "test -f config/mcp-servers.yaml"
check ".env.example exists" "test -f .env.example"
echo ""

# --- Step 3: Source Structure ---
echo "▸ Step 3: Executor Source Structure"
echo ""
check "executor/__init__.py exists" "test -f src/factory/executor/__init__.py"
check "executor/client.py exists" "test -f src/factory/executor/client.py"
check "executor/contracts.py exists" "test -f src/factory/executor/contracts.py"
check "executor/session.py exists" "test -f src/factory/executor/session.py"
check "executor/tools.py exists" "test -f src/factory/executor/tools.py"
check "adapters/base.py exists" "test -f src/factory/executor/adapters/base.py"
check "adapters/firmware.py exists" "test -f src/factory/executor/adapters/firmware.py"
check "adapters/mobile.py exists" "test -f src/factory/executor/adapters/mobile.py"
check "adapters/backend.py exists" "test -f src/factory/executor/adapters/backend.py"
echo ""

# --- Step 4: Python Imports ---
echo "▸ Step 4: Python Import Verification"
echo ""
check "Import contracts" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.contracts import ExecutionRequest, ExecutionResult'"
check "Import session" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.session import Session, SessionConfig'"
check "Import client" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.client import OpenCodeClient'"
check "Import tools" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.tools import ALL_TOOLS, get_tools_for_operation'"
check "Import adapters" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.adapters import get_adapter, list_domains'"
check "Firmware adapter loads" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.adapters import get_adapter; a = get_adapter(\"firmware\"); assert a.name == \"firmware\"'"
check "Mobile adapter loads" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.adapters import get_adapter; a = get_adapter(\"mobile\"); assert a.name == \"mobile\"'"
check "Backend adapter loads" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.adapters import get_adapter; a = get_adapter(\"backend\"); assert a.name == \"backend\"'"
echo ""

# --- Step 5: Tool Definitions ---
echo "▸ Step 5: Tool Definitions"
echo ""
check "4 tools registered" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.tools import ALL_TOOLS; assert len(ALL_TOOLS) == 4'"
check "File tool has constraints" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.tools import FILE_TOOL; assert len(FILE_TOOL.constraints) > 0'"
check "Terminal tool has blocked cmds" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.tools import TERMINAL_TOOL; assert any(\"rm\" in c for c in TERMINAL_TOOL.constraints)'"
check "Git tool blocks main" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.tools import GIT_TOOL; assert any(\"main\" in c.lower() for c in GIT_TOOL.constraints)'"
check "Patch tool validates" "cd . && PYTHONPATH=src python3 -c 'from factory.executor.tools import PATCH_TOOL; assert any(\"validate\" in c.lower() for c in PATCH_TOOL.constraints)'"
echo ""

# --- Step 6: Unit Tests ---
echo "▸ Step 6: Unit Tests"
echo ""
if command -v uv > /dev/null 2>&1; then
    check "pytest passes" "uv run pytest tests/unit/test_executor.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
else
    check "pytest passes" "PYTHONPATH=src python3 -m pytest tests/unit/test_executor.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
fi
echo ""

# --- Step 7: OpenCode Binary (Optional) ---
echo "▸ Step 7: OpenCode Binary (optional)"
echo ""
if command -v opencode > /dev/null 2>&1; then
    check "opencode binary found" "opencode --version"
    check "opencode --help works" "opencode --help"
else
    echo "  ⚠️  opencode binary not installed (optional for unit tests)"
    echo "  Install: npm install -g opencode"
fi
echo ""

# --- Summary ---
echo "══════════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo "  Results: $PASS/$TOTAL passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
    echo "  ✅ All verification steps passed!"
else
    echo "  ❌ $FAIL verification steps failed. Review above."
    exit 1
fi
echo "══════════════════════════════════════════════════════════"
