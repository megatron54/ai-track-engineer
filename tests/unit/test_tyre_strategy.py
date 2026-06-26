"""Tests for tyre strategy."""

from __future__ import annotations

import pytest
from src.strategy.tyre_strategy import TyreAdvice, TyreStrategy


def test_invalid_critical() -> None:
    with pytest.raises(ValueError, match="critical_wear_pct"):
        TyreStrategy(critical_wear_pct=0)


def test_no_data() -> None:
    report = TyreStrategy().report()
    assert report.advice is TyreAdvice.STAY_OUT
    assert report.wear_rate_per_lap is None
    assert "Gathering" in report.message


def test_healthy_tyres() -> None:
    ts = TyreStrategy(critical_wear_pct=50.0)
    for w in [100.0, 98.0, 96.0]:
        ts.record_wear(w)
    report = ts.report()
    assert report.advice is TyreAdvice.STAY_OUT
    assert report.wear_rate_per_lap == pytest.approx(2.0)
    assert report.laps_until_critical is not None and report.laps_until_critical > 10


def test_pit_now_when_critical() -> None:
    ts = TyreStrategy(critical_wear_pct=50.0)
    for w in [55.0, 52.0, 49.0]:
        ts.record_wear(w)
    report = ts.report()
    assert report.advice is TyreAdvice.PIT_NOW
    assert "Box" in report.message


def test_consider_pit() -> None:
    ts = TyreStrategy(critical_wear_pct=50.0)
    for w in [70.0, 67.0, 64.0]:  # rate=3, remaining=(64-50)/3 = 4.67 laps
        ts.record_wear(w)
    report = ts.report()
    assert report.advice is TyreAdvice.CONSIDER_PIT
