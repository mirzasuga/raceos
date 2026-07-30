# Factory Validation: "Why engine load indicator always 100%"

> End-to-end trace for a **bug investigation** task (not implementation).
> This exercises a different path through the factory than "implement X".

---

## Task Input

```
$ factory task "why engine load indicator always 100% show in display" --domain firmware
```

---

## Phase 1: Classification

### Agent: Orchestrator

```
Input:  "why engine load indicator always 100% show in display"
Domain: firmware

Classification:
  task_type: debugging        ← "why" = investigation/debugging
  complexity: MEDIUM          ← single symptom, likely single root cause
  target_agent: engineer
  requires_planning: false    ← debugging doesn't need spec generation
  requires_human_gate: false  ← MEDIUM + debugging = direct execution
  
Reasoning:
  - "why" signals investigation, not new implementation
  - "always 100%" = specific observable symptom (bug)
  - Single display field affected (scoped problem)
  - No architectural decision needed — this is a fix
```

**9Router call:** `route(task_type="classification")` → DeepSeek Chat, 32 tokens
**Cost:** $0.0001
**Duration:** ~2s

---

## Phase 2: Knowledge Validation

### Agent: Knowledge Agent

```
Checks:
  ✅ openspec/specs/display-dashboard/spec.md — exists
  ✅ openspec/specs/ecu-protocol/spec.md — exists
  ✅ openspec/specs/firmware-core/spec.md — exists
  ✅ No conflicting docs about load calculation
  ℹ️ display-dashboard spec mentions LOAD in vitals section
  ℹ️ ecu-protocol spec defines telemetry data fields

Status: OK
```

**Duration:** ~500ms (no LLM)

---

## Phase 3: Context Resolution

### Agent: Context Agent

```
Task type: debugging (firmware)
Requires: understanding of data flow ECU → display

TIER 1 (Principles — always):
  ├── .ai/steering.md (270 tokens)
  └── engineering-principles.md (1,580 tokens)
  Subtotal: 1,850 tokens

TIER 2 (Domain — display + ecu protocol):
  ├── openspec/specs/display-dashboard/spec.md (1,800 tokens)
  │   Key: "LOAD" is one of the vitals fields rendered with bar + state
  ├── openspec/specs/ecu-protocol/spec.md (1,000 tokens)
  │   Key: TelemetryData.load is parsed from ECU frame
  Subtotal: 2,800 tokens

TIER 3 (Target files — load data flow chain):
  ├── firmware/core/telemetry_data.h (400 tokens)
  │   Key: struct TelemetryData { uint8_t load; ... }
  ├── firmware/middleware/telemetry_parser.cpp (1,200 tokens)
  │   Key: parseFrame() extracts load from byte position
  ├── firmware/middleware/dashboard_view.cpp (2,100 tokens)
  │   Key: renderVitals() displays load value
  └── firmware/core/display_tokens.h (600 tokens)
  │   Key: kLoadWarnThreshold, kLoadDangerThreshold
  Subtotal: 4,300 tokens

TIER 4 (Codebase Memory):
  ├── "Juken5 protocol: load at byte offset 8, raw 0-255 maps to 0-100%" (200 tokens)
  ├── "DashboardView::renderVitals uses TelemetryData.load directly" (150 tokens)
  └── "Parser convention: raw byte → percentage via (raw * 100 / 255)" (180 tokens)
  Subtotal: 530 tokens

TOTAL: 9,480 tokens (within 12K budget ✅)

CACHE STATUS:
  tier1: HIT (cached from previous task 2 minutes ago)
  tier2: MISS (different domain combo: display + ecu)
  Effective I/O: ~250ms (tier1 cached, tier2+3+4 loaded fresh)
```

**Duration:** ~250ms (Tier 1 cached!)
**Cost:** $0.00

---

## Phase 4: Planning

### SKIPPED

```
Classification:
  complexity: MEDIUM
  requires_planning: false

Reason: Debugging tasks don't generate specs. The task is
"find and fix a bug" not "design a new capability."
Direct routing to execution.
```

**Duration:** 0s
**Cost:** $0.00

---

## Phase 5: Human Gate

### SKIPPED

```
Classification:
  requires_human_gate: false

Reason: MEDIUM complexity + debugging = no gate needed.
A bug fix doesn't need architectural approval.
```

**Duration:** 0s
**Cost:** $0.00

---

## Phase 6: Execution

### Agent: Engineering Agent (via OpenCode)

**9Router call:** `route(task_type="debugging")` → Claude Sonnet 4.6, 4096 tokens, temp=0.0
**Note:** Temperature 0.0 for debugging (deterministic analysis needed).

**OpenCode session:**

```
System prompt: context.tier1 + tier2 + tier3 + tier4 (9,480 tokens)
Constraints:
  - No dynamic allocation
  - No magic numbers
  - Host-native testable
  - Run tests after fix
  - Commit on factory/ branch
Tools: file (read/write), terminal (pio build/test), git, patch

--- Agent's Investigation ---

Step 1: Read telemetry_parser.cpp
  Found: parseFrame() extracts load from ECU byte
  Code: data.load = frame[8];
  Issue: raw byte (0-255) stored directly — NOT converted to percentage!

Step 2: Read dashboard_view.cpp
  Found: renderVitals() displays data.load as percentage
  Code: drawBar("LOAD", data.load, 100);  // assumes 0-100%
  
Step 3: Root Cause Identified
  ┌──────────────────────────────────────────────────────────┐
  │ ROOT CAUSE:                                               │
  │                                                          │
  │ ECU sends load as raw byte: 0-255                        │
  │ Parser stores raw byte: data.load = frame[8] (= 255)    │
  │ Dashboard treats it as percentage: drawBar(load, 100)    │
  │                                                          │
  │ When engine is at 100% load, ECU sends 255.              │
  │ But dashboard expects 0-100, so 255 shows as "100%"     │
  │ (actually clamped/overflowing).                          │
  │                                                          │
  │ When engine is at 50% load, ECU sends ~128.              │
  │ Dashboard shows 128% — which gets clamped to 100%.       │
  │ → That's why it ALWAYS shows 100%!                       │
  │                                                          │
  │ FIX: Convert raw byte to percentage in parser:           │
  │   data.load = (frame[8] * 100) / 255;                   │
  └──────────────────────────────────────────────────────────┘

Step 4: Apply fix
  File: firmware/middleware/telemetry_parser.cpp
  Before: data.load = frame[8];
  After:  data.load = static_cast<uint8_t>((frame[8] * 100) / 255);

Step 5: Add named constant
  File: firmware/core/board_config.h
  Added: constexpr uint8_t kEcuLoadRawMax = 255;
  
  File: firmware/middleware/telemetry_parser.cpp
  Updated: data.load = static_cast<uint8_t>((frame[8] * 100) / kEcuLoadRawMax);

Step 6: Add test
  File: firmware/tests/test_telemetry_parser.cpp
  Added:
    TEST(TelemetryParser, LoadConvertsRawToPercentage) {
      // 255 raw → 100%
      frame[8] = 255;
      parse(&data, frame);
      TEST_ASSERT_EQUAL(100, data.load);
      
      // 128 raw → 50%
      frame[8] = 128;
      parse(&data, frame);
      TEST_ASSERT_EQUAL(50, data.load);
      
      // 0 raw → 0%
      frame[8] = 0;
      parse(&data, frame);
      TEST_ASSERT_EQUAL(0, data.load);
    }

Step 7: Build + test
  $ pio build -e native → ✅
  $ pio test -e native → ✅ (16 passed, 0 failed — including new test)

Step 8: Commit
  $ git branch factory/fix-load-always-100
  $ git add -A
  $ git commit "[factory] fix: convert ECU load raw byte (0-255) to percentage (0-100)"
```

**Result:**
```
status: "success"
modified_files:
  - firmware/core/board_config.h
  - firmware/middleware/telemetry_parser.cpp
  - firmware/tests/test_telemetry_parser.cpp
output: "Root cause: raw byte not converted to percentage. Fixed in parser."
test_result: { passed: 16, failed: 0 }
git_branch: "factory/fix-load-always-100"
```

**Cost:** ~$0.14 (Claude Sonnet 4.6, ~11K input + 3K output)
**Duration:** ~35s

---

## Phase 7: Review

### Agent: Review Agent

**9Router call:** `route(task_type="review")` → Claude Sonnet 4, temp=0.0

**Review:**

```
Architecture Foundations:
  ✅ Layered: fix in middleware/ (correct — parser lives there)
  ✅ No #include violations
  ✅ No dynamic allocation
  ✅ No magic number (kEcuLoadRawMax named constant) 
  ✅ Host-native testable (test added, passes on native)
  ✅ No hardware dependency in fix

Spec compliance:
  ✅ ecu-protocol spec: parser produces percentage values
  ✅ display-dashboard spec: vitals expect 0-100% range

Code quality:
  ✅ Cast to uint8_t prevents overflow
  ✅ Test covers boundary values (0, 128, 255)
  ✅ Commit message is descriptive

Potential concern:
  ⚠️ (minor) Other telemetry fields (RPM, temp) — are they also raw?
  → This is a SEPARATE investigation. Not in scope of this fix.

Verdict: APPROVED (0 critical, 0 major, 1 minor note)
```

**Cost:** ~$0.06 (Claude Sonnet 4, ~5K input + 800 output)
**Duration:** ~4s

---

## Phase 8: Validation

### Agent: Validation Agent (TRUST EXECUTOR)

```
Trust check:
  execution.status == "success"  ✅
  output contains "passed"       ✅
  output contains "failed: 0"    ✅
  is_retry == False              ✅
  TRUST_EXECUTOR_TESTS == True   ✅

→ FAST PATH: Trust executor results
→ Skip redundant build+test re-run

Result: { 
  validation: { build_passed: true, tests_passed: true, trusted_from_executor: true }
}
```

**Cost:** $0.00
**Duration:** ~1s (no subprocess, just state check)

---

## Phase 9: Knowledge Update

### Agent: Knowledge Agent

```
Patterns stored in codebase-memory:
  1. "ECU raw byte conversion: (raw * 100) / 255 for percentage fields"
     files: [telemetry_parser.cpp, board_config.h]
     category: convention
     
  2. "kEcuLoadRawMax=255: named constant for ECU protocol raw range"
     files: [board_config.h]
     category: convention

  3. "Bug pattern: raw-to-percentage conversion missing in parser"
     files: [telemetry_parser.cpp]
     category: decision (fix rationale)

Cross-reference:
  - ecu-protocol spec now has known implementation detail (byte→pct mapping)
  
⚠️ Flag for human: Other fields (RPM, temp, duty) may have same raw-byte issue.
   Suggest follow-up investigation task.
```

**Cost:** $0.00
**Duration:** ~1s

---

## Complete Task Summary

| Phase | Agent | Duration | Cost | LLM Calls |
|---|---|---|---|---|
| Classification | Orchestrator | 2s | $0.0001 | 1 (DeepSeek) |
| Knowledge | Knowledge Agent | 0.5s | $0.00 | 0 |
| Context | Context Agent | **0.25s** | $0.00 | 0 (T1 cached) |
| Planning | **SKIPPED** | 0s | $0.00 | 0 |
| Human Gate | **SKIPPED** | 0s | $0.00 | 0 |
| Execution | Engineer | 35s | $0.14 | 1 (Claude) |
| Review | Reviewer | 4s | $0.06 | 1 (Claude) |
| Validation | Validator | **1s** | $0.00 | 0 (trusted) |
| Knowledge | Knowledge Agent | 1s | $0.00 | 0 |
| **TOTAL** | | **~44s** | **$0.20** | **3** |

---

## Comparison: Bug Fix vs Feature Implementation

| Metric | Feature (Engine Load Gauge) | Bug Fix (Always 100%) |
|---|---|---|
| Duration | 58s | **44s** |
| Cost | $0.56 | **$0.20** |
| LLM calls | 4-6 | **3** |
| Planning | GPT-5 (8s, $0.30) | **Skipped** |
| Human gate | Required | **Skipped** |
| Phases executed | 9/9 | **7/9** |
| Complexity | HIGH | MEDIUM |

**Key insight:** The factory correctly identifies debugging tasks as simpler workflows. No planning overhead, no human gate, cheaper model, faster completion. The architecture adapts to task type.

---

## Bottleneck Analysis

| Bottleneck | Severity | Analysis |
|---|---|---|
| **OpenCode investigation** (35s) | MEDIUM | Inherent — Claude needs to read files, reason about data flow, then fix. Cannot be parallelized. |
| **Review after obvious fix** | LOW | For a 1-line fix with clear root cause, review may be overkill. But defense-in-depth is the policy. |
| **Context for debugging** | NONE | Cache served Tier 1 instantly. Tier 3 loaded exact files needed. Tier 4 provided the crucial hint (byte 0-255 maps to percentage). |

### Surprising Finding: Tier 4 (Memory) Was Crucial

The codebase memory pattern "Juken5 protocol: load at byte offset 8, raw 0-255 maps to 0-100%" gave Claude the immediate context to understand the byte encoding. Without this, Claude would have needed to read the Juken5 protocol documentation (additional file reads + time).

**Tier 4 saved ~5-10s of investigation time** by providing the encoding convention upfront.

---

## Duplicated Responsibility Analysis

| Concern | Checked By | Redundant? |
|---|---|---|
| Fix correctness | OpenCode (runs test) + Validator (trusts executor) | **NO** — Validator just confirms, doesn't re-run |
| Architecture compliance | Engineering constraints + Review Agent | **ACCEPTABLE** — Constraints prevent, review catches |
| Named constants | Engineering constraints ("no magic numbers") + Review | **ACCEPTABLE** — Defense in depth |

**No actionable duplications found for bug-fix workflow.** The "trust executor" optimization already eliminated the main duplication (double test run).

---

## Improvement Suggestions

### 1. Auto-suggest related investigations (NEW)

**Observation:** Knowledge Agent flagged "other fields may have same raw-byte issue" but only as a note. This should automatically create a follow-up task suggestion.

**Suggestion:** After a bug fix, Knowledge Agent could emit:
```
suggested_follow_ups:
  - "Investigate: do RPM, temp, duty fields also need raw-to-percentage conversion?"
```

CLI would show this to the human:
```
✅ Task TASK-A1B2C3 completed.
💡 Suggested follow-up: "Investigate raw-to-percentage conversion for RPM, temp, duty fields"
   Run: factory task "..." --domain firmware
```

**Effort:** LOW (add `suggested_follow_ups` to knowledge_node output)
**Impact:** MEDIUM (catches systematic bugs early)

---

### 2. Debug-mode context: auto-include protocol docs (LOW effort)

**Observation:** For debugging tasks, the data flow from ECU → parser → display is critical. The context resolver could auto-detect "debugging" type and include the protocol spec even if the domain is "display."

**Current behavior:** Task says "display" → loads display spec. But the bug is in the PARSER (ecu layer).

**Suggestion:** For `task_type: debugging`, load BOTH the symptom domain spec (display) AND the data-source domain spec (ecu-protocol). The context resolver already does this correctly in this trace (loaded both display + ecu specs in Tier 2), so this is actually already working. No change needed.

---

### 3. Confidence-based review skipping (FUTURE consideration)

**Observation:** For a clear 1-line bug fix with test, the review step (4s + $0.06) provides little incremental value. The fix is obvious and tested.

**Suggestion:** Add a confidence signal from the executor:
```
execution.confidence: "high"  # clear root cause, test proves fix
```

If confidence is "high" AND fix is small (< 5 lines changed), reviewer could do a lighter check (or skip).

**Risk:** Skipping review risks missing subtle issues. Keep as defense-in-depth unless cost is a concern.

**Recommendation:** Do NOT implement this. $0.06 for review is cheap insurance. The current architecture is correct.

---

## Verdict: ✅ Architecture Handles Bug Fixes Efficiently

The factory correctly:
1. **Classified** "why" as debugging (not implementation)
2. **Skipped** planning and human gate (not needed for bug fix)
3. **Selected** Claude at temp=0 (deterministic debugging)
4. **Loaded** relevant context (display + ecu protocol + existing code + memory patterns)
5. **Found** root cause via systematic investigation
6. **Fixed** with proper constant naming (no magic numbers)
7. **Tested** with boundary values (0, 128, 255)
8. **Reviewed** without re-running tests (trust optimization working)
9. **Learned** the pattern for future tasks

**Total: 44 seconds, $0.20, zero human intervention needed.**

The architecture is validated for both feature implementation AND bug investigation workflows.
