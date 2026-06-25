"""Tests for the tyre thermal model."""

from __future__ import annotations

import pytest
from src.analysis.tyre_model import ThermalStatus, TyreThermalModel

from tests.factories import make_physics, make_wheels


def test_invalid_window() -> None:
    with pytest.raises(ValueError, match="optimal_min must be below"):
        TyreThermalModel(optimal_min=100.0, optimal_max=80.0)


@pytest.mark.parametrize(
    ("temp", "expected"),
    [
        (70.0, ThermalStatus.COLD),
        (80.0, ThermalStatus.OPTIMAL),
        (90.0, ThermalStatus.OPTIMAL),
        (100.0, ThermalStatus.OPTIMAL),
        (110.0, ThermalStatus.HOT),
    ],
)
def test_classify(temp: float, expected: ThermalStatus) -> None:
    assert TyreThermalModel().classify(temp) == expected


def test_evaluate_all_optimal() -> None:
    physics = make_physics(tyre_core_temp=make_wheels(90.0))
    report = TyreThermalModel().evaluate(physics)
    assert report.all_optimal is True
    assert report.overheating is False
    assert report.too_cold is False
    assert report.front_rear_delta == pytest.approx(0.0)


def test_evaluate_detects_overheating_front() -> None:
    from src.telemetry.models import Wheels

    physics = make_physics(
        tyre_core_temp=Wheels(front_left=110.0, front_right=108.0, rear_left=90.0, rear_right=90.0)
    )
    report = TyreThermalModel().evaluate(physics)
    assert report.overheating is True
    assert report.statuses[0] is ThermalStatus.HOT
    assert report.statuses[2] is ThermalStatus.OPTIMAL
    # Front markedly hotter than rear.
    assert report.front_rear_delta > 15.0


def test_evaluate_detects_cold_tyres() -> None:
    physics = make_physics(tyre_core_temp=make_wheels(60.0))
    report = TyreThermalModel().evaluate(physics)
    assert report.too_cold is True
    assert report.all_optimal is False
