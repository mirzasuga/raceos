"""
Cost Tracking & Optimization.

Tracks spend per call/task/model/day and enforces budget limits.
Implements degradation strategy when approaching budget ceiling.

Cost is calculated from:
    cost = (input_tokens / 1000 * input_rate) + (output_tokens / 1000 * output_rate)

Budget enforcement:
    80% → alert human
    90% → downgrade non-critical to cheaper models
    95% → queue non-urgent tasks
    100% → only critical/safety tasks proceed

Usage:
    tracker = CostTracker(config, catalog)
    tracker.record(model_key, input_tokens, output_tokens, task_id)
    status = tracker.get_budget_status()
    should_downgrade = tracker.should_downgrade()
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .policy import ModelInfo


@dataclass
class CostConfig:
    """Budget and cost tracking configuration."""

    daily_limit_usd: float = 50.0
    per_task_limit_usd: float = 5.0
    per_session_limit_usd: float = 20.0
    alert_threshold_pct: float = 80.0
    ledger_path: str = "./data/cost_ledger.jsonl"

    # Degradation thresholds
    downgrade_threshold_pct: float = 90.0
    queue_threshold_pct: float = 95.0
    critical_only_threshold_pct: float = 100.0

    # Downgrade map (when budget constrained)
    downgrade_map: dict[str, str] = field(default_factory=lambda: {
        "gpt-5": "claude-sonnet-latest",
        "claude-sonnet-latest": "claude-sonnet",
        "claude-sonnet": "deepseek-reasoner",
        "gemini-pro": "deepseek-chat",
    })


@dataclass
class CostRecord:
    """A single cost event."""

    timestamp: float
    date: str
    model_key: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    task_id: str = ""
    task_type: str = ""


@dataclass
class BudgetStatus:
    """Current budget status snapshot."""

    spent_today_usd: float
    daily_limit_usd: float
    remaining_usd: float
    pct_used: float
    should_alert: bool
    should_downgrade: bool
    should_queue: bool
    critical_only: bool
    total_calls_today: int = 0
    top_model: str = ""             # Most expensive model today


class CostTracker:
    """
    Tracks and enforces cost budget.

    Records every LLM call with cost, provides real-time
    budget status, and signals when degradation is needed.
    """

    def __init__(
        self,
        config: CostConfig | None = None,
        catalog: dict[str, ModelInfo] | None = None,
    ):
        self.config = config or CostConfig()
        self.catalog = catalog or {}
        self._ensure_ledger_dir()

    def record(
        self,
        model_key: str,
        input_tokens: int,
        output_tokens: int,
        task_id: str = "",
        task_type: str = "",
    ) -> CostRecord:
        """
        Record a completed LLM call with cost calculation.

        Args:
            model_key: Catalog key of model used.
            input_tokens: Prompt tokens consumed.
            output_tokens: Completion tokens generated.
            task_id: Associated task ID.
            task_type: Type of task (for analytics).

        Returns:
            CostRecord with calculated cost.
        """
        cost = self._calculate_cost(model_key, input_tokens, output_tokens)
        model_info = self.catalog.get(model_key)

        record = CostRecord(
            timestamp=time.time(),
            date=str(date.today()),
            model_key=model_key,
            model_id=model_info.id if model_info else model_key,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            task_id=task_id,
            task_type=task_type,
        )

        self._append_to_ledger(record)
        return record

    def get_budget_status(self) -> BudgetStatus:
        """
        Get current budget status with all threshold signals.

        Returns:
            BudgetStatus with spending, limits, and action flags.
        """
        spent = self._get_today_spend()
        pct = (spent / self.config.daily_limit_usd * 100) if self.config.daily_limit_usd > 0 else 0
        remaining = max(0, self.config.daily_limit_usd - spent)

        return BudgetStatus(
            spent_today_usd=spent,
            daily_limit_usd=self.config.daily_limit_usd,
            remaining_usd=remaining,
            pct_used=pct,
            should_alert=pct >= self.config.alert_threshold_pct,
            should_downgrade=pct >= self.config.downgrade_threshold_pct,
            should_queue=pct >= self.config.queue_threshold_pct,
            critical_only=pct >= self.config.critical_only_threshold_pct,
            total_calls_today=self._get_today_call_count(),
        )

    def get_task_spend(self, task_id: str) -> float:
        """Get total spend for a specific task."""
        total = 0.0
        for record in self._read_today_records():
            if record.get("task_id") == task_id:
                total += record.get("cost_usd", 0)
        return total

    def check_task_budget(self, task_id: str) -> bool:
        """Check if a task has budget remaining."""
        spent = self.get_task_spend(task_id)
        return spent < self.config.per_task_limit_usd

    def get_downgrade(self, model_key: str) -> str | None:
        """
        Get the downgraded model for budget-constrained operation.

        Returns:
            Cheaper model key, or None if no downgrade available.
        """
        return self.config.downgrade_map.get(model_key)

    def estimate_cost(self, model_key: str, input_tokens: int, output_tokens: int) -> float:
        """Pre-calculate cost without recording (for budgeting)."""
        return self._calculate_cost(model_key, input_tokens, output_tokens)

    # --- Internal ---

    def _calculate_cost(self, model_key: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost from tokens × rate."""
        info = self.catalog.get(model_key)
        if not info:
            return 0.0  # Unknown model, can't calculate

        input_cost = (input_tokens / 1000) * info.cost_per_1k_input
        output_cost = (output_tokens / 1000) * info.cost_per_1k_output
        return input_cost + output_cost

    def _get_today_spend(self) -> float:
        """Sum all spending for today."""
        today = str(date.today())
        total = 0.0
        for record in self._read_all_records():
            if record.get("date") == today:
                total += record.get("cost_usd", 0)
        return total

    def _get_today_call_count(self) -> int:
        """Count calls today."""
        today = str(date.today())
        return sum(1 for r in self._read_all_records() if r.get("date") == today)

    def _read_today_records(self) -> list[dict]:
        """Read today's records from ledger."""
        today = str(date.today())
        return [r for r in self._read_all_records() if r.get("date") == today]

    def _read_all_records(self) -> list[dict]:
        """Read all records from ledger file."""
        ledger = Path(self.config.ledger_path)
        if not ledger.exists():
            return []
        records = []
        for line in ledger.read_text().strip().split("\n"):
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _append_to_ledger(self, record: CostRecord) -> None:
        """Append a record to the ledger file (JSON Lines)."""
        ledger = Path(self.config.ledger_path)

        # P4-15: Rotate ledger if too large (>10MB) or new month
        self._rotate_if_needed(ledger)

        entry = {
            "timestamp": record.timestamp,
            "date": record.date,
            "model_key": record.model_key,
            "model_id": record.model_id,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cost_usd": record.cost_usd,
            "task_id": record.task_id,
            "task_type": record.task_type,
        }
        with open(ledger, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _rotate_if_needed(self, ledger: Path) -> None:
        """
        Rotate ledger file when:
        - File exceeds 10MB, OR
        - First write of a new month

        Rotation renames current file to ledger.YYYY-MM.jsonl
        and starts fresh. Old files are preserved for auditing.
        """
        if not ledger.exists():
            return

        max_size_bytes = 10 * 1024 * 1024  # 10MB

        # Check size
        size = ledger.stat().st_size
        needs_rotation = size > max_size_bytes

        # Check month boundary
        if not needs_rotation:
            from datetime import date as date_module
            current_month = date_module.today().strftime("%Y-%m")
            # Read last line to check its month
            try:
                with open(ledger, "rb") as f:
                    f.seek(max(-200, -size), 2)  # Read last 200 bytes
                    last_lines = f.read().decode(errors="ignore").strip().split("\n")
                    if last_lines:
                        last_entry = json.loads(last_lines[-1])
                        last_month = last_entry.get("date", "")[:7]  # YYYY-MM
                        if last_month and last_month != current_month:
                            needs_rotation = True
            except (json.JSONDecodeError, OSError, IndexError):
                pass

        if needs_rotation:
            # Rename: cost_ledger.jsonl → cost_ledger.2026-07.jsonl
            from datetime import date as date_module
            archive_name = ledger.stem + f".{date_module.today().strftime('%Y-%m')}" + ledger.suffix
            archive_path = ledger.parent / archive_name
            # Avoid overwriting existing archive
            if archive_path.exists():
                archive_name = ledger.stem + f".{int(time.time())}" + ledger.suffix
                archive_path = ledger.parent / archive_name
            ledger.rename(archive_path)

    def _ensure_ledger_dir(self) -> None:
        """Create ledger directory if it doesn't exist."""
        Path(self.config.ledger_path).parent.mkdir(parents=True, exist_ok=True)
