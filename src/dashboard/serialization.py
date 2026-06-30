"""Serialise domain objects into dashboard event envelopes.

These builders turn domain objects into the envelopes that flow to the browser
over the WebSocket:

* ``session`` - sent once when a session loads (track, car, corners, map params).
* ``telemetry`` - per-frame state (speed, rpm, inputs, position, live delta).
* ``lap`` - emitted when a lap completes (time, sectors, personal best, advice).
* ``gap`` - gaps (seconds) and trends to the cars ahead and behind.

Keeping these builders pure makes the wire format easy to test and evolve.
"""

from __future__ import annotations

from typing import Any

from src.analysis.pipeline import LapReport
from src.knowledge.models import TrackInfo
from src.strategy.gap_manager import GapReport
from src.telemetry.models import TelemetryFrame


def session_event(
    track: TrackInfo, *, car: str, best_ever_ms: int | None = None
) -> dict[str, Any]:
    """Build the ``session`` envelope describing the active track and car.

    ``best_ever_ms`` is the all-time personal-best lap (ms) for this track/car
    from the lap store, so the dashboard can show a real historical best rather
    than only Assetto Corsa's current-session best.
    """
    projection = track.map
    map_payload: dict[str, Any] | None = None
    if projection is not None:
        map_payload = {
            "width": projection.width,
            "height": projection.height,
            "x_offset": projection.x_offset,
            "z_offset": projection.z_offset,
            "scale_factor": projection.scale_factor,
            "margin": projection.margin,
        }
    return {
        "type": "session",
        "track": track.name,
        "track_id": track.track_id,
        "car": car,
        "length_m": round(track.length_m, 1),
        "best_ever_ms": best_ever_ms,
        "corners": [
            {"index": c.index, "name": c.name, "entry": c.entry, "exit": c.exit}
            for c in track.corners
        ],
        "map": map_payload,
    }


def telemetry_event(frame: TelemetryFrame, *, delta: float | None = None) -> dict[str, Any]:
    """Build the ``telemetry`` envelope for a single frame."""
    physics = frame.physics
    graphics = frame.graphics
    return {
        "type": "telemetry",
        "t": round(frame.timestamp, 3),
        "speed_kmh": round(physics.speed_kmh, 1),
        "rpm": physics.rpm,
        "gear": physics.gear_label,
        "gas": round(physics.gas, 3),
        "brake": round(physics.brake, 3),
        "fuel": round(physics.fuel, 2),
        "lap_pos": round(graphics.normalized_car_position, 4),
        "coords": [round(graphics.car_coordinates[0], 2), round(graphics.car_coordinates[2], 2)],
        "position": graphics.position,
        "sector": graphics.current_sector_index,
        "current_time": graphics.current_time,
        "last_time": graphics.last_time,
        "best_time": graphics.best_time,
        "completed_laps": graphics.completed_laps,
        "tyre_temp": [round(v, 1) for v in physics.tyre_core_temp.as_tuple()],
        "tyre_wear": [round(v, 2) for v in physics.tyre_wear.as_tuple()],
        "steer_angle": round(physics.steer_angle, 3),
        "g_lat": round(physics.g_force_lateral, 3),
        "g_lon": round(physics.g_force_longitudinal, 3),
        "delta": round(delta, 3) if delta is not None else None,
        "status": graphics.status.name,
        "session": graphics.session_type.name,
    }


def lap_event(report: LapReport) -> dict[str, Any]:
    """Build the ``lap`` envelope for a completed lap report."""
    return {
        "type": "lap",
        "number": report.lap.lap_number,
        "time_ms": report.lap.lap_time_ms,
        "valid": report.lap.valid,
        "is_personal_best": report.is_personal_best,
        "sectors_ms": list(report.lap.sector_times_ms),
        "corner_losses": [
            {"corner": loss.corner_name, "delta_s": round(loss.delta_s, 3)}
            for loss in report.corner_losses
        ],
        "advice": [rec.message for rec in report.recommendations],
    }


def gap_event(report: GapReport) -> dict[str, Any]:
    """Build the ``gap`` envelope describing gaps to the cars ahead and behind."""
    return {
        "type": "gap",
        "ahead_s": report.gap_ahead_s,
        "behind_s": report.gap_behind_s,
        "trend_ahead": report.trend_ahead.value,
        "trend_behind": report.trend_behind.value,
        "contact_ahead_laps": report.contact_ahead_laps,
        "contact_behind_laps": report.contact_behind_laps,
        "message": report.message,
    }


# Backwards-compatible alias used by the minimal embedded page.
def frame_to_payload(frame: TelemetryFrame) -> dict[str, Any]:
    """Return a telemetry envelope (kept for compatibility)."""
    return telemetry_event(frame)
