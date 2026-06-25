"""Convert raw shared-memory structures into validated domain models.

This is the single bridge between the ctypes layer and the rest of the
application. Isolating it here keeps ctypes specifics (array access, enum
coercion) out of the domain models and makes the mapping straightforward to
unit-test with in-memory structures.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.telemetry.models import (
    ACGraphics,
    ACPhysics,
    ACStaticInfo,
    TelemetryFrame,
    Wheels,
)
from src.telemetry.shm_structs import (
    ACFlagType,
    ACSessionType,
    ACStatus,
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)


def _vec3(array: Iterable[float]) -> tuple[float, float, float]:
    """Coerce a ``c_float * 3`` ctypes array into a float 3-tuple."""
    x, y, z = list(array)
    return (float(x), float(y), float(z))


def physics_from_struct(raw: SPageFilePhysics) -> ACPhysics:
    """Map a :class:`SPageFilePhysics` structure to :class:`ACPhysics`."""
    return ACPhysics(
        packet_id=int(raw.packetId),
        gas=float(raw.gas),
        brake=float(raw.brake),
        clutch=float(raw.clutch),
        steer_angle=float(raw.steerAngle),
        gear=int(raw.gear),
        rpm=int(raw.rpms),
        speed_kmh=float(raw.speedKmh),
        fuel=float(raw.fuel),
        g_force=_vec3(raw.accG),
        velocity=_vec3(raw.velocity),
        tyre_core_temp=Wheels.of(list(raw.tyreCoreTemperature)),
        tyre_temp_inner=Wheels.of(list(raw.tyreTempI)),
        tyre_temp_middle=Wheels.of(list(raw.tyreTempM)),
        tyre_temp_outer=Wheels.of(list(raw.tyreTempO)),
        tyre_pressure=Wheels.of(list(raw.wheelsPressure)),
        tyre_wear=Wheels.of(list(raw.tyreWear)),
        wheel_slip=Wheels.of(list(raw.wheelSlip)),
        brake_temp=Wheels.of(list(raw.brakeTemp)),
        suspension_travel=Wheels.of(list(raw.suspensionTravel)),
        tc=float(raw.tc),
        abs=float(raw.abs),
        turbo_boost=float(raw.turboBoost),
        brake_bias=float(raw.brakeBias),
        air_temp=float(raw.airTemp),
        road_temp=float(raw.roadTemp),
    )


def graphics_from_struct(raw: SPageFileGraphic) -> ACGraphics:
    """Map a :class:`SPageFileGraphic` structure to :class:`ACGraphics`."""
    return ACGraphics(
        packet_id=int(raw.packetId),
        status=ACStatus(int(raw.status)),
        session_type=_safe_session_type(int(raw.session)),
        current_time=str(raw.currentTime),
        last_time=str(raw.lastTime),
        best_time=str(raw.bestTime),
        split=str(raw.split),
        completed_laps=int(raw.completedLaps),
        position=int(raw.position),
        current_time_ms=int(raw.iCurrentTime),
        last_time_ms=int(raw.iLastTime),
        best_time_ms=int(raw.iBestTime),
        session_time_left=float(raw.sessionTimeLeft),
        distance_traveled=float(raw.distanceTraveled),
        current_sector_index=int(raw.currentSectorIndex),
        last_sector_time_ms=int(raw.lastSectorTime),
        number_of_laps=int(raw.numberOfLaps),
        is_in_pit=bool(raw.isInPit),
        is_in_pit_lane=bool(raw.isInPitLane),
        tyre_compound=str(raw.tyreCompound),
        normalized_car_position=float(raw.normalizedCarPosition),
        car_coordinates=_vec3(raw.carCoordinates),
        flag=ACFlagType(int(raw.flag)),
        surface_grip=float(raw.surfaceGrip),
    )


def static_from_struct(raw: SPageFileStatic) -> ACStaticInfo:
    """Map a :class:`SPageFileStatic` structure to :class:`ACStaticInfo`."""
    return ACStaticInfo(
        sm_version=str(raw.smVersion),
        ac_version=str(raw.acVersion),
        num_cars=int(raw.numCars),
        car_model=str(raw.carModel),
        track=str(raw.track),
        track_configuration=str(raw.trackConfiguration),
        car_skin=str(raw.carSkin),
        sector_count=int(raw.sectorCount),
        max_torque=float(raw.maxTorque),
        max_power=float(raw.maxPower),
        max_rpm=int(raw.maxRpm),
        max_fuel=float(raw.maxFuel),
        track_spline_length=float(raw.trackSPlineLength),
        penalties_enabled=bool(raw.penaltiesEnabled),
        pit_window_start=int(raw.pitWindowStart),
        pit_window_end=int(raw.pitWindowEnd),
    )


def frame_from_structs(
    physics: SPageFilePhysics,
    graphics: SPageFileGraphic,
    static: SPageFileStatic,
    *,
    timestamp: float,
) -> TelemetryFrame:
    """Assemble a :class:`TelemetryFrame` from the three raw pages."""
    return TelemetryFrame(
        timestamp=timestamp,
        physics=physics_from_struct(physics),
        graphics=graphics_from_struct(graphics),
        static_info=static_from_struct(static),
    )


def _safe_session_type(value: int) -> ACSessionType:
    """Coerce a raw session value, tolerating unexpected codes."""
    try:
        return ACSessionType(value)
    except ValueError:
        return ACSessionType.UNKNOWN
