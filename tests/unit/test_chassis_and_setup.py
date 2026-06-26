"""Tests for chassis parsers (aero, brakes, suspension) and setup I/O."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.knowledge.car_physics import AeroSpec, BrakeSpec, CarPhysicsModel, SuspensionSpec
from src.setup_lab import apply_changes, read_setup, write_setup

_AERO_INI = """
[HEADER]
VERSION=2
[WING_0]
NAME=BODY
CHORD=1
SPAN=2.23
ANGLE=1
CL_GAIN=0
CD_GAIN=1
[WING_1]
NAME=REAR
CHORD=0.3
SPAN=1.2
ANGLE=5
CL_GAIN=2.5
CD_GAIN=0.8
"""

_BRAKES_INI = """
[HEADER]
VERSION=1
[DATA]
MAX_TORQUE=3800
FRONT_SHARE=0.62
"""

_SUSPENSION_INI = """
[HEADER]
VERSION=2
[BASIC]
WHEELBASE=2.95
CG_LOCATION=0.505
[ARB]
FRONT=24000
REAR=11000
[FRONT]
SPRING_RATE=42760
TOE_OUT=-0.0004
STATIC_CAMBER=-0.35
TRACK=1.817
[REAR]
SPRING_RATE=38500
TOE_OUT=0.001
STATIC_CAMBER=-1.5
TRACK=1.82
"""

_SETUP_INI = "[ARB_FRONT]\nVALUE=3\n\n[ARB_REAR]\nVALUE=1\n\n[FUEL]\nVALUE=40\n"


def test_aero_spec() -> None:
    aero = AeroSpec.from_text(_AERO_INI)
    assert len(aero.wings) == 2
    assert aero.wings[0].name == "BODY"
    assert aero.wings[1].cl_gain == pytest.approx(2.5)


def test_brake_spec() -> None:
    brakes = BrakeSpec.from_text(_BRAKES_INI)
    assert brakes.max_torque == pytest.approx(3800.0)
    assert brakes.front_share == pytest.approx(0.62)


def test_suspension_spec() -> None:
    susp = SuspensionSpec.from_text(_SUSPENSION_INI)
    assert susp.wheelbase == pytest.approx(2.95)
    assert susp.arb_front == pytest.approx(24000)
    assert susp.front.spring_rate == pytest.approx(42760)
    assert susp.rear.static_camber == pytest.approx(-1.5)


def test_car_model_includes_chassis(tmp_path: Path) -> None:
    (tmp_path / "car.ini").write_text("[INFO]\nSCREEN_NAME=T\n[BASIC]\nTOTALMASS=1000\n")
    (tmp_path / "drivetrain.ini").write_text("[GEARS]\nCOUNT=0\nFINAL=1\n")
    (tmp_path / "aero.ini").write_text(_AERO_INI)
    (tmp_path / "brakes.ini").write_text(_BRAKES_INI)
    (tmp_path / "suspensions.ini").write_text(_SUSPENSION_INI)
    model = CarPhysicsModel.from_dir(tmp_path)
    assert model.aero is not None and len(model.aero.wings) == 2
    assert model.brakes is not None and model.brakes.front_share == pytest.approx(0.62)
    assert model.suspension is not None and model.suspension.wheelbase == pytest.approx(2.95)


def test_read_write_setup(tmp_path: Path) -> None:
    path = tmp_path / "test.ini"
    path.write_text(_SETUP_INI, encoding="utf-8")
    setup = read_setup(path)
    assert setup["ARB_FRONT"] == "3"
    assert setup["FUEL"] == "40"


def test_write_creates_backup(tmp_path: Path) -> None:
    path = tmp_path / "test.ini"
    path.write_text(_SETUP_INI, encoding="utf-8")
    setup = read_setup(path)
    write_setup(path, apply_changes(setup, {"FUEL": "50"}))
    assert path.with_suffix(".ini.bak").is_file()
    new = read_setup(path)
    assert new["FUEL"] == "50"
    assert new["ARB_FRONT"] == "3"


def test_apply_changes_is_immutable() -> None:
    base = {"A": "1", "B": "2"}
    result = apply_changes(base, {"B": "9", "C": "3"})
    assert result == {"A": "1", "B": "9", "C": "3"}
    assert base["B"] == "2"  # original unchanged
