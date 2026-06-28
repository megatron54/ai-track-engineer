"""Tests for building corner training samples from recorded telemetry."""

from __future__ import annotations

import pytest
from src.knowledge.models import Corner
from src.ml.corner_dataset import build_corner_samples
from src.ml.recorded_session import TelemetrySample


def _samples(
    lap: int,
    *,
    n: int = 200,
    brake_zone: tuple[float, float] | None = None,
    speed: float = 200.0,
) -> list[TelemetrySample]:
    """A lap of ``n`` samples 0->1 with optional braking over a position range."""
    out: list[TelemetrySample] = []
    for i in range(n):
        pos = i / (n - 1)
        braking = brake_zone is not None and brake_zone[0] <= pos <= brake_zone[1]
        out.append(
            TelemetrySample(
                lap=lap,
                lap_pos=pos,
                timestamp=i * 0.1,
                speed_kmh=speed,
                gear=5,
                brake=0.5 if braking else 0.0,
                g_lat=1.0,
                tyre_temp_avg=95.0,
            )
        )
    return out


def test_build_corner_samples_extracts_entry_and_time() -> None:
    corners = [Corner(index=1, name="T1", entry=0.2, exit=0.4)]
    samples = _samples(1, n=200, brake_zone=(0.13, 0.18), speed=180.0)
    rows = build_corner_samples({1: samples}, corners, [1])
    assert len(rows) == 1
    row = rows[0]
    assert row.lap == 1
    assert row.corner_index == 1
    assert row.entry_speed_kmh == 180.0
    assert row.entry_gear == 5
    assert row.corner_time_s == pytest.approx(3.9, abs=0.3)
    assert row.brake_point_pos == pytest.approx(0.13, abs=0.02)
    assert row.entry_g_lat == pytest.approx(1.0)


def test_brake_point_defaults_to_entry_without_braking() -> None:
    corners = [Corner(index=1, name="T1", entry=0.2, exit=0.4)]
    rows = build_corner_samples({1: _samples(1, n=200)}, corners, [1])
    assert rows[0].brake_point_pos == pytest.approx(0.2, abs=0.01)


def test_multiple_corners_and_lap_filter() -> None:
    corners = [
        Corner(index=1, name="T1", entry=0.1, exit=0.2),
        Corner(index=2, name="T2", entry=0.6, exit=0.7),
    ]
    by_lap = {1: _samples(1, n=300), 2: _samples(2, n=300)}
    rows = build_corner_samples(by_lap, corners, [1])  # only lap 1 requested
    assert {row.lap for row in rows} == {1}
    assert {row.corner_index for row in rows} == {1, 2}


def test_corner_with_too_few_samples_is_skipped() -> None:
    corners = [Corner(index=1, name="T1", entry=0.999, exit=0.9995)]
    rows = build_corner_samples({1: _samples(1, n=50)}, corners, [1])
    assert rows == []


def test_missing_lap_is_ignored() -> None:
    corners = [Corner(index=1, name="T1", entry=0.2, exit=0.4)]
    rows = build_corner_samples({1: _samples(1)}, corners, [2, 3])
    assert rows == []
