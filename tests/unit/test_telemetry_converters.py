"""Tests for raw-struct -> domain-model converters.

Building the ctypes structures in memory and round-tripping them through the
converters validates both the conversion logic and that the struct field names
match what the converters expect.
"""

from __future__ import annotations

import pytest
from src.telemetry import converters
from src.telemetry.shm_structs import (
    ACFlagType,
    ACSessionType,
    ACStatus,
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)


def _set_array(field: object, values: list[float]) -> None:
    for index, value in enumerate(values):
        field[index] = value  # type: ignore[index]


def test_physics_from_struct_maps_core_fields() -> None:
    raw = SPageFilePhysics()
    raw.packetId = 42
    raw.gas = 1.0
    raw.brake = 0.25
    raw.clutch = 0.0
    raw.steerAngle = -12.0
    raw.gear = 4
    raw.rpms = 7200
    raw.speedKmh = 210.5
    raw.fuel = 33.3
    _set_array(raw.accG, [0.4, -0.1, 1.2])
    _set_array(raw.velocity, [1.0, 0.0, 58.0])
    _set_array(raw.tyreCoreTemperature, [80.0, 81.0, 82.0, 83.0])
    _set_array(raw.tyreTempI, [85, 85, 85, 85])
    _set_array(raw.tyreTempM, [84, 84, 84, 84])
    _set_array(raw.tyreTempO, [83, 83, 83, 83])
    _set_array(raw.wheelsPressure, [27.0, 27.1, 26.9, 27.2])
    _set_array(raw.tyreWear, [99.0, 98.0, 97.0, 96.0])
    _set_array(raw.wheelSlip, [0.1, 0.2, 0.3, 0.4])
    _set_array(raw.brakeTemp, [300, 310, 290, 295])
    _set_array(raw.suspensionTravel, [0.01, 0.02, 0.03, 0.04])
    raw.tc = 0.5
    raw.abs = 0.3
    raw.turboBoost = 1.1
    raw.brakeBias = 0.57
    raw.airTemp = 22.0
    raw.roadTemp = 31.0

    physics = converters.physics_from_struct(raw)

    assert physics.packet_id == 42
    assert physics.gear == 4
    assert physics.gear_label == "3"
    assert physics.rpm == 7200
    assert physics.speed_kmh == pytest.approx(210.5, abs=1e-3)
    # Longitudinal g maps to the third (z) axis of the acceleration vector.
    assert physics.g_force_longitudinal == physics.g_force[2]
    assert physics.tyre_core_temp.as_tuple() == (80.0, 81.0, 82.0, 83.0)
    assert physics.tyre_pressure.front_left == pytest.approx(27.0, abs=1e-4)
    assert physics.brake_bias == pytest.approx(0.57, abs=1e-4)


def test_graphics_from_struct_maps_enums_and_strings() -> None:
    raw = SPageFileGraphic()
    raw.packetId = 7
    raw.status = ACStatus.LIVE
    raw.session = ACSessionType.QUALIFY
    raw.currentTime = "1:30.500"
    raw.completedLaps = 3
    raw.position = 2
    raw.iCurrentTime = 90500
    raw.normalizedCarPosition = 0.42
    _set_array(raw.carCoordinates, [12.0, 1.0, 34.0])
    raw.isInPit = 0
    raw.isInPitLane = 1
    raw.flag = ACFlagType.YELLOW
    raw.tyreCompound = "medium"
    raw.surfaceGrip = 0.98

    graphics = converters.graphics_from_struct(raw)

    assert graphics.status is ACStatus.LIVE
    assert graphics.session_type is ACSessionType.QUALIFY
    assert graphics.current_time == "1:30.500"
    assert graphics.completed_laps == 3
    assert round(graphics.normalized_car_position, 2) == 0.42
    assert graphics.is_in_pit is False
    assert graphics.is_in_pit_lane is True
    assert graphics.flag is ACFlagType.YELLOW
    assert graphics.tyre_compound == "medium"


def test_graphics_unknown_session_falls_back_to_unknown() -> None:
    raw = SPageFileGraphic()
    raw.session = 99  # not a valid AC_SESSION_TYPE
    graphics = converters.graphics_from_struct(raw)
    assert graphics.session_type is ACSessionType.UNKNOWN


def test_static_from_struct_maps_fields() -> None:
    raw = SPageFileStatic()
    raw.smVersion = "1.14.3"
    raw.acVersion = "1.16.4"
    raw.numCars = 12
    raw.carModel = "ks_ferrari_488_gt3"
    raw.track = "ks_red_bull_ring"
    raw.trackConfiguration = "layout_gp"
    raw.sectorCount = 3
    raw.maxRpm = 8500
    raw.maxFuel = 90.0
    raw.trackSPlineLength = 4318.0
    raw.penaltiesEnabled = 1
    raw.pitWindowStart = 5
    raw.pitWindowEnd = 15

    static = converters.static_from_struct(raw)

    assert static.car_model == "ks_ferrari_488_gt3"
    assert static.track == "ks_red_bull_ring"
    assert static.track_configuration == "layout_gp"
    assert static.num_cars == 12
    assert static.max_rpm == 8500
    assert static.penalties_enabled is True
    assert static.pit_window_end == 15


def test_frame_from_structs_assembles_full_frame() -> None:
    physics = SPageFilePhysics()
    physics.rpms = 6000
    graphics = SPageFileGraphic()
    graphics.status = ACStatus.LIVE
    static = SPageFileStatic()
    static.track = "ks_laguna_seca"

    frame = converters.frame_from_structs(
        physics, graphics, static, timestamp=12.5
    )

    assert frame.timestamp == 12.5
    assert frame.physics.rpm == 6000
    assert frame.static_info.track == "ks_laguna_seca"
    assert frame.is_live is True
