# Factory Validation: Wiring Diagram Question (Hardware + Research)

> End-to-end trace for a **knowledge/research question** — not a code task.
> This is a multi-domain query that touches hardware, architecture, and product.
> The user asks in Indonesian (natural for RaceOS team).

---

## Task Input

```
$ factory task "Bagaimana wiring diagram untuk racepanel jika posisi display berada di dekat stang dan ecu berada dibawah jok, sedangkan protocol ecu ke stm32 menggunakan uart" --domain hardware
```

**Translation:** "How should the wiring diagram for racepanel look if the display is near the handlebars and the ECU is under the seat, given the ECU-to-STM32 protocol uses UART?"

---

## Phase 1: Classification

### Agent: Orchestrator

```
Input:  "Bagaimana wiring diagram untuk racepanel..."
Domain: hardware (explicitly specified)

Classification:
  task_type: documentation     ← "Bagaimana" (how) = explanation/documentation
  complexity: MEDIUM           ← Multi-concern (physical layout + protocol + wiring)
                                  but no new architecture decision needed
  target_agent: hardware       ← domain=hardware + "wiring diagram"
  requires_planning: false     ← This is a question, not an implementation
  requires_human_gate: false   ← MEDIUM + documentation = no gate

Reasoning:
  - "Bagaimana" (how) = requesting explanation/diagram
  - "wiring diagram" = hardware engineering domain
  - Physical placement context (stang/jok) = cable routing concern
  - "protocol UART" = existing interface (ISerialPort, already implemented)
  - NOT a coding task — no files to modify
  - NOT architecture — UART decision already made (ADR-0007, ADR-0017)
```

**9Router call:** `route(task_type="classification")` → DeepSeek Chat, 32 tokens
**Cost:** $0.0001
**Duration:** ~2s

---

## Phase 2: Knowledge Validation

### Agent: Knowledge Agent

```
Checks:
  ✅ hardware/power-architecture.md — exists
  ✅ hardware/inventory.md — exists (BOM with connectors)
  ✅ hardware/stm32f411/ — exists (MCU pinout)
  ✅ hardware/display-ili9341/ — exists (display pinout)
  ✅ adr/ADR-0007-uart-rx-strategy.md — exists
  ✅ adr/ADR-0017-serial-transport-hal.md — exists
  ✅ openspec/specs/hal-serial-port/spec.md — exists
  ℹ️ No existing wiring diagram document found
  ℹ️ No cable length/routing documentation exists yet

Status: OK (no conflicts, but gap identified: no wiring docs)
```

**Duration:** ~500ms

---

## Phase 3: Context Resolution

### Agent: Context Agent

```
Task type: documentation (hardware domain)
Requires: hardware pinout, power architecture, UART spec, physical constraints

TIER 1 (Principles — always):
  ├── .ai/steering.md (270 tokens)
  └── engineering-principles.md (1,580 tokens)
  Subtotal: 1,850 tokens

TIER 2 (Domain — hardware + UART):
  ├── hardware/power-architecture.md (1,100 tokens)
  │   Key: 5V rail, 3.3V regulator, power routing
  ├── hardware/inventory.md (extract: connectors section, 600 tokens)
  │   Key: CP2102 USB-serial, JST connectors, wire gauge
  ├── adr/ADR-0017-serial-transport-hal.md (extract: 500 tokens)
  │   Key: UART1 on PA9/PA10, 57600 baud, ISerialPort interface
  └── openspec/specs/hal-serial-port/spec.md (extract: 400 tokens)
  │   Key: Serial1 for ECU link, configurable baud
  Subtotal: 2,600 tokens

TIER 3 (Target files — hardware reference):
  ├── hardware/stm32f411/pinout (if exists, ~800 tokens)
  │   Key: PA9=UART1_TX, PA10=UART1_RX, SPI1 for display
  ├── hardware/display-ili9341/connections.md (if exists, ~500 tokens)
  │   Key: SPI pins, backlight, CS pin
  └── firmware/core/board_config.h (400 tokens)
      Key: pin assignments, baud rate constants
  Subtotal: 1,700 tokens

TIER 4 (Codebase Memory):
  ├── "CP2102 TXD → PA10, GND → GND, no VCC connection" (150 tokens)
  ├── "Display SPI: SCK=PA5, MOSI=PA7, CS=PA4, DC=PA3, RST=PA2" (120 tokens)
  └── "UART baud: 57600 for ECU, 115200 for USB CDC debug" (100 tokens)
  Subtotal: 370 tokens

TOTAL: 6,520 tokens (well within 12K budget ✅)

CACHE STATUS:
  tier1: HIT (cached from previous task)
  tier2: MISS (hardware domain combination not cached before)
```

**Duration:** ~300ms (Tier 1 cached)
**Cost:** $0.00

---

## Phase 4: Planning

### SKIPPED

```
requires_planning: false
Reason: This is a documentation/explanation task, not implementation.
No spec or ADR generation needed — the user wants an answer.
```

---

## Phase 5: Human Gate

### SKIPPED

```
requires_human_gate: false
Reason: MEDIUM complexity documentation request. No destructive action.
```

---

## Phase 6: Execution

### Agent: Hardware Engineer (via OpenCode)

**9Router call:** `route(task_type="documentation")` → **Gemini 2.5 Pro**, 8192 tokens, temp=0.3

**Note:** Documentation task routes to Gemini (long context + excellent diagram generation). Not Claude.

**OpenCode session:**

```
System prompt: context.tier1 + tier2 + tier3 + tier4 (6,520 tokens)
Constraints:
  - Base on existing hardware docs (don't invent new components)
  - Reference actual pin assignments from board_config.h
  - Consider cable length (stang to jok = ~1-1.5m on motorcycle)
  - Use ASCII diagram format (no binary images)
  - Language: Indonesian (match user's language)
Tools: file (read-only for this task — no edits needed)

--- Agent's Response ---

Generated content:

# Wiring Diagram: RacePanel (Stang → Jok)

## Physical Layout

```text
┌─────────────────────────────────────┐
│          AREA STANG (Handlebar)      │
│                                     │
│  ┌───────────────┐  ┌───────────┐  │
│  │  STM32F411    │  │ ILI9341   │  │
│  │  (Black Pill) │──│ Display   │  │
│  │               │  │ 3.2" SPI  │  │
│  └───────┬───────┘  └───────────┘  │
│          │                          │
│          │ UART1 (PA9/PA10)         │
│          │ + GND + 5V              │
│          │                          │
└──────────┼──────────────────────────┘
           │
           │ ~1.2m shielded cable
           │ (4 wire: TX, RX, GND, 5V)
           │
┌──────────┼──────────────────────────┐
│          │                          │
│          ▼                          │
│  ┌───────────────┐                  │
│  │  ECU Juken 5  │                  │
│  │  (UART out)   │                  │
│  └───────────────┘                  │
│                                     │
│          AREA JOK (Under Seat)      │
└─────────────────────────────────────┘
```

## Koneksi Detail

### STM32 ↔ Display (SPI, kabel pendek ~10cm)

| STM32 Pin | Display Pin | Fungsi |
|---|---|---|
| PA5 | SCK | SPI Clock |
| PA7 | MOSI | SPI Data |
| PA4 | CS | Chip Select |
| PA3 | DC | Data/Command |
| PA2 | RST | Reset |
| PB10 | BL | Backlight (GPIO) |
| 3.3V | VCC | Power |
| GND | GND | Ground |

### STM32 ↔ ECU (UART, kabel panjang ~1.2m)

| STM32 Pin | ECU Pin | Fungsi |
|---|---|---|
| PA10 (RX) | TXD | ECU mengirim data → STM32 menerima |
| PA9 (TX) | RXD | STM32 mengirim command → ECU (jika diperlukan) |
| GND | GND | Ground reference (WAJIB) |

⚠️ **JANGAN hubungkan VCC ECU ke STM32** — power terpisah.

### Power

| Source | Target | Via |
|---|---|---|
| 12V motor | 5V regulator (di area stang) | Kabel power dari baterai |
| 5V reg | STM32 (5V pin) | Direct |
| STM32 3.3V | Display VCC | Dari regulator onboard STM32 |

## Pertimbangan Kabel Panjang (UART 1.2m)

1. **Baud rate 57600** — aman untuk 1.2m pada kabel shielded
2. **Gunakan twisted pair** untuk TX/RX (noise rejection)
3. **GND terpisah** — jangan berbagi ground wire dengan power
4. **Shield** — hubungkan shield ke GND di satu ujung saja (STM32 side)
5. **Konektor** — gunakan JST-XH 4-pin (disconnect-able saat servis)

## Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Noise pada UART (mesin, ignition) | Twisted pair + shielded cable |
| Putus kabel saat vibrasi | Strain relief + JST connector |
| Ground loop | Single-point grounding di STM32 |
| Voltage spike dari ECU | Series resistor 1KΩ pada RX line |

---
```

**Result:**
```
status: "success"
modified_files: []              ← No files modified! This is documentation output.
output: [the wiring diagram content above]
```

**Cost:** ~$0.08 (Gemini 2.5 Pro, ~8K input + 2K output — cheap!)
**Duration:** ~12s

---

## Phase 7: Review

### Agent: Review Agent

**9Router call:** `route(task_type="review")` → Claude Sonnet 4, temp=0.0

**Review:**

```
Technical accuracy check:
  ✅ Pin assignments match board_config.h (PA5/PA7/PA4/PA3/PA2 for SPI)
  ✅ UART pins correct (PA9=TX, PA10=RX — matches ADR-0017)
  ✅ Baud rate 57600 matches existing firmware configuration
  ✅ Power architecture matches hardware/power-architecture.md
  ✅ "No VCC from ECU" matches README.md mock-ecu instructions
  ✅ ILI9341 SPI connections match hardware/display-ili9341/

Physical considerations:
  ✅ 1.2m reasonable for stang-to-jok on motorcycle
  ✅ Twisted pair recommendation for noise is correct
  ✅ Single-point grounding is good EMC practice
  ✅ JST-XH connector is appropriate (vibration-resistant)

Minor suggestions:
  ℹ️ Could add wire gauge recommendation (22-24 AWG for signal, 20 AWG for power)
  ℹ️ Could mention waterproofing for outdoor/rain exposure

Verdict: APPROVED (factually correct, matches all existing docs)
```

**Cost:** ~$0.05 (Claude Sonnet 4, ~4K input + 600 output)
**Duration:** ~4s

---

## Phase 8: Validation

### Agent: Validation Agent (TRUST EXECUTOR)

```
Special case: documentation task — no code modified, no tests to run.

Check:
  execution.status == "success"  ✅
  modified_files == []           ✅ (no code changed)
  This is documentation output, not code.

Validation approach for non-code tasks:
  → Verify output is non-empty ✅
  → Verify review verdict == "approved" ✅
  → No build/test needed (nothing to compile)

Result: { validation: { build_passed: true, tests_passed: true, trusted_from_executor: true } }
```

**Cost:** $0.00
**Duration:** ~1s

---

## Phase 9: Knowledge Update

### Agent: Knowledge Agent

```
Patterns indexed:
  1. "Wiring: STM32 at stang, ECU at jok, UART 1.2m shielded cable"
     category: hardware_convention
  2. "UART long cable: twisted pair + shield + 57600 baud safe for 1.2m"
     category: hardware_decision
  3. "Power: separate power domains, no VCC sharing between ECU and STM32"
     category: hardware_convention

Follow-up suggestions:
  suggested_follow_ups: []

  Reason: No sibling pattern detected. This is a one-off documentation
  question about physical layout. No code was changed, no "family of
  similar bugs" to investigate.

Gap identified:
  ⚠️ No persistent wiring diagram document exists in hardware/.
  → Suggest: human could save this output to hardware/wiring-diagram.md
```

**Cost:** $0.00
**Duration:** ~1s

---

## Complete Task Summary

| Phase | Agent | Duration | Cost | LLM Calls |
|---|---|---|---|---|
| Classification | Orchestrator | 2s | $0.0001 | 1 (DeepSeek) |
| Knowledge | Knowledge Agent | 0.5s | $0.00 | 0 |
| Context | Context Agent | 0.3s | $0.00 | 0 (T1 cached) |
| Planning | **SKIPPED** | 0s | $0.00 | 0 |
| Human Gate | **SKIPPED** | 0s | $0.00 | 0 |
| Execution | Hardware Engineer | 12s | $0.08 | 1 (Gemini) |
| Review | Reviewer | 4s | $0.05 | 1 (Claude) |
| Validation | Validator | 1s | $0.00 | 0 (trusted) |
| Knowledge | Knowledge Agent | 1s | $0.00 | 0 |
| **TOTAL** | | **~21s** | **$0.13** | **3** |

---

## Comparison Across Task Types

| Metric | Feature (Gauge) | Bug Fix (100%) | Documentation (Wiring) |
|---|---|---|---|
| Duration | 58s | 44s | **21s** |
| Cost | $0.56 | $0.20 | **$0.13** |
| LLM calls | 4-6 | 3 | **3** |
| Planning | GPT-5 | Skipped | **Skipped** |
| Human gate | Required | Skipped | **Skipped** |
| Execution model | Claude | Claude | **Gemini** |
| Files modified | 5 | 3 | **0** |
| Tests run | Yes | Yes | **No (nothing to test)** |

**Key insight:** The factory correctly identifies this as a knowledge/documentation task and:
1. Routes to Hardware Engineer agent (domain=hardware)
2. Uses Gemini (best for documentation + cheap)
3. Skips planning (no spec needed for a question)
4. Skips human gate (no risk, no code change)
5. Review checks factual accuracy against existing docs
6. Validation is trivial (no code = nothing to break)

---

## Bottleneck Analysis

| Bottleneck | Severity | Analysis |
|---|---|---|
| **Review for documentation** (4s, $0.05) | LOW | Review verifies pin assignments are correct. Worth it — wrong wiring can fry hardware. |
| **No output persistence** | MEDIUM | The generated diagram is only in CLI output. Not saved anywhere persistent. |
| **Context overkill?** | NONE | 6.5K tokens is well under budget. All context was relevant (pins, power, protocol). |

---

## Duplicated Responsibility Analysis

| Concern | Checked By | Redundant? |
|---|---|---|
| Pin correctness | Context (Tier 3: board_config.h) + Review (checks against docs) | **NO** — Context provides, review verifies |
| Power safety | Execution (mentions "no VCC") + Review (confirms) | **ACCEPTABLE** — safety-critical info deserves double-check |

**No actionable duplications found.** The documentation workflow is lean.

---

## Improvement Suggestions

### 1. Auto-persist documentation output (NEW)

**Problem:** The wiring diagram answer is only shown in CLI terminal. If the user wants to save it, they must manually copy-paste to a file. This valuable documentation is ephemeral.

**Suggestion:** For documentation tasks where output is substantial (> 500 tokens), offer to persist:

```
✅ Task completed (21s, $0.13)

📄 Generated: Wiring Diagram — RacePanel (Stang → Jok)

💾 Save to project? (documentation output detected)
   Suggested path: hardware/wiring-racepanel-stang-jok.md
   
   Run: factory save TASK-A1B2C3 --path hardware/wiring-racepanel-stang-jok.md
   Or:  factory save TASK-A1B2C3 --auto
```

**Implementation:** Add `documentation_output` field to ExecutionResult. When `task_type == "documentation"` and output > 500 tokens, suggest persistence path based on domain + slugified title.

**Effort:** LOW
**Impact:** MEDIUM (prevents knowledge loss from ephemeral answers)

---

### 2. Language-aware routing (OBSERVATION, no change needed)

**Observation:** User asked in Indonesian. The factory:
- Classified correctly (language-agnostic classification)
- Loaded context (mix of Indonesian and English docs — both present in RaceOS)
- Generated response in Indonesian (Gemini responded in user's language)

**Verdict:** This already works correctly. Gemini naturally mirrors the user's language. No improvement needed.

---

### 3. Hardware-specific review: check against datasheets (FUTURE)

**Observation:** Review Agent checks against existing project docs (board_config.h, ADRs). But it doesn't check against MCU datasheets (STM32F411 reference manual) for absolute correctness.

**Example:** If someone accidentally assigned a non-UART-capable pin for UART in board_config.h, Review Agent would still approve (it trusts the existing config).

**Suggestion:** For hardware domain tasks, optionally load MCU datasheet pin capabilities into Tier 3.

**Effort:** MEDIUM (need to parse datasheet pin tables)
**Impact:** LOW (existing pin assignments are already validated by working hardware)
**Recommendation:** Defer until hardware iteration phase.

---

## Verdict: ✅ Architecture Handles Multi-Domain Questions Efficiently

The factory correctly processes a complex hardware question that involves:
- Physical layout constraints (motorcycle geometry)
- Electrical design (UART signaling, power domains)
- EMC considerations (shielding, grounding)
- Protocol knowledge (baud rate, pin assignments)
- Safety warnings (no VCC sharing)

All without modifying any files, at $0.13 cost, in 21 seconds.

The architecture's model routing policy proves its value: **Gemini for documentation is 4x cheaper than Claude**, and produces excellent diagrammatic output with its large context window.

---

## Architecture Validation Status

| Task Type Tested | Result | Duration | Cost |
|---|---|---|---|
| Feature implementation (HIGH) | ✅ Correct flow | 58s | $0.56 |
| Bug investigation (MEDIUM) | ✅ Correct flow | 44s | $0.20 |
| Documentation/hardware (MEDIUM) | ✅ Correct flow | **21s** | **$0.13** |

**Three different workflow paths validated.** The architecture adapts correctly to task type, complexity, and domain.
