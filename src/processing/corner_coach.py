"""Real-time corner coaching: post-corner feedback and brake-zone prediction.

Runs alongside the pipeline, comparing the car's speed and position at each
corner against the best lap's trace to generate short, actionable messages:
- **Post-corner**: immediately after exiting a corner, how much time was
  gained/lost and whether the entry was early/late.
- **Brake prediction**: as the car approaches a braking zone, whether it is
  ahead or behind the reference speed at that distance.
"""

from __future__ import annotations

from src.knowledge.models import Corner, TrackInfo
from src.processing.lap_trace import LapTrace
from src.processing.message_queue import MessagePriority, PriorityMessage


class CornerCoach:
    """Emit per-corner feedback from the live telemetry stream."""

    def __init__(self, track: TrackInfo, *, delta_threshold: float = 0.05) -> None:
        self._track = track
        self._threshold = delta_threshold
        self._last_corner: Corner | None = None
        self._reference: LapTrace | None = None

    def set_reference(self, trace: LapTrace) -> None:
        """Update the reference (personal best) trace."""
        self._reference = trace

    def process(
        self,
        position: float,
        speed_kmh: float,
        elapsed_s: float,
        timestamp: float,
    ) -> list[PriorityMessage]:
        """Feed the car's current state and return any generated messages."""
        messages: list[PriorityMessage] = []
        current_corner = self._track.corner_at(position)

        # Post-corner: we just left a corner (were in one, now we're not or in a new one).
        if (
            self._last_corner is not None
            and current_corner is not self._last_corner
            and self._reference is not None
        ):
            messages.extend(self._post_corner(self._last_corner, elapsed_s, timestamp))

        # Brake prediction: approaching the next corner.
        if current_corner is None and self._reference is not None:
            msg = self._brake_check(position, speed_kmh, timestamp)
            if msg is not None:
                messages.append(msg)

        self._last_corner = current_corner
        return messages

    def _post_corner(
        self, corner: Corner, elapsed_s: float, timestamp: float
    ) -> list[PriorityMessage]:
        assert self._reference is not None
        ref_time = self._reference.segment_time(corner.entry, corner.exit)
        try:
            actual_time = elapsed_s - self._reference.time_at(corner.entry)
        except (ValueError, IndexError):
            return []
        delta = actual_time - ref_time
        if abs(delta) < self._threshold:
            return []
        direction = "lost" if delta > 0 else "gained"
        return [
            PriorityMessage(
                priority=MessagePriority.NORMAL,
                timestamp=timestamp,
                text=f"[{corner.name}] {direction} {abs(delta):.2f}s vs best",
                corner=corner.name,
            )
        ]

    def _brake_check(
        self, position: float, speed_kmh: float, timestamp: float
    ) -> PriorityMessage | None:
        assert self._reference is not None
        next_corner = self._next_corner(position)
        if next_corner is None:
            return None
        # Only warn when close to the corner entry (within 5% of the track).
        dist = next_corner.entry - position
        if dist < 0:
            dist += 1.0
        if dist > 0.05:
            return None
        ref_speed = self._reference.speed_at(position)
        diff = speed_kmh - ref_speed
        if abs(diff) < 3.0:
            return None
        if diff > 0:
            return PriorityMessage(
                priority=MessagePriority.HIGH,
                timestamp=timestamp,
                text=(
                    f"Approaching {next_corner.name}: "
                    f"+{diff:.0f} km/h vs best — brake earlier"
                ),
                corner=next_corner.name,
            )
        return None

    def _next_corner(self, position: float) -> Corner | None:
        """Find the next corner ahead of the current position."""
        best: Corner | None = None
        best_dist = 2.0
        for corner in self._track.corners:
            dist = corner.entry - position
            if dist < 0:
                dist += 1.0
            if 0 < dist < best_dist:
                best = corner
                best_dist = dist
        return best
