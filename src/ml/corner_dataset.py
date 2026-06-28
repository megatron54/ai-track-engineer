"""Build corner-level training samples from recorded telemetry.

For each trainable lap and each track corner, extract the entry conditions the
driver controls - entry speed, brake point, gear and peak lateral g - and the
time taken through the corner, which is the target the corner-time predictor
learns. Pure standard library plus the :class:`~src.knowledge.models.Corner`
domain model; the heavier ML stack lives only in the training script.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.knowledge.models import Corner
from src.ml.recorded_session import TelemetrySample

# A driver is "on the brakes" once brake input exceeds this fraction.
_BRAKE_THRESHOLD = 0.1
# How far (in normalised track position) before a corner to look for the brake
# point. ~0.08 of a lap is a generous braking zone for any circuit.
_BRAKE_LOOKBACK = 0.08
# A corner needs at least this many samples to yield a usable timing.
_MIN_CORNER_SAMPLES = 2


@dataclass(frozen=True, slots=True)
class CornerSample:
    """One (lap, corner) training row: entry conditions -> time through corner."""

    lap: int
    corner_index: int
    entry_speed_kmh: float
    brake_point_pos: float
    entry_gear: int
    entry_g_lat: float
    corner_time_s: float


def _corner_sample(
    lap: int, ordered: list[TelemetrySample], corner: Corner
) -> CornerSample | None:
    """Extract a single corner sample, or ``None`` if the corner has no data."""
    inside = [s for s in ordered if corner.contains(s.lap_pos)]
    if len(inside) < _MIN_CORNER_SAMPLES:
        return None
    entry, exit_ = inside[0], inside[-1]
    corner_time = exit_.timestamp - entry.timestamp
    if corner_time <= 0:
        return None

    # Brake point: earliest position in the approach window where the driver is
    # on the brakes. Falls back to the corner entry if no braking is detected.
    brake_point = entry.lap_pos
    low = corner.entry - _BRAKE_LOOKBACK
    approach = [
        s.lap_pos
        for s in ordered
        if low <= s.lap_pos <= corner.entry and s.brake > _BRAKE_THRESHOLD
    ]
    if approach:
        brake_point = min(approach)

    peak_g_lat = max(abs(s.g_lat) for s in inside)
    return CornerSample(
        lap=lap,
        corner_index=corner.index,
        entry_speed_kmh=entry.speed_kmh,
        brake_point_pos=brake_point,
        entry_gear=entry.gear,
        entry_g_lat=peak_g_lat,
        corner_time_s=corner_time,
    )


def build_corner_samples(
    samples_by_lap: dict[int, list[TelemetrySample]],
    corners: Sequence[Corner],
    trainable_laps: Sequence[int],
) -> list[CornerSample]:
    """Build corner training rows for the given laps and corners.

    Args:
        samples_by_lap: Samples grouped by lap.
        corners: The track's corners (with normalised entry/exit positions).
        trainable_laps: Laps selected by :func:`src.ml.lap_quality.assess_laps`.

    Returns:
        One :class:`CornerSample` per (lap, corner) that has enough data.
    """
    rows: list[CornerSample] = []
    for lap in trainable_laps:
        samples = samples_by_lap.get(lap)
        if not samples:
            continue
        ordered = sorted(samples, key=lambda s: s.lap_pos)
        for corner in corners:
            sample = _corner_sample(lap, ordered, corner)
            if sample is not None:
                rows.append(sample)
    return rows
