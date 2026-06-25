"""Tests for the AI context builder."""

from __future__ import annotations

from src.ai.context_builder import build_lap_context
from src.analysis.engine_monitor import AlertSeverity, EngineAlert
from src.analysis.models import CornerDelta
from src.analysis.tyre_model import ThermalStatus, TyreThermalReport
from src.knowledge.models import Corner, TrackInfo
from src.processing.models import Lap

_TRACK = TrackInfo(
    track_id="ks_laguna_seca",
    name="Laguna Seca",
    corners=(Corner(index=7, name="The Corkscrew", entry=0.665, exit=0.717),),
)


def test_context_includes_lap_time_and_track() -> None:
    lap = Lap(lap_number=3, lap_time_ms=88_500, sector_times_ms=(30_000, 29_000, 29_500))
    context = build_lap_context(lap=lap, track=_TRACK)
    assert "Laguna Seca" in context
    assert "88.500s" in context
    assert "S1 30.000s" in context
    assert "No reference lap yet" in context


def test_context_includes_corner_losses_and_tyres() -> None:
    lap = Lap(lap_number=5, lap_time_ms=90_000)
    losses = [CornerDelta(corner_index=7, corner_name="The Corkscrew", delta_s=0.42)]
    tyre = TyreThermalReport(
        statuses=(
            ThermalStatus.HOT,
            ThermalStatus.HOT,
            ThermalStatus.OPTIMAL,
            ThermalStatus.OPTIMAL,
        ),
        core_temps=(110.0, 108.0, 95.0, 95.0),
        front_rear_delta=14.0,
    )
    alerts = [
        EngineAlert(kind="over_rev", severity=AlertSeverity.CRITICAL, message="Over-rev", rpm=8200)
    ]
    context = build_lap_context(
        lap=lap, track=_TRACK, corner_losses=losses, tyre_report=tyre, engine_alerts=alerts
    )
    assert "The Corkscrew: +0.420s" in context
    assert "hot/hot/optimal/optimal" in context
    assert "over_rev@8200rpm" in context


def test_context_marks_invalid_lap() -> None:
    lap = Lap(lap_number=2, lap_time_ms=95_000, valid=False)
    assert "INVALID" in build_lap_context(lap=lap, track=_TRACK)
