# Firmware Core Spec (Test Fixture)

## Requirements

- REQ-001: Layered architecture with one-way dependencies.
- REQ-002: All hardware access behind HAL interfaces.
- REQ-003: Pure logic host-native testable.

## Scenarios

### Scenario: Build compiles on native environment
Given the firmware source code
When built with `pio build -e native`
Then compilation succeeds with zero errors
