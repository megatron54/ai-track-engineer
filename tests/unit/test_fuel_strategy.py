"""Tests for fuel strategy."""

from __future__ import annotations

import pytest
from src.strategy.fuel_strategy import FuelStatus, FuelStrategy


def test_invalid_window() -> None:
    with pytest.raises(ValueError, match="window must be >= 1"):
        FuelStrategy(window=0)


def test_negative_fuel_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        FuelStrategy().record_lap_fuel(-1.0)


def test_consumption_unknown_with_one_reading() -> None:
    strategy = FuelStrategy()
    strategy.record_lap_fuel(50.0)
    assert strategy.consumption_per_lap is None
    assert strategy.laps_remaining() is None
    assert strategy.report().status is FuelStatus.OK


def test_consumption_and_range() -> None:
    strategy = FuelStrategy()
    for fuel in (50.0, 47.5, 45.0, 42.5):  # 2.5 L/lap
        strategy.record_lap_fuel(fuel)
    assert strategy.consumption_per_lap == pytest.approx(2.5)
    assert strategy.laps_remaining() == pytest.approx(42.5 / 2.5)
    assert strategy.fuel_for_laps(10) == pytest.approx(25.0)


def test_refuelling_is_ignored() -> None:
    strategy = FuelStrategy()
    strategy.record_lap_fuel(50.0)
    strategy.record_lap_fuel(47.0)  # -3
    strategy.record_lap_fuel(70.0)  # refuel (ignored)
    strategy.record_lap_fuel(67.0)  # -3
    assert strategy.consumption_per_lap == pytest.approx(3.0)


def test_status_against_race_distance() -> None:
    strategy = FuelStrategy()
    for fuel in (20.0, 18.0, 16.0):  # 2 L/lap, 16 L left -> 8 laps
        strategy.record_lap_fuel(fuel)
    assert strategy.report(laps_left=5).status is FuelStatus.OK
    assert strategy.report(laps_left=8).status is FuelStatus.LOW
    critical = strategy.report(laps_left=12)
    assert critical.status is FuelStatus.CRITICAL
    assert critical.margin_laps is not None and critical.margin_laps < 0


def test_status_absolute_range() -> None:
    strategy = FuelStrategy()
    for fuel in (5.0, 3.0):  # 2 L/lap, 3 L left -> 1.5 laps
        strategy.record_lap_fuel(fuel)
    assert strategy.report().status is FuelStatus.CRITICAL


def test_window_limits_average() -> None:
    strategy = FuelStrategy(window=2)
    # Consumptions: 1, 2, 3 -> window keeps last two (2, 3) -> avg 2.5
    for fuel in (10.0, 9.0, 7.0, 4.0):
        strategy.record_lap_fuel(fuel)
    assert strategy.consumption_per_lap == pytest.approx(2.5)
