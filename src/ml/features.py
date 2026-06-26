"""Feature engineering for ML models.

Extracts a flat feature vector from a telemetry frame that an XGBoost or
scikit-learn model can consume. Features are grouped into driver inputs,
motion, tyres, and position so downstream models can select relevant subsets.

This module is intentionally dependency-free (no sklearn/xgboost) so it can
run in the normal (non-ML) install; only the training scripts need the ML
extras.
"""

from __future__ import annotations

from typing import Any

from src.telemetry.models import TelemetryFrame


def frame_features(frame: TelemetryFrame) -> dict[str, Any]:
    """Extract a flat feature dict from a telemetry frame."""
    physics = frame.physics
    graphics = frame.graphics
    temps = physics.tyre_core_temp.as_tuple()
    pressures = physics.tyre_pressure.as_tuple()
    wear = physics.tyre_wear.as_tuple()
    return {
        # Driver inputs.
        "gas": round(physics.gas, 4),
        "brake": round(physics.brake, 4),
        "clutch": round(physics.clutch, 4),
        "steer_angle": round(physics.steer_angle, 2),
        # Motion.
        "speed_kmh": round(physics.speed_kmh, 2),
        "rpm": physics.rpm,
        "gear": physics.gear,
        "g_lat": round(physics.g_force_lateral, 4),
        "g_lon": round(physics.g_force_longitudinal, 4),
        # Position.
        "lap_pos": round(graphics.normalized_car_position, 5),
        "sector": graphics.current_sector_index,
        # Tyres.
        "tyre_temp_avg": round(sum(temps) / 4.0, 2),
        "tyre_temp_spread": round(max(temps) - min(temps), 2),
        "tyre_press_avg": round(sum(pressures) / 4.0, 3),
        "tyre_wear_avg": round(sum(wear) / 4.0, 2),
        # Environment.
        "fuel": round(physics.fuel, 3),
        "brake_bias": round(physics.brake_bias, 4),
    }


def corner_entry_features(
    speed_kmh: float,
    brake_point_pos: float,
    gear: int,
    g_lat: float,
) -> dict[str, float]:
    """Minimal feature set for the corner-time predictor.

    These are the inputs the driver controls at corner entry that most affect
    the time through the corner.
    """
    return {
        "entry_speed_kmh": round(speed_kmh, 2),
        "brake_point_pos": round(brake_point_pos, 5),
        "entry_gear": float(gear),
        "entry_g_lat": round(g_lat, 4),
    }
