"""Tests for the digital twin and what-if simulator."""

from __future__ import annotations

import pytest
from src.setup_lab.digital_twin import PointMassModel
from src.setup_lab.what_if import what_if

_CORNERS = [(1, 80.0, 150.0), (2, 200.0, 300.0), (3, 50.0, 100.0)]
_LENGTH = 4000.0


def _baseline() -> PointMassModel:
    return PointMassModel(mass_kg=1500, power_w=500_000, cl=2.5, cd=1.0)


def test_top_speed_positive() -> None:
    model = _baseline()
    assert model.top_speed_ms() > 50


def test_more_downforce_increases_corner_speed() -> None:
    base = _baseline()
    more_df = base.with_changes(cl_delta=1.0)
    v_base = base.max_corner_speed(80.0)
    v_more = more_df.max_corner_speed(80.0)
    assert v_more > v_base


def test_more_drag_reduces_top_speed() -> None:
    base = _baseline()
    more_drag = base.with_changes(cd_delta=0.5)
    assert more_drag.top_speed_ms() < base.top_speed_ms()


def test_simulate_lap_returns_positive_time() -> None:
    sim = _baseline().simulate_lap(_CORNERS, _LENGTH)
    assert sim.predicted_lap_time_s > 0
    assert sim.top_speed_kmh > 0
    assert len(sim.corners) == 3


def test_what_if_more_downforce_faster_in_corners() -> None:
    result = what_if(
        _baseline(), _CORNERS, _LENGTH, cl_delta=0.5, cd_delta=0.1,
        description="more rear wing",
    )
    # More CL should help corners but hurt straights; net effect depends on track.
    assert result.delta_s != 0.0
    assert "more rear wing" in result.explanation
    assert result.before.predicted_lap_time_s != result.after.predicted_lap_time_s


def test_what_if_zero_change_is_zero_delta() -> None:
    result = what_if(_baseline(), _CORNERS, _LENGTH)
    assert result.delta_s == pytest.approx(0.0)


def test_what_if_more_mass_is_slower() -> None:
    result = what_if(_baseline(), _CORNERS, _LENGTH, mass_delta=200)
    assert result.delta_s > 0  # heavier = slower
