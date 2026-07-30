#!/usr/bin/env bash
# ============================================================
# Codebase Memory MCP Integration Verification
# ============================================================
# Verifies the memory module structure, imports, configuration,
# and test suite without requiring the actual MCP server.
#
# Usage:
#     chmod +x scripts/verify-memory.sh
#     ./scripts/verify-memory.sh
# ============================================================

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Codebase Memory MCP — Verification                      ║"
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
check "config/memory.yaml exists" "test -f config/memory.yaml"
check "memory.yaml is valid YAML" "python3 -c 'import yaml; yaml.safe_load(open(\"config/memory.yaml\"))'"
check "memory.yaml has server section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/memory.yaml\")); assert \"server\" in d[\"memory\"]'"
check "memory.yaml has indexing section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/memory.yaml\")); assert \"indexing\" in d[\"memory\"]'"
check "memory.yaml has search section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/memory.yaml\")); assert \"search\" in d[\"memory\"]'"
check "memory.yaml has symbols section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/memory.yaml\")); assert \"symbols\" in d[\"memory\"]'"
check "memory.yaml has dependencies section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/memory.yaml\")); assert \"dependencies\" in d[\"memory\"]'"
check "memory.yaml has context_builder section" "python3 -c 'import yaml; d=yaml.safe_load(open(\"config/memory.yaml\")); assert \"context_builder\" in d[\"memory\"]'"
echo ""

# --- Step 2: Source Structure ---
echo "▸ Step 2: Module Structure"
echo ""
check "memory/__init__.py" "test -f src/factory/memory/__init__.py"
check "memory/types.py" "test -f src/factory/memory/types.py"
check "memory/client.py" "test -f src/factory/memory/client.py"
check "memory/indexer.py" "test -f src/factory/memory/indexer.py"
check "memory/search.py" "test -f src/factory/memory/search.py"
check "memory/symbols.py" "test -f src/factory/memory/symbols.py"
check "memory/dependencies.py" "test -f src/factory/memory/dependencies.py"
check "memory/context_builder.py" "test -f src/factory/memory/context_builder.py"
echo ""

# --- Step 3: Python Imports ---
echo "▸ Step 3: Import Verification"
echo ""
check "Import types" "PYTHONPATH=src python3 -c 'from factory.memory.types import Language, Symbol, SymbolKind, SearchResult, MemoryContext'"
check "Import client" "PYTHONPATH=src python3 -c 'from factory.memory.client import MemoryClient, ServerConfig, ServerUnavailableError'"
check "Import indexer" "PYTHONPATH=src python3 -c 'from factory.memory.indexer import RepositoryIndexer, IndexerConfig'"
check "Import search" "PYTHONPATH=src python3 -c 'from factory.memory.search import SemanticSearch, SearchConfig'"
check "Import symbols" "PYTHONPATH=src python3 -c 'from factory.memory.symbols import SymbolLookup'"
check "Import dependencies" "PYTHONPATH=src python3 -c 'from factory.memory.dependencies import DependencyLookup, LayerConfig'"
check "Import context_builder" "PYTHONPATH=src python3 -c 'from factory.memory.context_builder import ContextBuilder, ContextBuilderConfig'"
check "Import package (all exports)" "PYTHONPATH=src python3 -c 'from factory.memory import MemoryClient, SemanticSearch, SymbolLookup, DependencyLookup, ContextBuilder'"
echo ""

# --- Step 4: Type Validation ---
echo "▸ Step 4: Type Correctness"
echo ""
check "Language enum has CPP" "PYTHONPATH=src python3 -c 'from factory.memory.types import Language; assert Language.CPP.value == \"cpp\"'"
check "SymbolKind has INTERFACE" "PYTHONPATH=src python3 -c 'from factory.memory.types import SymbolKind; assert SymbolKind.INTERFACE.value == \"interface\"'"
check "LayerConfig validates dependencies" "PYTHONPATH=src python3 -c '
from factory.memory.dependencies import LayerConfig
lc = LayerConfig()
assert lc.is_valid_dependency(\"firmware/app/x.cpp\", \"firmware/middleware/y.h\") == True
assert lc.is_valid_dependency(\"firmware/drivers/x.cpp\", \"firmware/app/y.h\") == False
'"
check "ContextBuilder produces MemoryContext" "PYTHONPATH=src python3 -c '
from unittest.mock import MagicMock
from factory.memory.context_builder import ContextBuilder
from factory.memory.types import MemoryContext
client = MagicMock()
client.call_tool.return_value = {\"results\": []}
builder = ContextBuilder(client)
ctx = builder.build(\"test\")
assert isinstance(ctx, MemoryContext)
'"
check "Indexer detects language from extension" "PYTHONPATH=src python3 -c '
from pathlib import Path
from factory.memory.indexer import RepositoryIndexer
from factory.memory.types import Language
assert RepositoryIndexer._detect_language(Path(\"test.cpp\")) == Language.CPP
assert RepositoryIndexer._detect_language(Path(\"test.py\")) == Language.PYTHON
'"
echo ""

# --- Step 5: Graceful Degradation ---
echo "▸ Step 5: Graceful Degradation"
echo ""
check "Client reports unavailable without server" "PYTHONPATH=src python3 -c '
from factory.memory.client import MemoryClient, ServerConfig
c = MemoryClient(ServerConfig(command=\"nonexistent_xyz\"))
assert c.is_available() == False
'"
check "Search returns empty on server error" "PYTHONPATH=src python3 -c '
from unittest.mock import MagicMock
from factory.memory.search import SemanticSearch
from factory.memory.client import ServerUnavailableError
client = MagicMock()
client.call_tool.side_effect = ServerUnavailableError(\"down\")
s = SemanticSearch(client)
assert s.search(\"anything\") == []
'"
check "ContextBuilder returns empty on error" "PYTHONPATH=src python3 -c '
from unittest.mock import MagicMock
from factory.memory.context_builder import ContextBuilder
from factory.memory.client import ServerUnavailableError
client = MagicMock()
client.call_tool.side_effect = ServerUnavailableError(\"down\")
b = ContextBuilder(client)
ctx = b.build(\"test\")
assert ctx.content == \"\"
assert ctx.token_count == 0
'"
echo ""

# --- Step 6: Unit Tests ---
echo "▸ Step 6: Unit Tests"
echo ""
if command -v uv > /dev/null 2>&1; then
    check "All memory tests pass" "uv run pytest tests/unit/test_memory.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
else
    check "All memory tests pass" "PYTHONPATH=src python3 -m pytest tests/unit/test_memory.py -v --tb=short -q 2>&1 | tail -1 | grep -q 'passed'"
fi
echo ""

# --- Step 7: MCP Server (Optional) ---
echo "▸ Step 7: MCP Server Binary (optional)"
echo ""
if command -v npx > /dev/null 2>&1; then
    check "npx available" "npx --version"
    echo "  ℹ️  To test with real server: npx -y @anthropic/codebase-memory-mcp"
else
    echo "  ⚠️  npx not installed. MCP server requires Node.js + npx."
fi
echo ""

# --- Summary ---
echo "══════════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo "  Results: $PASS/$TOTAL passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
    echo "  ✅ All verification steps passed!"
    echo ""
    echo "  Next steps:"
    echo "    1. Install MCP server: npx -y @anthropic/codebase-memory-mcp"
    echo "    2. Index repository: factory memory index"
    echo "    3. Connect to LangGraph (future milestone)"
else
    echo "  ❌ $FAIL verification steps failed. Review above."
    exit 1
fi
echo "══════════════════════════════════════════════════════════"
