"""Tests for car physics INI parsers and the unified model."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.knowledge.car_physics import CarPhysicsModel, CarSpec, Drivetrain, parse_ini

_CAR_INI = """
[INFO]
SCREEN_NAME=BMW 740D G11 2017
[BASIC]
TOTALMASS=2840
INERTIA=1.90,1.40,4.85
[GRAPHICS]
FUEL_LIGHT_MIN_LITERS=10
"""

_DRIVETRAIN_INI = """
[TRACTION]
TYPE=RWD
[GEARS]
COUNT=8     ; forward gears
GEAR_R=-3.317
GEAR_1=5.0
GEAR_2=3.20
GEAR_3=2.143
GEAR_4=1.72
GEAR_5=1.314
GEAR_6=1.00
GEAR_7=0.822
GEAR_8=0.64
FINAL=3.95
"""

_POWER_LUT = "0|90\n1000|120\n5500|600\n6000|600\n6900|561\n"


def test_parse_ini_handles_comments_and_case() -> None:
    data = parse_ini(_DRIVETRAIN_INI)
    assert data["GEARS"]["COUNT"] == "8"
    assert data["GEARS"]["GEAR_1"] == "5.0"
    assert data["TRACTION"]["TYPE"] == "RWD"


def test_car_spec_from_text() -> None:
    car = CarSpec.from_text(_CAR_INI)
    assert car.screen_name == "BMW 740D G11 2017"
    assert car.total_mass_kg == pytest.approx(2840.0)
    assert car.fuel_light_min_l == pytest.approx(10.0)


def test_drivetrain_from_text() -> None:
    dt = Drivetrain.from_text(_DRIVETRAIN_INI)
    assert dt.traction_type == "RWD"
    assert dt.gear_count == 8
    assert len(dt.gear_ratios) == 8
    assert dt.gear_ratios[0] == pytest.approx(5.0)
    assert dt.final_drive == pytest.approx(3.95)
    assert dt.reverse_ratio == pytest.approx(-3.317)
    assert dt.ratio_for(8) == pytest.approx(0.64 * 3.95)
    assert dt.ratio_for(9) is None


def _write_car(tmp: Path) -> Path:
    (tmp / "car.ini").write_text(_CAR_INI, encoding="utf-8")
    (tmp / "drivetrain.ini").write_text(_DRIVETRAIN_INI, encoding="utf-8")
    (tmp / "power.lut").write_text(_POWER_LUT, encoding="utf-8")
    return tmp


def test_car_model_from_dir(tmp_path: Path) -> None:
    model = CarPhysicsModel.from_dir(_write_car(tmp_path))
    assert model.car.total_mass_kg == pytest.approx(2840.0)
    assert model.drivetrain.gear_count == 8
    assert model.peak_power_hp is not None
    assert model.power_to_weight is not None
    speed = model.top_speed_kmh(tyre_radius_m=0.34)
    assert speed is not None and speed > 0


def test_car_model_missing_files(tmp_path: Path) -> None:
    model = CarPhysicsModel.from_dir(tmp_path)
    assert model.power is None
    assert model.peak_power_hp is None
    assert model.power_to_weight is None
    assert model.top_speed_kmh(0.34) is None
