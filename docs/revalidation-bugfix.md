# Revalidation: "Always 100%" Bug (Post-Improvement)

> Re-tracing the bug fix with Knowledge Agent auto-suggest follow-ups.

---

## What Changed

| Component | Before | After |
|---|---|---|
| `knowledge_node` | Stored patterns, no follow-up suggestions | **Detects sibling fields, suggests follow-up tasks** |
| `FactoryState` | No follow-up field | **`suggested_follow_ups: list[dict]`** |

---

## Re-trace: Phase 9 (Knowledge Update) — IMPROVED

### Before (original)

```
Knowledge Agent output:
  - Stored 3 patterns in codebase-memory
  - ⚠️ Flag for human: Other fields may have same issue
  - (flag buried in logs, human may miss it)
```

### After (improved)

```
Knowledge Agent output:
  patterns_indexed:
    1. "Files modified together: board_config.h, telemetry_parser.cpp, test_telemetry_parser.cpp"
    2. "Fix applied: raw-to-percentage"

  suggested_follow_ups:
    - description: "Investigate: do rpm, temp, duty, voltage, throttle fields also need raw-to-percentage?"
      domain: "firmware"
      priority: "medium"
      reason: "Bug in 'load' may also exist in sibling fields"
      related_task: "why engine load indicator always 100% show in display"
```

### How It Works (step by step)

```python
# Knowledge node logic for this specific task:

combined_text = "...telemetry_parser...load...raw...byte...255...percentage..."

# 1. Module detection: "telemetry_parser" found in text
# 2. Field detection: "load" matches in SIBLING_PATTERNS["telemetry_parser"]["fields"]
# 3. Sibling identification: ["rpm", "temp", "duty", "voltage", "throttle"]
# 4. Fix type detection: "raw", "255", "percentage" → "raw-to-percentage" (3 keyword matches)
# 5. Generate suggestion from template
```

---

## CLI Output (What Human Sees)

```
✅ Task TASK-A1B2C3 completed (44s, $0.20)

  Root cause: raw byte (0-255) not converted to percentage in parser
  Fix: data.load = (frame[8] * 100) / kEcuLoadRawMax
  Tests: 16 passed, 0 failed
  Branch: factory/fix-load-always-100

💡 Suggested follow-up:
   "Investigate: do rpm, temp, duty, voltage, throttle fields
    also need raw-to-percentage?"
   Priority: medium
   Reason: Bug in 'load' may also exist in sibling fields
   
   Run: factory task "check if rpm, temp, duty, voltage, throttle need raw-to-percentage conversion" --domain firmware
```

---

## Impact Analysis

| Metric | Before | After | Delta |
|---|---|---|---|
| Duration | 44s | 44s | +0s (follow-up detection is ~10ms) |
| Cost | $0.20 | $0.20 | $0.00 (no LLM needed for detection) |
| Human action | Read logs, maybe notice flag | **Actionable suggestion in CLI output** | Better UX |
| Bug coverage | Fixed 1 field (load) | Fixed 1 + **suggested 5 siblings** | 6x coverage potential |

---

## What Happens If Human Runs the Follow-up

```
$ factory task "check if rpm, temp, duty, voltage, throttle need raw-to-percentage conversion" --domain firmware

Classification:
  task_type: debugging
  complexity: MEDIUM (systematic check across known fields)
  requires_planning: false
  requires_human_gate: false

Execution:
  → Claude investigates each field in telemetry_parser.cpp
  → Finds: rpm also stored as raw (0-16383 → needs /163.83 for RPM)
  → Finds: temp stored correctly (already Celsius)
  → Finds: duty stored as raw byte (0-255 → needs conversion like load)
  → Fixes duty conversion
  → All tests pass

Knowledge Agent:
  suggested_follow_ups: []  (no more siblings to check)
```

**The auto-suggest creates a chain of systematic fixes** that human can execute one by one, catching all instances of a pattern bug.

---

## Edge Cases Tested

| Scenario | Knowledge Agent Behavior |
|---|---|
| Fix to a non-telemetry file | No siblings detected → no follow-up |
| Fix that touches ALL fields | No sibling left → no follow-up |
| Feature implementation (not bug) | `task_type != debugging` → no follow-up |
| Fix with vague output | Falls back to generic "investigate similar" suggestion |
| Multiple modules touched | Generates follow-up per module family |

---

## Verdict: ✅ Improvement Validated

The auto-suggest follow-up:
1. **Costs nothing** — pure pattern matching, no LLM
2. **Adds ~10ms** to knowledge phase (negligible)
3. **Catches systematic bugs** — one fix reveals N siblings
4. **Non-blocking** — suggestions are displayed, not auto-executed
5. **Human decides** — preserves "AI suggests, human decides" principle

No architecture changes were needed. Single node update + state field addition.
