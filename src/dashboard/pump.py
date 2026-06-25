"""Capture orchestration: pump telemetry frames into the hub and processors.

``capture_to_hub`` is the glue between a telemetry source and the rest of the
system: it streams frames, publishes them to the dashboard hub, runs lap
segmentation, and invokes an optional callback for each completed lap (e.g. to
persist it). It owns the source lifecycle so callers cannot leak it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.dashboard.hub import TelemetryHub
from src.processing.lap_segmenter import LapSegmenter
from src.processing.models import Lap
from src.telemetry.source import TelemetrySource

LapCallback = Callable[[Lap], Awaitable[None]]


async def capture_to_hub(
    source: TelemetrySource,
    hub: TelemetryHub,
    *,
    hz: int,
    max_frames: int | None = None,
    segmenter: LapSegmenter | None = None,
    on_lap: LapCallback | None = None,
) -> int:
    """Stream frames from *source*, fanning them out and segmenting laps.

    Args:
        source: The telemetry source to drive.
        hub: The fan-out hub that dashboard clients subscribe to.
        hz: Capture rate.
        max_frames: Optional cap (mainly for tests); ``None`` runs until the
            source is exhausted or the task is cancelled.
        segmenter: Optional lap segmenter; when provided, completed laps trigger
            ``on_lap``.
        on_lap: Optional async callback invoked with each completed lap.

    Returns:
        The number of frames processed.
    """
    frames = 0
    source.connect()
    try:
        async for frame in source.stream(hz, max_frames=max_frames, on_error="skip"):
            frames += 1
            hub.publish(frame)
            if segmenter is not None:
                lap = segmenter.process(frame)
                if lap is not None and on_lap is not None:
                    await on_lap(lap)
    finally:
        source.close()
    return frames
