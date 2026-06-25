"""Tests for LUT and power-curve parsing."""

from __future__ import annotations

import pytest
from src.knowledge.car_physics.lut import Lut
from src.knowledge.car_physics.power_parser import PowerCurve

_POWER_LUT = """
0|90
1000|120
2000|234
4000|440
5500|600
6000|600
6900|561
"""


def test_lut_requires_points() -> None:
    with pytest.raises(ValueError, match="at least one point"):
        Lut([])


def test_lut_parse_and_interpolate() -> None:
    lut = Lut.from_text("0|0\n100|10\n200|30\n; comment\nbad line\n")
    assert lut.x_min == 0.0
    assert lut.x_max == 200.0
    assert lut.value_at(50) == pytest.approx(5.0)
    assert lut.value_at(150) == pytest.approx(20.0)
    # Clamped outside the range.
    assert lut.value_at(-10) == pytest.approx(0.0)
    assert lut.value_at(999) == pytest.approx(30.0)


def test_lut_orders_points() -> None:
    lut = Lut([(200.0, 2.0), (0.0, 0.0), (100.0, 1.0)])
    assert lut.points[0] == (0.0, 0.0)
    assert lut.points[-1] == (200.0, 2.0)


def test_power_curve_peaks() -> None:
    curve = PowerCurve.from_text(_POWER_LUT)
    assert curve.max_rpm == 6900.0
    # Peak torque is 600 Nm (first reached at 5500).
    peak_t = curve.peak_torque
    assert peak_t.torque_nm == pytest.approx(600.0)
    assert peak_t.rpm == 5500.0
    # Peak power should be at higher RPM than peak torque.
    peak_p = curve.peak_power
    assert peak_p.rpm >= peak_t.rpm
    assert peak_p.power_w > 0
    assert peak_p.power_hp > 0


def test_power_at_computes_from_torque() -> None:
    curve = PowerCurve.from_text("1000|100\n2000|100\n")
    # power = torque * rpm * 2pi/60
    import math

    assert curve.power_at(2000) == pytest.approx(100 * 2000 * 2 * math.pi / 60)


def test_power_band() -> None:
    curve = PowerCurve.from_text(_POWER_LUT)
    low, high = curve.power_band(0.9)
    assert low <= curve.peak_power.rpm <= high
    with pytest.raises(ValueError, match="fraction must be"):
        curve.power_band(0.0)
