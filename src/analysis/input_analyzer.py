"""Per-corner analysis of raw driver inputs: brake, throttle, steering.

``lap_comparator.py`` answers *how much* time was gained or lost through a
corner (a pure time delta). This module answers *why*: where the driver
braked relative to their reference lap, when they got back on the throttle,
how much braking and steering overlapped (trail braking), and how many times
they reversed the steering direction (a smoothness/correction proxy).

All functions are pure and operate on :class:`~src.processing.lap_trace.LapTrace`,
so they are fully testable with synthetic traces - no live driving required.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.knowledge.models import Corner
from src.processing.lap_trace import LapTrace

# A corner is "braked" once the pedal crosses this fraction.
_BRAKE_THRESHOLD = 0.10
# Throttle is considered "reapplied" once it crosses this fraction.
_THROTTLE_THRESHOLD = 0.10
# How far before a corner's entry to search for the brake point, as a
# fraction of the lap. 0.15 comfortably covers a late braking zone without
# picking up braking from the previous corner on a short circuit.
_LOOKBACK = 0.15


@dataclass(frozen=True)
class CornerInputProfile:
    """A single lap's driver-input signature through one corner."""

    corner_index: int
    corner_name: str
    brake_point: float | None
    throttle_point: float | None
    trail_braking_overlap: float
    steering_reversals: int


@dataclass(frozen=True)
class CornerInputDelta:
    """Difference between a lap's input profile and a reference lap's, per corner.

    Position deltas are *current minus reference* in normalised track
    position: positive ``brake_point_delta`` means the current lap braked
    later (lost ground); negative means earlier.
    """

    corner_index: int
    corner_name: str
    brake_point_delta: float | None
    throttle_point_delta: float | None
    trail_braking_overlap_delta: float
    steering_reversals_delta: int

    def brake_point_delta_m(self, track_length_m: float) -> float | None:
        """Brake-point delta converted to metres along the track."""
        if self.brake_point_delta is None or track_length_m <= 0:
            return None
        return self.brake_point_delta * track_length_m

    def throttle_point_delta_m(self, track_length_m: float) -> float | None:
        """Throttle-reapplication delta converted to metres along the track."""
        if self.throttle_point_delta is None or track_length_m <= 0:
            return None
        return self.throttle_point_delta * track_length_m


def _brake_window(corner: Corner, lookback: float) -> tuple[float, float]:
    """The search window before a corner's entry, wrapping past the line if needed."""
    start = corner.entry - lookback
    if start < 0:
        start += 1.0
    return start, corner.entry


def corner_input_profile(
    trace: LapTrace,
    corner: Corner,
    *,
    brake_threshold: float = _BRAKE_THRESHOLD,
    throttle_threshold: float = _THROTTLE_THRESHOLD,
    lookback: float = _LOOKBACK,
) -> CornerInputProfile:
    """Build the input profile for one corner from a single lap trace."""
    brake_start, brake_end = _brake_window(corner, lookback)
    return CornerInputProfile(
        corner_index=corner.index,
        corner_name=corner.name,
        brake_point=trace.first_crossing("brake", brake_threshold, brake_start, brake_end),
        throttle_point=trace.first_crossing(
            "gas", throttle_threshold, corner.entry, corner.exit
        ),
        trail_braking_overlap=trace.trail_braking_overlap(brake_start, corner.exit),
        steering_reversals=trace.steering_reversals(corner.entry, corner.exit),
    )


def _position_delta(current: float | None, reference: float | None) -> float | None:
    """Shortest signed distance ``current - reference`` in ``[0, 1)`` position space."""
    if current is None or reference is None:
        return None
    delta = current - reference
    if delta > 0.5:
        delta -= 1.0
    elif delta < -0.5:
        delta += 1.0
    return delta


def compare_corner_inputs(
    current: LapTrace,
    reference: LapTrace,
    corner: Corner,
    **profile_kwargs: float,
) -> CornerInputDelta:
    """Compare a lap's input profile through ``corner`` against a reference lap."""
    cur = corner_input_profile(current, corner, **profile_kwargs)
    ref = corner_input_profile(reference, corner, **profile_kwargs)
    return CornerInputDelta(
        corner_index=corner.index,
        corner_name=corner.name,
        brake_point_delta=_position_delta(cur.brake_point, ref.brake_point),
        throttle_point_delta=_position_delta(cur.throttle_point, ref.throttle_point),
        trail_braking_overlap_delta=cur.trail_braking_overlap - ref.trail_braking_overlap,
        steering_reversals_delta=cur.steering_reversals - ref.steering_reversals,
    )
