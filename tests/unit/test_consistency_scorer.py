"""Tests for the consistency scorer."""

from __future__ import annotations

import pytest
from src.processing.models import Lap
from src.setup_lab.consistency_scorer import score_consistency


def _lap(n: int, ms: int, *, valid: bool = True) -> Lap:
    return Lap(lap_number=n, lap_time_ms=ms, valid=valid)


def test_empty_session() -> None:
    score = score_consistency([])
    assert score.overall == 0.0
    assert score.sample_size == 0
    assert score.clean_lap_pct == 0.0


def test_single_valid_lap_has_zero_overall() -> None:
    score = score_consistency([_lap(1, 90_000)])
    assert score.sample_size == 1
    assert score.overall == 0.0
    assert score.mean_lap_time_s == pytest.approx(90.0)


def test_metronomic_laps_score_high() -> None:
    laps = [_lap(i, 90_000 + i * 10) for i in range(6)]  # ~tiny spread
    score = score_consistency(laps)
    assert score.overall > 0.9
    assert score.clean_lap_pct == 1.0
    assert score.stdev_s < 0.1


def test_erratic_laps_score_low() -> None:
    laps = [_lap(1, 90_000), _lap(2, 95_000), _lap(3, 88_000), _lap(4, 97_000)]
    score = score_consistency(laps)
    assert score.overall < 0.5
    assert score.stdev_s > 1.0


def test_invalid_laps_reduce_clean_pct_and_score() -> None:
    laps = [
        _lap(1, 90_000),
        _lap(2, 90_100),
        _lap(3, 90_050, valid=False),
        _lap(4, 90_080, valid=False),
    ]
    score = score_consistency(laps)
    assert score.clean_lap_pct == pytest.approx(0.5)
    # Consistent valid laps but only 50% clean -> overall halved.
    assert 0.0 < score.overall <= 0.5
