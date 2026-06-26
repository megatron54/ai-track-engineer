"""Gap manager: track and project gaps to cars ahead and behind.

Fed the position and lap count of nearby cars (or their gap in seconds as
reported by the shared memory), this module tracks the trend and predicts when
contact (or a safe gap) will be reached.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

_DEFAULT_WINDOW = 5


class GapTrend(StrEnum):
    CLOSING = "closing"
    STABLE = "stable"
    OPENING = "opening"


@dataclass(frozen=True)
class GapReport:
    gap_ahead_s: float | None
    gap_behind_s: float | None
    trend_ahead: GapTrend
    trend_behind: GapTrend
    contact_ahead_laps: float | None
    contact_behind_laps: float | None
    message: str


class GapManager:
    """Track gaps to the car ahead and behind over a rolling window."""

    def __init__(self, window: int = _DEFAULT_WINDOW) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        self._window = window
        self._ahead: deque[float] = deque(maxlen=window)
        self._behind: deque[float] = deque(maxlen=window)

    def update(self, *, gap_ahead_s: float | None, gap_behind_s: float | None) -> None:
        """Record the latest gap readings (seconds). ``None`` = no car."""
        if gap_ahead_s is not None:
            self._ahead.append(gap_ahead_s)
        if gap_behind_s is not None:
            self._behind.append(gap_behind_s)

    def report(self) -> GapReport:
        trend_a, contact_a = self._analyze(self._ahead)
        trend_b, contact_b = self._analyze(self._behind)
        gap_a = self._ahead[-1] if self._ahead else None
        gap_b = self._behind[-1] if self._behind else None
        return GapReport(
            gap_ahead_s=round(gap_a, 2) if gap_a is not None else None,
            gap_behind_s=round(gap_b, 2) if gap_b is not None else None,
            trend_ahead=trend_a,
            trend_behind=trend_b,
            contact_ahead_laps=round(contact_a, 1) if contact_a is not None else None,
            contact_behind_laps=round(contact_b, 1) if contact_b is not None else None,
            message=self._build_message(gap_a, trend_a, contact_a, gap_b, trend_b, contact_b),
        )

    def _analyze(self, history: deque[float]) -> tuple[GapTrend, float | None]:
        if len(history) < 2:
            return (GapTrend.STABLE, None)
        rate = (history[-1] - history[0]) / (len(history) - 1)
        if abs(rate) < 0.05:
            return (GapTrend.STABLE, None)
        if rate < 0:
            laps_to_contact = -history[-1] / rate if history[-1] > 0 else None
            return (GapTrend.CLOSING, laps_to_contact)
        return (GapTrend.OPENING, None)

    @staticmethod
    def _build_message(
        gap_a: float | None, trend_a: GapTrend, contact_a: float | None,
        gap_b: float | None, trend_b: GapTrend, contact_b: float | None,
    ) -> str:
        parts: list[str] = []
        if gap_a is not None:
            s = f"Ahead: {gap_a:.1f}s ({trend_a.value})"
            if contact_a is not None:
                s += f" — contact in ~{contact_a:.0f} laps"
            parts.append(s)
        if gap_b is not None:
            s = f"Behind: {gap_b:.1f}s ({trend_b.value})"
            if contact_b is not None:
                s += f" — contact in ~{contact_b:.0f} laps"
            parts.append(s)
        return " | ".join(parts) if parts else "No gap data."
