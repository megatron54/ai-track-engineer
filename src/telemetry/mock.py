"""A deterministic mock telemetry source for development without Assetto Corsa.

:class:`MockTelemetrySource` simulates a car lapping a circuit: the normalised
track position advances each frame, while speed, RPM, gear, fuel and tyre
temperatures follow simple but coherent models. It is deterministic — each
``read_frame`` advances simulated time by a fixed ``dt`` — which makes it ideal
for tests and for driving the dashboard offline.
"""

from __future__ import annotations

import math

from src.telemetry.models import (
    ACGraphics,
    ACPhysics,
    ACStaticInfo,
    TelemetryFrame,
    Wheels,
)
from src.telemetry.shm_structs import ACFlagType, ACSessionType, ACStatus
from src.telemetry.source import SourceNotConnectedError, TelemetrySource

_MIN_SPEED_KMH = 80.0
_MAX_SPEED_KMH = 240.0
_CORNERS_PER_LAP = 8
_GEAR_SPEED_STEP = 35.0  # km/h per gear band (rough)
_MAX_GEARS = 6


def format_lap_time(ms: int) -> str:
    """Format milliseconds as ``m:ss.mmm`` (Assetto Corsa style)."""
    if ms < 0:
        return "--:--.---"
    minutes, remainder = divmod(ms, 60_000)
    seconds = remainder / 1000.0
    return f"{minutes}:{seconds:06.3f}"


class MockTelemetrySource(TelemetrySource):
    """Generate synthetic telemetry for a car lapping a circuit."""

    def __init__(
        self,
        *,
        dt: float = 1.0 / 60.0,
        lap_time_s: float = 90.0,
        track: str = "ks_laguna_seca",
        car_model: str = "ks_ferrari_488_gt3",
        track_length_m: float = 3602.0,
        max_rpm: int = 8500,
        fuel_start_l: float = 40.0,
        fuel_per_lap_l: float = 2.4,
    ) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        if lap_time_s <= 0:
            raise ValueError("lap_time_s must be positive")
        self._dt = dt
        self._lap_time_s = lap_time_s
        self._track = track
        self._car_model = car_model
        self._track_length_m = track_length_m
        self._max_rpm = max_rpm
        self._fuel_start_l = fuel_start_l
        self._fuel_per_lap_l = fuel_per_lap_l

        self._sim_time = 0.0
        self._packet_id = 0
        self._connected = False
        self._static = self._build_static()

    # -- TelemetrySource interface -----------------------------------------
    def connect(self) -> ACStaticInfo:
        self._connected = True
        self._sim_time = 0.0
        self._packet_id = 0
        return self._static

    def read_frame(self) -> TelemetryFrame:
        if not self._connected:
            raise SourceNotConnectedError("call connect() before read_frame()")
        if self._packet_id > 0:
            self._sim_time += self._dt
        self._packet_id += 1

        lap_progress = (self._sim_time % self._lap_time_s) / self._lap_time_s
        completed_laps = int(self._sim_time // self._lap_time_s)
        lap_time_ms = int((self._sim_time % self._lap_time_s) * 1000)
        full_lap_ms = int(self._lap_time_s * 1000)
        reference_time = format_lap_time(full_lap_ms) if completed_laps else "--:--.---"

        speed = self._speed_at(lap_progress)
        gear = self._gear_for_speed(speed)
        rpm = self._rpm_for(speed, gear)
        gas, brake = self._pedals_at(lap_progress)
        fuel = max(0.0, self._fuel_start_l - completed_laps * self._fuel_per_lap_l)
        tyre_temp = self._tyre_temp(lap_progress)

        physics = ACPhysics(
            packet_id=self._packet_id,
            gas=gas,
            brake=brake,
            clutch=0.0,
            steer_angle=self._steer_at(lap_progress),
            gear=gear + 1,  # AC raw gear: 0=R, 1=N, 2=1st -> gear index 1 == 1st
            rpm=rpm,
            speed_kmh=speed,
            fuel=fuel,
            g_force=self._g_force_at(lap_progress),
            velocity=(0.0, 0.0, speed / 3.6),
            tyre_core_temp=Wheels.of([tyre_temp] * 4),
            tyre_temp_inner=Wheels.of([tyre_temp + 2.0] * 4),
            tyre_temp_middle=Wheels.of([tyre_temp] * 4),
            tyre_temp_outer=Wheels.of([tyre_temp - 2.0] * 4),
            tyre_pressure=Wheels.of([27.5] * 4),
            tyre_wear=Wheels.of([max(0.0, 100.0 - completed_laps * 1.5)] * 4),
            wheel_slip=Wheels.of([brake * 0.3] * 4),
            brake_temp=Wheels.of([300.0 + brake * 250.0] * 4),
            suspension_travel=Wheels.of([0.02] * 4),
            tc=0.0,
            abs=0.0,
            turbo_boost=0.0,
            brake_bias=0.58,
            air_temp=24.0,
            road_temp=30.0,
        )
        graphics = ACGraphics(
            packet_id=self._packet_id,
            status=ACStatus.LIVE,
            session_type=ACSessionType.PRACTICE,
            current_time=format_lap_time(lap_time_ms),
            last_time=reference_time,
            best_time=reference_time,
            split="",
            completed_laps=completed_laps,
            position=1,
            current_time_ms=lap_time_ms,
            last_time_ms=full_lap_ms if completed_laps else 0,
            best_time_ms=full_lap_ms if completed_laps else 0,
            session_time_left=0.0,
            distance_traveled=self._sim_time / self._lap_time_s * self._track_length_m,
            current_sector_index=min(2, int(lap_progress * 3)),
            last_sector_time_ms=0,
            number_of_laps=0,
            is_in_pit=False,
            is_in_pit_lane=False,
            tyre_compound="soft",
            normalized_car_position=lap_progress,
            car_coordinates=self._coords_at(lap_progress),
            flag=ACFlagType.NONE,
            surface_grip=1.0,
        )
        return TelemetryFrame(
            timestamp=self._sim_time,
            physics=physics,
            graphics=graphics,
            static_info=self._static,
        )

    def close(self) -> None:
        self._connected = False

    # -- Internal models ---------------------------------------------------
    def _build_static(self) -> ACStaticInfo:
        return ACStaticInfo(
            sm_version="mock",
            ac_version="mock",
            num_cars=1,
            car_model=self._car_model,
            track=self._track,
            track_configuration="",
            car_skin="default",
            sector_count=3,
            max_torque=700.0,
            max_power=500_000.0,
            max_rpm=self._max_rpm,
            max_fuel=self._fuel_start_l,
            track_spline_length=self._track_length_m,
            penalties_enabled=True,
            pit_window_start=0,
            pit_window_end=0,
        )

    def _corner_factor(self, progress: float) -> float:
        """0 at the slowest point of a corner, 1 on the straights."""
        return 0.5 + 0.5 * math.sin(2.0 * math.pi * progress * _CORNERS_PER_LAP)

    def _speed_at(self, progress: float) -> float:
        return _MIN_SPEED_KMH + (_MAX_SPEED_KMH - _MIN_SPEED_KMH) * self._corner_factor(progress)

    def _gear_for_speed(self, speed: float) -> int:
        return max(1, min(_MAX_GEARS, 1 + int(speed // _GEAR_SPEED_STEP)))

    def _rpm_for(self, speed: float, gear: int) -> int:
        band = speed - (gear - 1) * _GEAR_SPEED_STEP
        frac = max(0.0, min(1.0, band / _GEAR_SPEED_STEP))
        return int(2500 + frac * (self._max_rpm - 2500))

    def _pedals_at(self, progress: float) -> tuple[float, float]:
        slope = math.cos(2.0 * math.pi * progress * _CORNERS_PER_LAP)
        if slope >= 0:
            return (min(1.0, slope + 0.2), 0.0)
        return (0.0, min(1.0, -slope))

    def _steer_at(self, progress: float) -> float:
        return 15.0 * math.sin(2.0 * math.pi * progress * _CORNERS_PER_LAP)

    def _g_force_at(self, progress: float) -> tuple[float, float, float]:
        lateral = 2.0 * math.sin(2.0 * math.pi * progress * _CORNERS_PER_LAP)
        longitudinal = 1.5 * math.cos(2.0 * math.pi * progress * _CORNERS_PER_LAP)
        return (lateral, 0.0, longitudinal)

    def _tyre_temp(self, progress: float) -> float:
        return 80.0 + 10.0 * self._corner_factor(progress)

    def _coords_at(self, progress: float) -> tuple[float, float, float]:
        angle = 2.0 * math.pi * progress
        radius = self._track_length_m / (2.0 * math.pi)
        return (radius * math.cos(angle), 0.0, radius * math.sin(angle))
