"""Reusable builders for telemetry test data.

These factories construct valid domain models with sensible defaults so each
test only specifies the fields it cares about. Keeping them here avoids
duplicating large keyword-argument blocks across the test suite.
"""

from __future__ import annotations

from typing import Any

from src.telemetry.models import (
    ACGraphics,
    ACPhysics,
    ACStaticInfo,
    TelemetryFrame,
    Wheels,
)
from src.telemetry.shm_structs import ACFlagType, ACSessionType, ACStatus


def make_wheels(value: float = 0.0) -> Wheels:
    """A :class:`Wheels` with all four corners set to *value*."""
    return Wheels.of([value, value, value, value])


def make_physics(**overrides: Any) -> ACPhysics:
    """Build an :class:`ACPhysics` with defaults overridable by keyword."""
    defaults: dict[str, Any] = {
        "packet_id": 1,
        "gas": 0.5,
        "brake": 0.0,
        "clutch": 0.0,
        "steer_angle": 0.0,
        "gear": 3,
        "rpm": 7000,
        "speed_kmh": 180.0,
        "fuel": 40.0,
        "g_force": (0.0, 0.0, 0.0),
        "velocity": (0.0, 0.0, 50.0),
        "tyre_core_temp": make_wheels(85.0),
        "tyre_temp_inner": make_wheels(86.0),
        "tyre_temp_middle": make_wheels(85.0),
        "tyre_temp_outer": make_wheels(84.0),
        "tyre_pressure": make_wheels(27.5),
        "tyre_wear": make_wheels(100.0),
        "wheel_slip": make_wheels(0.0),
        "brake_temp": make_wheels(350.0),
        "suspension_travel": make_wheels(0.02),
        "tc": 0.0,
        "abs": 0.0,
        "turbo_boost": 0.0,
        "brake_bias": 0.58,
        "air_temp": 24.0,
        "road_temp": 30.0,
    }
    defaults.update(overrides)
    return ACPhysics(**defaults)


def make_graphics(**overrides: Any) -> ACGraphics:
    """Build an :class:`ACGraphics` with defaults overridable by keyword."""
    defaults: dict[str, Any] = {
        "packet_id": 1,
        "status": ACStatus.LIVE,
        "session_type": ACSessionType.PRACTICE,
        "current_time": "1:23.456",
        "last_time": "1:24.000",
        "best_time": "1:23.000",
        "split": "-0.123",
        "completed_laps": 2,
        "position": 1,
        "current_time_ms": 83456,
        "last_time_ms": 84000,
        "best_time_ms": 83000,
        "session_time_left": 600.0,
        "distance_traveled": 5000.0,
        "current_sector_index": 1,
        "last_sector_time_ms": 28000,
        "number_of_laps": 0,
        "is_in_pit": False,
        "is_in_pit_lane": False,
        "tyre_compound": "soft",
        "normalized_car_position": 0.5,
        "car_coordinates": (10.0, 0.0, 20.0),
        "flag": ACFlagType.NONE,
        "surface_grip": 1.0,
    }
    defaults.update(overrides)
    return ACGraphics(**defaults)


def make_static(**overrides: Any) -> ACStaticInfo:
    """Build an :class:`ACStaticInfo` with defaults overridable by keyword."""
    defaults: dict[str, Any] = {
        "sm_version": "1.14.3",
        "ac_version": "1.16.4",
        "num_cars": 1,
        "car_model": "ks_ferrari_488_gt3",
        "track": "ks_laguna_seca",
        "track_configuration": "",
        "car_skin": "default",
        "sector_count": 3,
        "max_torque": 700.0,
        "max_power": 500000.0,
        "max_rpm": 8500,
        "max_fuel": 90.0,
        "track_spline_length": 3602.0,
        "penalties_enabled": True,
        "pit_window_start": 0,
        "pit_window_end": 0,
    }
    defaults.update(overrides)
    return ACStaticInfo(**defaults)


def make_frame(
    *,
    timestamp: float = 0.0,
    status: ACStatus = ACStatus.LIVE,
    normalized_car_position: float = 0.5,
    **physics_overrides: Any,
) -> TelemetryFrame:
    """Build a :class:`TelemetryFrame` for tests.

    Common knobs (``status``, ``normalized_car_position``) are surfaced
    directly; any remaining keyword arguments override physics fields.
    """
    return TelemetryFrame(
        timestamp=timestamp,
        physics=make_physics(**physics_overrides),
        graphics=make_graphics(
            status=status, normalized_car_position=normalized_car_position
        ),
        static_info=make_static(),
    )
