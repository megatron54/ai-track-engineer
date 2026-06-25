"""Serialise telemetry frames into compact JSON payloads for the dashboard.

Kept separate from the transport so the wire format is easy to test and evolve
independently of the WebSocket handler.
"""

from __future__ import annotations

from typing import Any

from src.telemetry.models import TelemetryFrame


def frame_to_payload(frame: TelemetryFrame) -> dict[str, Any]:
    """Convert a telemetry frame into a JSON-serialisable dashboard payload."""
    physics = frame.physics
    graphics = frame.graphics
    return {
        "t": round(frame.timestamp, 3),
        "speed_kmh": round(physics.speed_kmh, 1),
        "rpm": physics.rpm,
        "gear": physics.gear_label,
        "gas": round(physics.gas, 3),
        "brake": round(physics.brake, 3),
        "fuel": round(physics.fuel, 2),
        "lap_pos": round(graphics.normalized_car_position, 4),
        "current_time": graphics.current_time,
        "last_time": graphics.last_time,
        "best_time": graphics.best_time,
        "completed_laps": graphics.completed_laps,
        "tyre_temp": [round(value, 1) for value in physics.tyre_core_temp.as_tuple()],
        "status": graphics.status.name,
        "session": graphics.session_type.name,
    }
