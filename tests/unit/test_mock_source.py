"""Tests for the mock telemetry source."""

from __future__ import annotations

import pytest
from src.telemetry.mock import MockTelemetrySource, format_lap_time
from src.telemetry.source import SourceNotConnectedError


@pytest.mark.parametrize(
    ("ms", "expected"),
    [(0, "0:00.000"), (83456, "1:23.456"), (60000, "1:00.000"), (-1, "--:--.---")],
)
def test_format_lap_time(ms: int, expected: str) -> None:
    assert format_lap_time(ms) == expected


def test_read_static_returns_current_static() -> None:
    source = MockTelemetrySource(car_model="ks_test_car")
    static = source.connect()
    assert source.read_static() is static
    assert source.read_static().car_model == "ks_test_car"


def test_invalid_constructor_args() -> None:
    with pytest.raises(ValueError, match="dt must be positive"):
        MockTelemetrySource(dt=0.0)
    with pytest.raises(ValueError, match="lap_time_s must be positive"):
        MockTelemetrySource(lap_time_s=0.0)


def test_read_before_connect_raises() -> None:
    source = MockTelemetrySource()
    with pytest.raises(SourceNotConnectedError):
        source.read_frame()


def test_connect_returns_static_info() -> None:
    source = MockTelemetrySource(track="ks_monza", max_rpm=9000)
    static_info = source.connect()
    assert static_info.track == "ks_monza"
    assert static_info.max_rpm == 9000


def test_position_advances_and_wraps_to_new_lap() -> None:
    source = MockTelemetrySource(dt=1.0, lap_time_s=10.0)
    source.connect()
    frames = [source.read_frame() for _ in range(11)]
    assert frames[0].graphics.normalized_car_position == pytest.approx(0.0)
    assert frames[0].graphics.completed_laps == 0
    # The 11th read advances simulated time to 10s == one full lap.
    assert frames[10].graphics.completed_laps == 1
    assert frames[10].graphics.normalized_car_position == pytest.approx(0.0, abs=1e-9)


def test_speed_and_rpm_stay_within_bounds() -> None:
    source = MockTelemetrySource(dt=0.5, lap_time_s=20.0)
    static_info = source.connect()
    for _ in range(40):
        frame = source.read_frame()
        assert 0.0 < frame.physics.speed_kmh <= 240.0
        assert 0 <= frame.physics.rpm <= static_info.max_rpm


def test_fuel_decreases_across_laps() -> None:
    source = MockTelemetrySource(dt=1.0, lap_time_s=5.0, fuel_start_l=10.0, fuel_per_lap_l=2.0)
    source.connect()
    frames = [source.read_frame() for _ in range(12)]
    assert frames[0].physics.fuel == pytest.approx(10.0)
    assert frames[-1].physics.fuel < 10.0


def test_output_is_deterministic() -> None:
    first = MockTelemetrySource()
    second = MockTelemetrySource()
    first.connect()
    second.connect()
    for _ in range(20):
        frame_a = first.read_frame()
        frame_b = second.read_frame()
        assert frame_a.physics.speed_kmh == frame_b.physics.speed_kmh
        assert (
            frame_a.graphics.normalized_car_position
            == frame_b.graphics.normalized_car_position
        )


async def test_mock_works_with_stream() -> None:
    source = MockTelemetrySource()
    source.connect()
    frames = [frame async for frame in source.stream(240, max_frames=10)]
    source.close()
    assert len(frames) == 10
    assert all(frame.is_live for frame in frames)
