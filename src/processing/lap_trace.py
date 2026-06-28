"""Lap traces: position-indexed telemetry for lap comparison.

A :class:`LapTrace` captures how a single lap evolved as a function of track
position, so two laps can be compared apples-to-apples regardless of where the
driver was at a given wall-clock time. Interpolation by normalised position is
the foundation for delta curves and per-corner analysis.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from src.telemetry.models import TelemetryFrame


class LapTrace:
    """Position-indexed samples for one lap (time and speed vs track position)."""

    def __init__(self, lap_number: int, samples: Sequence[tuple[float, float, float]]) -> None:
        """Build a trace from ``(position, time_s, speed_kmh)`` samples.

        Samples are sorted by position and de-duplicated so the position axis is
        strictly increasing (required for interpolation). Time is rebased so the
        lap starts at ``0``.
        """
        if len(samples) < 2:
            raise ValueError("a lap trace needs at least 2 samples")

        ordered = sorted(samples, key=lambda s: s[0])
        positions: list[float] = []
        times: list[float] = []
        speeds: list[float] = []
        base_time = ordered[0][1]
        last_position = None
        for position, time_s, speed in ordered:
            if last_position is not None and position <= last_position:
                continue  # drop non-increasing positions
            positions.append(position)
            times.append(time_s - base_time)
            speeds.append(speed)
            last_position = position

        if len(positions) < 2:
            raise ValueError("lap trace has too few distinct positions")

        self.lap_number = lap_number
        self._positions = np.asarray(positions, dtype=float)
        self._times = np.asarray(times, dtype=float)
        self._speeds = np.asarray(speeds, dtype=float)

    @classmethod
    def from_frames(cls, lap_number: int, frames: Iterable[TelemetryFrame]) -> LapTrace:
        """Build a trace from the telemetry frames captured during a lap."""
        samples = [
            (
                frame.graphics.normalized_car_position,
                frame.timestamp,
                frame.physics.speed_kmh,
            )
            for frame in frames
        ]
        return cls(lap_number, samples)

    @property
    def duration(self) -> float:
        """Elapsed time across the trace (last sample time)."""
        return float(self._times[-1])

    @property
    def is_clean(self) -> bool:
        """Whether elapsed time rises monotonically along the lap.

        A clean single lap has time increasing with track position. A trace
        stitched across a mid-lap restart or teleport (e.g. AC hotlap "restart")
        has time jump backwards, which corrupts position-based interpolation.
        Such a trace must not be used as a delta reference.
        """
        if self._times.size < 2:
            return False
        return bool(np.all(np.diff(self._times) >= 0.0))

    @property
    def start_position(self) -> float:
        return float(self._positions[0])

    @property
    def end_position(self) -> float:
        return float(self._positions[-1])

    def time_at(self, position: float) -> float:
        """Interpolated elapsed time at a normalised track position."""
        return float(np.interp(position, self._positions, self._times))

    def speed_at(self, position: float) -> float:
        """Interpolated speed (km/h) at a normalised track position."""
        return float(np.interp(position, self._positions, self._speeds))

    def segment_time(self, start: float, end: float) -> float:
        """Time spent between two positions (``start`` <= ``end``)."""
        return self.time_at(end) - self.time_at(start)
