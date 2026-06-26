"""Detect recurring patterns and regressions in driving data.

Analyses a sequence of laps (from SQLite) to surface actionable patterns:
- Which corners consistently cost the most time.
- Whether specific corners have regressed recently.
- Whether consistency is improving or degrading over time.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from src.analysis.models import CornerDelta


@dataclass(frozen=True)
class CornerPattern:
    """A recurring time-loss pattern at a specific corner."""

    corner_name: str
    occurrences: int
    avg_delta_s: float
    trend: str  # "improving", "stable", "regressing"


@dataclass(frozen=True)
class PatternReport:
    """Summary of detected patterns across a session or multi-session history."""

    worst_corners: list[CornerPattern]
    consistency_trend: str  # "improving", "stable", "regressing"
    lap_time_trend: str  # "improving", "stable", "regressing"


def _trend(values: Sequence[float], threshold: float = 0.02) -> str:
    """Simple linear trend from a sequence of values."""
    if len(values) < 3:
        return "stable"
    first_half = statistics.fmean(values[: len(values) // 2])
    second_half = statistics.fmean(values[len(values) // 2 :])
    diff = second_half - first_half
    if diff < -threshold:
        return "improving"
    if diff > threshold:
        return "regressing"
    return "stable"


def detect_patterns(
    corner_deltas_per_lap: Sequence[Sequence[CornerDelta]],
    lap_times_s: Sequence[float],
    *,
    min_occurrences: int = 3,
    limit: int = 5,
) -> PatternReport:
    """Analyse corner deltas and lap times for patterns.

    Args:
        corner_deltas_per_lap: Per-lap lists of corner deltas (from the
            comparator). Each inner sequence covers the corners where time was
            lost on that lap.
        lap_times_s: Valid lap times in session order.
        min_occurrences: A corner must appear in at least this many laps to be
            reported as a pattern.
        limit: Maximum number of worst corners to report.
    """
    # Accumulate per-corner losses across laps.
    corner_losses: dict[str, list[float]] = defaultdict(list)
    for lap_deltas in corner_deltas_per_lap:
        for delta in lap_deltas:
            if delta.lost_time:
                corner_losses[delta.corner_name].append(delta.delta_s)

    worst: list[CornerPattern] = []
    for name, losses in corner_losses.items():
        if len(losses) < min_occurrences:
            continue
        worst.append(
            CornerPattern(
                corner_name=name,
                occurrences=len(losses),
                avg_delta_s=round(statistics.fmean(losses), 3),
                trend=_trend(losses),
            )
        )
    worst.sort(key=lambda p: p.avg_delta_s, reverse=True)

    # Lap-time consistency: stdev trend.
    stdevs: list[float] = []
    window = max(3, len(lap_times_s) // 4)
    for i in range(0, len(lap_times_s) - window + 1, max(1, window // 2)):
        chunk = lap_times_s[i : i + window]
        if len(chunk) >= 2:
            stdevs.append(statistics.stdev(chunk))

    return PatternReport(
        worst_corners=worst[:limit],
        consistency_trend=_trend(stdevs, threshold=0.1),
        lap_time_trend=_trend(list(lap_times_s), threshold=0.1),
    )
