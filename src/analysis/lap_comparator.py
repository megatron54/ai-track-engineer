"""Compare two laps: delta curves and per-corner time gain/loss.

Given a reference and a current :class:`~src.processing.lap_trace.LapTrace`, the
comparator answers "where am I gaining or losing time?" — the central question
of lap analysis — by differencing interpolated time-vs-position curves.
"""

from __future__ import annotations

from src.analysis.models import CornerDelta
from src.knowledge.models import Corner, TrackInfo
from src.processing.lap_trace import LapTrace


class LapComparison:
    """Difference a current lap against a reference lap."""

    def __init__(self, reference: LapTrace, current: LapTrace) -> None:
        self._reference = reference
        self._current = current

    def time_delta_at(self, position: float) -> float:
        """Cumulative time delta at a position (current minus reference)."""
        return self._current.time_at(position) - self._reference.time_at(position)

    def delta_curve(self, samples: int = 100) -> list[tuple[float, float]]:
        """Sample the delta curve across the lap.

        Returns ``(position, delta_s)`` pairs over the overlapping position
        range of the two laps.
        """
        if samples < 2:
            raise ValueError("samples must be >= 2")
        start = max(self._reference.start_position, self._current.start_position)
        end = min(self._reference.end_position, self._current.end_position)
        step = (end - start) / (samples - 1)
        return [
            (start + step * i, self.time_delta_at(start + step * i))
            for i in range(samples)
        ]

    def final_delta(self) -> float:
        """Delta at the end of the overlapping range (overall lap-time gap)."""
        end = min(self._reference.end_position, self._current.end_position)
        return self.time_delta_at(end)

    def corner_delta(self, corner: Corner) -> CornerDelta:
        """Time gained/lost through a single corner."""
        delta = self._corner_time(self._current, corner) - self._corner_time(
            self._reference, corner
        )
        return CornerDelta(
            corner_index=corner.index, corner_name=corner.name, delta_s=delta
        )

    def corner_deltas(self, track: TrackInfo) -> list[CornerDelta]:
        """Per-corner deltas for every corner on the track, in track order."""
        return [self.corner_delta(corner) for corner in track.corners]

    def biggest_losses(self, track: TrackInfo, limit: int = 3) -> list[CornerDelta]:
        """Corners where the current lap lost the most time, worst first."""
        losses = [delta for delta in self.corner_deltas(track) if delta.lost_time]
        losses.sort(key=lambda delta: delta.delta_s, reverse=True)
        return losses[:limit]

    @staticmethod
    def _corner_time(trace: LapTrace, corner: Corner) -> float:
        """Time spent within a corner, handling start/finish wrap."""
        if corner.entry <= corner.exit:
            return trace.segment_time(corner.entry, corner.exit)
        # Corner wraps the line: sum the tail of the lap and the head.
        return trace.segment_time(corner.entry, 1.0) + trace.segment_time(0.0, corner.exit)
