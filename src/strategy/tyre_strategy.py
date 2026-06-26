"""Tyre strategy: when to pit for fresh rubber based on degradation trend.

Estimates the lap-time loss from tyre wear using a simple linear model:
as the wear percentage drops, lap time increases proportionally. The strategy
advises pitting when the cumulative time loss exceeds the pit-stop time penalty.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

_DEFAULT_PIT_LOSS_S = 25.0  # typical pit-stop time loss in seconds


class TyreAdvice(StrEnum):
    STAY_OUT = "stay_out"
    CONSIDER_PIT = "consider_pit"
    PIT_NOW = "pit_now"


@dataclass(frozen=True)
class TyreStrategyReport:
    avg_wear_pct: float
    wear_rate_per_lap: float | None
    laps_until_critical: float | None
    advice: TyreAdvice
    message: str


class TyreStrategy:
    """Estimate tyre life and advise when to pit."""

    def __init__(
        self,
        *,
        critical_wear_pct: float = 50.0,
        pit_loss_s: float = _DEFAULT_PIT_LOSS_S,
        window: int = 5,
    ) -> None:
        if critical_wear_pct <= 0 or critical_wear_pct > 100:
            raise ValueError("critical_wear_pct must be in (0, 100]")
        self._critical = critical_wear_pct
        self._pit_loss = pit_loss_s
        self._readings: deque[float] = deque(maxlen=window)

    def record_wear(self, avg_wear_pct: float) -> None:
        """Record the average wear across the four tyres (100 = new)."""
        self._readings.append(avg_wear_pct)

    @property
    def wear_rate(self) -> float | None:
        """Percentage-points of wear lost per lap (positive = degrading)."""
        if len(self._readings) < 2:
            return None
        rate = (self._readings[0] - self._readings[-1]) / (len(self._readings) - 1)
        return max(0.0, rate)

    def report(self) -> TyreStrategyReport:
        current = self._readings[-1] if self._readings else 100.0
        rate = self.wear_rate
        laps_left: float | None = None
        if rate is not None and rate > 0:
            laps_left = (current - self._critical) / rate

        if laps_left is not None and laps_left <= 0:
            advice = TyreAdvice.PIT_NOW
            msg = "Tyres past critical wear. Box now."
        elif laps_left is not None and laps_left <= 3:
            advice = TyreAdvice.PIT_NOW
            msg = f"Tyres critical in ~{laps_left:.0f} laps. Box box box."
        elif laps_left is not None and laps_left <= 8:
            advice = TyreAdvice.CONSIDER_PIT
            msg = f"Tyres will be critical in ~{laps_left:.0f} laps. Start thinking about a stop."
        else:
            advice = TyreAdvice.STAY_OUT
            msg = f"Tyres fine ({current:.0f}%)." if rate else "Gathering tyre data..."

        return TyreStrategyReport(
            avg_wear_pct=round(current, 1),
            wear_rate_per_lap=round(rate, 2) if rate is not None else None,
            laps_until_critical=round(laps_left, 1) if laps_left is not None else None,
            advice=advice,
            message=msg,
        )
