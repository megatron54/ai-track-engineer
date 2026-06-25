"""Post-session analysis: summarise a session's laps.

Turns a list of completed laps into the numbers a driver cares about after a
run: best lap, pace, consistency, improvement over the session, and the
"theoretical best" lap from the fastest sectors.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from src.processing.models import Lap


class SessionReport(BaseModel):
    """Aggregate statistics for a driving session."""

    model_config = ConfigDict(frozen=True)

    total_laps: int
    valid_laps: int
    best_lap_ms: int | None = None
    average_lap_ms: float | None = None
    consistency_stdev_ms: float | None = None
    improvement_ms: int | None = None
    theoretical_best_ms: int | None = None

    @property
    def best_lap_seconds(self) -> float | None:
        """Best lap time in seconds, or ``None``."""
        return None if self.best_lap_ms is None else self.best_lap_ms / 1000.0


def _theoretical_best(valid: Sequence[Lap]) -> int | None:
    """Sum of the fastest time in each sector across the valid laps."""
    sector_counts = {len(lap.sector_times_ms) for lap in valid if lap.sector_times_ms}
    if len(sector_counts) != 1:
        return None  # inconsistent or missing sector data
    count = sector_counts.pop()
    if count == 0:
        return None
    best_sectors = [
        min(lap.sector_times_ms[i] for lap in valid if lap.sector_times_ms)
        for i in range(count)
    ]
    return sum(best_sectors)


def build_session_report(laps: Sequence[Lap]) -> SessionReport:
    """Build a :class:`SessionReport` from a session's laps."""
    valid = [lap for lap in laps if lap.valid and lap.lap_time_ms > 0]
    if not valid:
        return SessionReport(total_laps=len(laps), valid_laps=0)

    times = [lap.lap_time_ms for lap in valid]
    best = min(times)
    average = statistics.fmean(times)
    consistency = statistics.stdev(times) if len(times) >= 2 else None
    improvement = times[0] - times[-1] if len(times) >= 2 else None

    return SessionReport(
        total_laps=len(laps),
        valid_laps=len(valid),
        best_lap_ms=best,
        average_lap_ms=round(average, 1),
        consistency_stdev_ms=round(consistency, 1) if consistency is not None else None,
        improvement_ms=improvement,
        theoretical_best_ms=_theoretical_best(valid),
    )
