"""Tests for telemetry and lap event serialization."""

from __future__ import annotations

import json

from src.ai.models import Priority, Recommendation
from src.analysis.models import CornerDelta
from src.analysis.pipeline import LapReport
from src.dashboard.serialization import gap_event, lap_event, telemetry_event
from src.processing.models import Lap
from src.strategy.gap_manager import GapManager

from tests.factories import make_frame, make_graphics


def test_telemetry_event_shape_and_json_safe() -> None:
    graphics = make_graphics(
        normalized_car_position=0.5,
        car_coordinates=(-188.59, 5.32, -254.52),
        position=3,
        current_sector_index=1,
    )
    frame = make_frame(graphics=graphics, speed_kmh=210.4, rpm=8000, gear=5)
    event = telemetry_event(frame, delta=-0.123)

    assert event["type"] == "telemetry"
    assert event["speed_kmh"] == 210.4
    assert event["gear"] == "4"
    assert event["coords"] == [-188.59, -254.52]  # x and z, not y
    assert event["position"] == 3
    assert event["sector"] == 1
    assert event["delta"] == -0.123
    json.dumps(event)  # must be JSON-serialisable


def test_telemetry_event_delta_none() -> None:
    assert telemetry_event(make_frame())["delta"] is None


def test_telemetry_event_includes_steer_wear_and_gforces() -> None:
    event = telemetry_event(make_frame())
    assert isinstance(event["tyre_wear"], list)
    assert len(event["tyre_wear"]) == 4
    assert isinstance(event["tyre_temp"], list)
    assert len(event["tyre_temp"]) == 4
    assert "steer_angle" in event
    assert "g_lat" in event
    assert "g_lon" in event
    json.dumps(event)  # must stay JSON-serialisable


def test_lap_event_includes_advice_and_losses() -> None:
    report = LapReport(
        lap=Lap(lap_number=3, lap_time_ms=90_500, sector_times_ms=(30_000, 30_000, 30_500)),
        is_personal_best=True,
        corner_losses=(CornerDelta(corner_index=7, corner_name="Corkscrew", delta_s=0.42),),
        recommendations=(
            Recommendation(priority=Priority.HIGH, message="[Corkscrew] brake later"),
        ),
    )
    event = lap_event(report)
    assert event["type"] == "lap"
    assert event["number"] == 3
    assert event["is_personal_best"] is True
    assert event["sectors_ms"] == [30_000, 30_000, 30_500]
    assert event["corner_losses"][0]["corner"] == "Corkscrew"
    assert event["advice"] == ["[Corkscrew] brake later"]
    json.dumps(event)


def test_gap_event_shape() -> None:
    gm = GapManager(window=5)
    for gap in [3.0, 2.5, 2.0, 1.5, 1.0]:
        gm.update(gap_ahead_s=gap, gap_behind_s=None)
    event = gap_event(gm.report())
    assert event["type"] == "gap"
    assert event["ahead_s"] == 1.0
    assert event["trend_ahead"] == "closing"
    assert event["contact_ahead_laps"] is not None
    assert event["behind_s"] is None
    assert event["trend_behind"] == "stable"
    assert "message" in event
    json.dumps(event)
