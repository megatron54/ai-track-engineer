"""Tests for lap traces."""

from __future__ import annotations

import pytest
from src.processing.lap_trace import LapTrace
from src.telemetry.mock import MockTelemetrySource


def test_trace_requires_two_samples() -> None:
    with pytest.raises(ValueError, match="at least 2 samples"):
        LapTrace(1, [(0.0, 0.0, 100.0)])


def test_trace_rebases_time_and_interpolates() -> None:
    # A lap where time advances linearly with position over 90 s.
    samples = [(0.0, 1000.0, 150.0), (0.5, 1045.0, 150.0), (1.0, 1090.0, 150.0)]
    trace = LapTrace(3, samples)
    assert trace.lap_number == 3
    assert trace.duration == pytest.approx(90.0)
    assert trace.time_at(0.0) == pytest.approx(0.0)
    assert trace.time_at(0.25) == pytest.approx(22.5)
    assert trace.time_at(1.0) == pytest.approx(90.0)


def test_trace_drops_non_increasing_positions() -> None:
    samples = [(0.0, 0.0, 100.0), (0.3, 10.0, 100.0), (0.3, 11.0, 100.0), (0.6, 20.0, 100.0)]
    trace = LapTrace(1, samples)
    # Duplicate 0.3 dropped; still interpolates cleanly.
    assert trace.segment_time(0.0, 0.6) == pytest.approx(20.0)


def test_speed_interpolation() -> None:
    trace = LapTrace(1, [(0.0, 0.0, 100.0), (1.0, 30.0, 200.0)])
    assert trace.speed_at(0.5) == pytest.approx(150.0)


def test_from_frames_builds_trace() -> None:
    source = MockTelemetrySource(dt=0.05, lap_time_s=2.0)
    source.connect()
    frames = [source.read_frame() for _ in range(40)]
    source.close()
    trace = LapTrace.from_frames(1, frames)
    assert trace.duration > 0
    assert 0.0 <= trace.start_position < trace.end_position <= 1.0
