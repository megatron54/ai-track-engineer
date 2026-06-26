"""Tests for pattern detection."""

from __future__ import annotations

from src.analysis.models import CornerDelta
from src.analysis.pattern_detector import detect_patterns


def _delta(corner: str, s: float) -> CornerDelta:
    return CornerDelta(corner_index=0, corner_name=corner, delta_s=s)


def test_worst_corners_ranked_by_avg_loss() -> None:
    per_lap = [
        [_delta("T1", 0.5), _delta("T3", 0.1)],
        [_delta("T1", 0.4), _delta("T3", 0.2)],
        [_delta("T1", 0.6), _delta("T3", 0.15)],
    ]
    report = detect_patterns(per_lap, [90.0, 89.5, 89.0])
    assert report.worst_corners[0].corner_name == "T1"
    assert report.worst_corners[0].occurrences == 3
    assert report.worst_corners[0].avg_delta_s > report.worst_corners[1].avg_delta_s


def test_corners_below_min_occurrences_excluded() -> None:
    per_lap = [[_delta("T1", 0.5)], [_delta("T1", 0.4)]]
    report = detect_patterns(per_lap, [90.0, 89.0], min_occurrences=3)
    assert report.worst_corners == []


def test_lap_time_trend_improving() -> None:
    times = [92.0, 91.5, 91.0, 90.5, 90.0, 89.5]
    report = detect_patterns([], times)
    assert report.lap_time_trend == "improving"


def test_lap_time_trend_regressing() -> None:
    times = [89.0, 89.5, 90.0, 90.5, 91.0, 91.5]
    report = detect_patterns([], times)
    assert report.lap_time_trend == "regressing"


def test_consistency_trend_stable() -> None:
    # Nearly identical lap times -> low stdev -> stable consistency.
    times = [90.0, 90.01, 90.02, 89.99, 90.0, 90.01]
    report = detect_patterns([], times)
    assert report.consistency_trend == "stable"


def test_corner_trend_detected() -> None:
    # T2 losses are shrinking -> improving.
    per_lap = [[_delta("T2", 0.8)]] * 3 + [[_delta("T2", 0.2)]] * 3
    report = detect_patterns(per_lap, [90.0] * 6)
    t2 = next(p for p in report.worst_corners if p.corner_name == "T2")
    assert t2.trend == "improving"
