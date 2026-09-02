from __future__ import annotations

import time
from dataclasses import dataclass

from contextrepair.config import BudgetConfig
from contextrepair.types import TokenUsage


class BudgetExceeded(RuntimeError):
    pass


@dataclass(slots=True)
class BudgetSnapshot:
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    elapsed_seconds: float
    usage_estimated: bool


class BudgetTracker:
    """One shared budget across every phase and attempt for a task."""

    def __init__(self, config: BudgetConfig):
        self.config = config
        self.calls = 0
        self.usage = TokenUsage()
        self.started_at = time.monotonic()
        self.usage_estimated = False

    def ensure_available(self) -> None:
        if self.calls >= self.config.max_model_calls:
            raise BudgetExceeded("model-call budget exhausted")
        if self.usage.total_tokens >= self.config.max_total_tokens:
            raise BudgetExceeded("token budget exhausted")
        if time.monotonic() - self.started_at >= self.config.max_wall_seconds:
            raise BudgetExceeded("wall-clock budget exhausted")

    def record(self, usage: TokenUsage) -> None:
        self.calls += 1
        self.usage.input_tokens += usage.input_tokens
        self.usage.output_tokens += usage.output_tokens
        self.usage.cost_usd += usage.cost_usd
        self.usage_estimated = self.usage_estimated or usage.estimated
        if self.usage.total_tokens > self.config.max_total_tokens:
            raise BudgetExceeded("model response exceeded remaining token budget")

    def remaining_tokens(self) -> int:
        return max(0, self.config.max_total_tokens - self.usage.total_tokens)

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            calls=self.calls,
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
            cost_usd=self.usage.cost_usd,
            elapsed_seconds=time.monotonic() - self.started_at,
            usage_estimated=self.usage_estimated,
        )
