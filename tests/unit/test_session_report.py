"""Tests for post-session reporting."""

from __future__ import annotations

import pytest
from src.analysis.session_report import build_session_report
from src.processing.models import Lap


def _lap(number: int, ms: int, *, valid: bool = True, sectors: tuple[int, ...] = ()) -> Lap:
    return Lap(lap_number=number, lap_time_ms=ms, valid=valid, sector_times_ms=sectors)


def test_empty_session() -> None:
    report = build_session_report([])
    assert report.total_laps == 0
    assert report.valid_laps == 0
    assert report.best_lap_ms is None


def test_invalid_laps_excluded() -> None:
    report = build_session_report([_lap(1, 90_000, valid=False)])
    assert report.total_laps == 1
    assert report.valid_laps == 0
    assert report.best_lap_ms is None


def test_basic_statistics() -> None:
    laps = [_lap(1, 92_000), _lap(2, 90_000), _lap(3, 91_000)]
    report = build_session_report(laps)
    assert report.total_laps == 3
    assert report.valid_laps == 3
    assert report.best_lap_ms == 90_000
    assert report.best_lap_seconds == pytest.approx(90.0)
    assert report.average_lap_ms == pytest.approx(91_000.0)
    assert report.consistency_stdev_ms is not None
    # Improvement: first (92.0) - last (91.0) = +1000 ms.
    assert report.improvement_ms == 1_000


def test_single_lap_has_no_consistency_or_improvement() -> None:
    report = build_session_report([_lap(1, 90_000)])
    assert report.best_lap_ms == 90_000
    assert report.consistency_stdev_ms is None
    assert report.improvement_ms is None


def test_theoretical_best_from_sectors() -> None:
    laps = [
        _lap(1, 90_000, sectors=(30_000, 30_000, 30_000)),
        _lap(2, 89_500, sectors=(29_500, 30_500, 29_500)),
    ]
    report = build_session_report(laps)
    # Best sectors: 29_500 + 30_000 + 29_500 = 89_000.
    assert report.theoretical_best_ms == 89_000


def test_theoretical_best_none_without_consistent_sectors() -> None:
    laps = [
        _lap(1, 90_000, sectors=(30_000, 30_000, 30_000)),
        _lap(2, 89_500, sectors=(29_500, 30_500)),  # different sector count
    ]
    assert build_session_report(laps).theoretical_best_ms is None
