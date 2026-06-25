"""Tests for the capture-to-hub pump."""

from __future__ import annotations

from src.dashboard.hub import TelemetryHub
from src.dashboard.pump import capture_to_hub
from src.processing.lap_segmenter import LapSegmenter
from src.processing.models import Lap
from src.telemetry.mock import MockTelemetrySource


async def test_pump_publishes_frames_and_closes_source() -> None:
    source = MockTelemetrySource()
    hub = TelemetryHub(queue_size=1000)
    queue = hub.subscribe()

    processed = await capture_to_hub(source, hub, hz=2000, max_frames=20)

    assert processed == 20
    assert queue.qsize() == 20
    # Source was closed: reading again would require a reconnect.
    assert source._connected is False  # noqa: SLF001 - asserting lifecycle in test


async def test_pump_invokes_on_lap_for_completed_laps() -> None:
    source = MockTelemetrySource(dt=0.05, lap_time_s=1.0)
    hub = TelemetryHub(queue_size=1000)
    segmenter = LapSegmenter()
    recorded: list[Lap] = []

    async def record(lap: Lap) -> None:
        recorded.append(lap)

    await capture_to_hub(
        source, hub, hz=4000, max_frames=80, segmenter=segmenter, on_lap=record
    )

    # ~80 frames at dt=0.05 == 4s simulated over 1s laps -> at least 2 laps.
    assert len(recorded) >= 2
    assert all(lap.lap_number > 0 for lap in recorded)


async def test_pump_without_segmenter_skips_lap_callback() -> None:
    source = MockTelemetrySource()
    hub = TelemetryHub(queue_size=100)
    # No segmenter/on_lap -> just fans out frames without error.
    processed = await capture_to_hub(source, hub, hz=2000, max_frames=10)
    assert processed == 10
