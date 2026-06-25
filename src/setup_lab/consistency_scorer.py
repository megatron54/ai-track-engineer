"""Driver consistency scoring.

The Setup Lab's guiding principle is that the best setup is the fastest one the
driver can execute *consistently*. This module quantifies consistency from a
session's lap times: the spread of lap times (coefficient of variation) and the
proportion of clean (valid) laps, combined into a single 0-1 score.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from src.processing.models import Lap

# A coefficient of variation at or above this is treated as fully inconsistent.
_CV_ZERO_SCORE = 0.03  # 3% lap-time spread -> 0 consistency


class ConsistencyScore(BaseModel):
    """Quantified driver consistency over a set of laps."""

    model_config = ConfigDict(frozen=True)

    overall: float  # 0 (erratic) - 1 (metronomic)
    mean_lap_time_s: float
    stdev_s: float
    clean_lap_pct: float
    sample_size: int


def score_consistency(laps: Sequence[Lap]) -> ConsistencyScore:
    """Score consistency from a session's laps.

    Args:
        laps: All laps (valid and invalid) from a session.

    Returns:
        A :class:`ConsistencyScore`. With fewer than two valid laps the spread
        cannot be measured and ``overall`` is ``0``.
    """
    valid = [lap for lap in laps if lap.valid and lap.lap_time_ms > 0]
    clean_pct = len(valid) / len(laps) if laps else 0.0

    if len(valid) < 2:
        mean_s = (valid[0].lap_time_ms / 1000.0) if valid else 0.0
        return ConsistencyScore(
            overall=0.0,
            mean_lap_time_s=round(mean_s, 3),
            stdev_s=0.0,
            clean_lap_pct=round(clean_pct, 3),
            sample_size=len(valid),
        )

    times_s = [lap.lap_time_ms / 1000.0 for lap in valid]
    mean_s = statistics.fmean(times_s)
    stdev_s = statistics.stdev(times_s)
    cv = stdev_s / mean_s if mean_s > 0 else 1.0
    spread_score = max(0.0, 1.0 - cv / _CV_ZERO_SCORE)
    # Weight the spread by how many laps were clean.
    overall = spread_score * clean_pct

    return ConsistencyScore(
        overall=round(overall, 3),
        mean_lap_time_s=round(mean_s, 3),
        stdev_s=round(stdev_s, 3),
        clean_lap_pct=round(clean_pct, 3),
        sample_size=len(valid),
    )
