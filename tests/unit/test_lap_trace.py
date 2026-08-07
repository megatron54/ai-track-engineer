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


def test_is_clean_true_for_monotonic_lap() -> None:
    trace = LapTrace(1, [(0.0, 0.0, 100.0), (0.5, 10.0, 120.0), (0.9, 20.0, 110.0)])
    assert trace.is_clean is True


def test_is_clean_false_when_time_goes_backwards() -> None:
    # Positions increase but time jumps backwards: a lap trace stitched across a
    # mid-lap restart. Such a reference must be rejected by the delta pipeline.
    trace = LapTrace(1, [(0.1, 50.0, 100.0), (0.2, 5.0, 120.0), (0.9, 60.0, 110.0)])
    assert trace.is_clean is False


def test_input_channels_default_to_zero_for_legacy_samples() -> None:
    # Existing 3-tuple samples (no brake/gas/steer) must keep working.
    trace = LapTrace(1, [(0.0, 0.0, 100.0), (1.0, 30.0, 200.0)])
    assert trace.brake_at(0.5) == pytest.approx(0.0)
    assert trace.throttle_at(0.5) == pytest.approx(0.0)
    assert trace.steer_at(0.5) == pytest.approx(0.0)


def test_input_channels_interpolate() -> None:
    trace = LapTrace(
        1,
        [
            (0.0, 0.0, 100.0, 0.0, 1.0, 0.0),
            (0.5, 10.0, 100.0, 1.0, 0.0, 0.4),
            (1.0, 20.0, 100.0, 0.0, 1.0, -0.4),
        ],
    )
    assert trace.brake_at(0.25) == pytest.approx(0.5)
    assert trace.throttle_at(0.25) == pytest.approx(0.5)
    assert trace.steer_at(0.75) == pytest.approx(0.0)


def test_from_frames_captures_inputs() -> None:
    source = MockTelemetrySource(dt=0.05, lap_time_s=2.0)
    source.connect()
    frames = [source.read_frame() for _ in range(40)]
    source.close()
    trace = LapTrace.from_frames(1, frames)
    # Just needs to not blow up and return a real float for a mid-lap position.
    mid = (trace.start_position + trace.end_position) / 2
    assert isinstance(trace.brake_at(mid), float)
    assert isinstance(trace.throttle_at(mid), float)
    assert isinstance(trace.steer_at(mid), float)


def test_first_crossing_interpolates_between_samples() -> None:
    trace = LapTrace(
        1,
        [
            (0.0, 0.0, 100.0, 0.0, 0.0, 0.0),
            (0.30, 3.0, 100.0, 0.0, 0.0, 0.0),
            (0.32, 3.2, 100.0, 0.2, 0.0, 0.0),
            (0.34, 3.4, 100.0, 1.0, 0.0, 0.0),
        ],
    )
    crossing = trace.first_crossing("brake", 0.5, 0.0, 0.4)
    assert crossing == pytest.approx(0.3275)


def test_first_crossing_returns_none_when_never_reached() -> None:
    trace = LapTrace(
        1,
        [
            (0.0, 0.0, 100.0, 0.0, 0.0, 0.0),
            (0.5, 5.0, 100.0, 0.05, 0.0, 0.0),
            (1.0, 10.0, 100.0, 0.05, 0.0, 0.0),
        ],
    )
    assert trace.first_crossing("brake", 0.5, 0.0, 1.0) is None


def test_first_crossing_wraps_past_start_finish_line() -> None:
    trace = LapTrace(
        1,
        [
            (0.90, 9.0, 100.0, 0.0, 0.0, 0.0),
            (0.95, 9.5, 100.0, 0.2, 0.0, 0.0),
            (0.98, 9.8, 100.0, 1.0, 0.0, 0.0),
            (0.02, 10.2, 100.0, 1.0, 0.0, 0.0),
            (0.05, 10.5, 100.0, 0.0, 0.0, 0.0),
        ],
    )
    # Search window wraps: starts at 0.90, ends at 0.05 (past the line).
    crossing = trace.first_crossing("brake", 0.5, 0.90, 0.05)
    assert crossing is not None
    assert crossing == pytest.approx(0.96125)


def test_trail_braking_overlap_measures_simultaneous_inputs() -> None:
    trace = LapTrace(
        1,
        [
            (0.0, 0.0, 100.0, 1.0, 0.0, 0.3),  # brake + steer: overlap
            (0.1, 1.0, 100.0, 1.0, 0.0, 0.0),  # brake only
            (0.2, 2.0, 100.0, 0.0, 0.0, 0.3),  # steer only
            (0.3, 3.0, 100.0, 0.0, 1.0, 0.0),  # neither
        ],
    )
    assert trace.trail_braking_overlap(0.0, 0.3) == pytest.approx(0.25)


def test_steering_reversals_counts_direction_changes() -> None:
    trace = LapTrace(
        1,
        [
            (0.0, 0.0, 100.0, 0.0, 0.0, 0.1),
            (0.1, 1.0, 100.0, 0.0, 0.0, 0.15),
            (0.2, 2.0, 100.0, 0.0, 0.0, -0.1),
            (0.3, 3.0, 100.0, 0.0, 0.0, -0.15),
            (0.4, 4.0, 100.0, 0.0, 0.0, 0.1),
        ],
    )
    # +,+,-,-,+ -> two direction changes.
    assert trace.steering_reversals(0.0, 0.4) == 2


def test_steering_reversals_ignores_deadband_noise() -> None:
    trace = LapTrace(
        1,
        [
            (0.0, 0.0, 100.0, 0.0, 0.0, 0.2),
            (0.1, 1.0, 100.0, 0.0, 0.0, 0.005),  # inside the deadband, ignored
            (0.2, 2.0, 100.0, 0.0, 0.0, 0.2),
        ],
    )
    assert trace.steering_reversals(0.0, 0.2) == 0
