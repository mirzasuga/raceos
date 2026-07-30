"""
Firmware Adapter.

Domain adapter for STM32 embedded firmware (C++, PlatformIO, Unity tests).
Enforces RaceOS firmware architectural constraints.
"""

from __future__ import annotations

from .base import BaseAdapter


class FirmwareAdapter(BaseAdapter):
    """Adapter for STM32F411 firmware development."""

    @property
    def name(self) -> str:
        return "firmware"

    @property
    def working_dir(self) -> str:
        return "../firmware"

    @property
    def build_commands(self) -> list[str]:
        return [
            "pio build -e native",              # Host-native build (for testing)
            "pio build -e blackpill_f411ce",    # Hardware build (debug)
        ]

    @property
    def test_commands(self) -> list[str]:
        return [
            "pio test -e native",               # Unity tests (host-native)
        ]

    @property
    def lint_commands(self) -> list[str]:
        return [
            "pio check -e native",              # Static analysis
        ]

    @property
    def constraints(self) -> list[str]:
        return [
            # Architecture
            "Layered architecture: app/ → middleware/ → drivers/ → core/. Never reverse.",
            "One-way dependencies only. No #include from lower to higher layer.",

            # Memory
            "No dynamic allocation (no new/malloc on data path). Use static buffers.",
            "No magic numbers. All constants named in board_config.h or relevant header.",

            # HAL
            "All hardware access behind HAL interfaces (IClock, ISerialPort, IGpio, IDisplayPanel).",
            "Guard ALL Arduino/hardware API with #if defined(ARDUINO). Only in drivers/.",

            # Testing
            "Pure logic MUST be host-native testable (env: native).",
            "Write Unity tests in firmware/tests/ for all new logic.",

            # Code style
            "Comments in Indonesian (project convention).",
            "Small functions, meaningful names, documented public API.",
            "Prefer Strategy/Observer/Adapter patterns. No factory pattern for wiring.",

            # Process
            "Run 'pio test -e native' and verify all tests pass before declaring done.",
            "Commit on branch factory/<task-name>. Never commit to main.",
        ]

    @property
    def file_patterns(self) -> list[str]:
        return ["*.cpp", "*.h", "*.c", "*.ini"]
