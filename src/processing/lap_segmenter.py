"""Lap segmentation from a telemetry stream.

:class:`LapSegmenter` is a small state machine that consumes telemetry frames
one at a time and emits a :class:`~src.processing.models.Lap` whenever the car
crosses the finish line. Lap completion is driven by Assetto Corsa's
``completed_laps`` counter (the authoritative signal), with per-sector splits
captured from ``current_sector_index`` transitions.

The segmenter is deliberately pure and synchronous so it is trivial to test;
:meth:`LapSegmenter.segment` adapts it to an async frame stream.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from src.processing.models import Lap
from src.telemetry.models import ACGraphics, TelemetryFrame


class LapSegmenter:
    """Detect completed laps from a sequence of telemetry frames."""

    def __init__(self) -> None:
        self._prev_completed_laps: int | None = None
        self._prev_sector_index: int | None = None
        self._sector_times_ms: list[int] = []
        self._lap_started_at: float = 0.0
        self._lap_valid: bool = True

    def process(self, frame: TelemetryFrame) -> Lap | None:
        """Feed one frame; return a :class:`Lap` if one just completed.

        Args:
            frame: The next telemetry frame.

        Returns:
            The completed lap, or ``None`` if the car has not crossed the line
            on this frame.
        """
        graphics = frame.graphics

        # First frame seen: initialise state, emit nothing.
        if self._prev_completed_laps is None:
            self._begin_lap(frame)
            self._prev_completed_laps = graphics.completed_laps
            return None

        if graphics.is_in_pit or graphics.is_in_pit_lane:
            self._lap_valid = False

        self._track_sector(graphics)

        if graphics.completed_laps > self._prev_completed_laps:
            lap = self._finish_lap(frame)
            self._prev_completed_laps = graphics.completed_laps
            self._begin_lap(frame)
            return lap
        return None

    async def segment(
        self, frames: AsyncIterator[TelemetryFrame]
    ) -> AsyncIterator[Lap]:
        """Yield completed laps from an async stream of frames."""
        async for frame in frames:
            lap = self.process(frame)
            if lap is not None:
                yield lap

    # -- Internal state transitions ----------------------------------------
    def _begin_lap(self, frame: TelemetryFrame) -> None:
        self._lap_started_at = frame.timestamp
        self._sector_times_ms = []
        self._prev_sector_index = frame.graphics.current_sector_index
        self._lap_valid = not (
            frame.graphics.is_in_pit or frame.graphics.is_in_pit_lane
        )

    def _track_sector(self, graphics: ACGraphics) -> None:
        # ``_prev_sector_index`` is always set by ``_begin_lap`` before any
        # frame reaches this method, so it is never None here.
        if graphics.current_sector_index != self._prev_sector_index:
            # A sector boundary was crossed; the finished sector's time is in
            # last_sector_time_ms. Ignore zero/unknown splits.
            if graphics.last_sector_time_ms > 0:
                self._sector_times_ms.append(graphics.last_sector_time_ms)
            self._prev_sector_index = graphics.current_sector_index

    def _finish_lap(self, frame: TelemetryFrame) -> Lap:
        graphics = frame.graphics
        return Lap(
            lap_number=graphics.completed_laps,
            lap_time_ms=graphics.last_time_ms,
            sector_times_ms=tuple(self._sector_times_ms),
            valid=self._lap_valid,
            started_at=self._lap_started_at,
            ended_at=frame.timestamp,
        )
