"""Lap traces: position-indexed telemetry for lap comparison.

A :class:`LapTrace` captures how a single lap evolved as a function of track
position, so two laps can be compared apples-to-apples regardless of where the
driver was at a given wall-clock time. Interpolation by normalised position is
the foundation for delta curves, per-corner time analysis, and (via
``brake_at``/``throttle_at``/``steer_at``/``first_crossing``) per-corner
*input* analysis: where the driver braked, when they got back on the
throttle, and how the two overlap.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal

import numpy as np

from src.telemetry.models import TelemetryFrame

# A sample is (position, time_s, speed_kmh) with optional (brake, gas, steer_angle)
# trailing values, defaulting to 0.0 when omitted (kept backwards-compatible with
# existing 3-tuple samples built before input analysis existed).
LapSample = tuple[float, ...]

InputFeature = Literal["brake", "gas"]


class LapTrace:
    """Position-indexed samples for one lap (time, speed and inputs vs. position)."""

    def __init__(self, lap_number: int, samples: Sequence[LapSample]) -> None:
        """Build a trace from samples.

        Each sample is ``(position, time_s, speed_kmh)`` with optional
        trailing ``brake``, ``gas`` and ``steer_angle`` values (defaulting to
        ``0.0`` when a sample provides fewer than 6 elements). Samples are
        sorted by position and de-duplicated so the position axis is strictly
        increasing (required for interpolation). Time is rebased so the lap
        starts at ``0``.
        """
        if len(samples) < 2:
            raise ValueError("a lap trace needs at least 2 samples")

        ordered = sorted(samples, key=lambda s: s[0])
        positions: list[float] = []
        times: list[float] = []
        speeds: list[float] = []
        brakes: list[float] = []
        gases: list[float] = []
        steers: list[float] = []
        base_time = ordered[0][1]
        last_position = None
        for sample in ordered:
            position, time_s, speed = sample[0], sample[1], sample[2]
            if last_position is not None and position <= last_position:
                continue  # drop non-increasing positions
            positions.append(position)
            times.append(time_s - base_time)
            speeds.append(speed)
            brakes.append(sample[3] if len(sample) > 3 else 0.0)
            gases.append(sample[4] if len(sample) > 4 else 0.0)
            steers.append(sample[5] if len(sample) > 5 else 0.0)
            last_position = position

        if len(positions) < 2:
            raise ValueError("lap trace has too few distinct positions")

        self.lap_number = lap_number
        self._positions = np.asarray(positions, dtype=float)
        self._times = np.asarray(times, dtype=float)
        self._speeds = np.asarray(speeds, dtype=float)
        self._brake = np.asarray(brakes, dtype=float)
        self._gas = np.asarray(gases, dtype=float)
        self._steer = np.asarray(steers, dtype=float)

    @classmethod
    def from_frames(cls, lap_number: int, frames: Iterable[TelemetryFrame]) -> LapTrace:
        """Build a trace from the telemetry frames captured during a lap."""
        samples = [
            (
                frame.graphics.normalized_car_position,
                frame.timestamp,
                frame.physics.speed_kmh,
                frame.physics.brake,
                frame.physics.gas,
                frame.physics.steer_angle,
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

    def brake_at(self, position: float) -> float:
        """Interpolated brake input (0..1) at a normalised track position."""
        return float(np.interp(position, self._positions, self._brake))

    def throttle_at(self, position: float) -> float:
        """Interpolated throttle input (0..1) at a normalised track position."""
        return float(np.interp(position, self._positions, self._gas))

    def steer_at(self, position: float) -> float:
        """Interpolated steering angle at a normalised track position."""
        return float(np.interp(position, self._positions, self._steer))

    def segment_time(self, start: float, end: float) -> float:
        """Time spent between two positions (``start`` <= ``end``)."""
        return self.time_at(end) - self.time_at(start)

    def _segment(
        self, start: float, end: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(positions, brake, gas, steer)`` restricted to ``[start, end]``.

        Handles the case where the window wraps the start/finish line
        (``start > end``): the head segment's positions are shifted by
        ``+1.0`` so the combined array stays strictly increasing for
        threshold-crossing detection.
        """
        if start <= end:
            mask = (self._positions >= start) & (self._positions <= end)
            return (
                self._positions[mask],
                self._brake[mask],
                self._gas[mask],
                self._steer[mask],
            )
        tail = self._positions >= start
        head = self._positions <= end
        positions = np.concatenate([self._positions[tail], self._positions[head] + 1.0])
        brake = np.concatenate([self._brake[tail], self._brake[head]])
        gas = np.concatenate([self._gas[tail], self._gas[head]])
        steer = np.concatenate([self._steer[tail], self._steer[head]])
        return positions, brake, gas, steer

    def first_crossing(
        self, feature: InputFeature, threshold: float, start: float, end: float
    ) -> float | None:
        """Normalised position of the first *rising* crossing of ``threshold``.

        Searches ``feature`` ("brake" or "gas") within ``[start, end]``
        (wrap-aware). Returns ``None`` if the feature never reaches
        ``threshold`` in that window (e.g. a corner taken flat-out, or no
        throttle reapplication before the trace ends).
        """
        positions, brake, gas, _ = self._segment(start, end)
        values = brake if feature == "brake" else gas
        if positions.size < 2:
            return None
        above = values >= threshold
        if not above.any():
            return None
        first_idx = int(np.argmax(above))
        if first_idx == 0:
            return float(positions[0] % 1.0)
        p0, p1 = positions[first_idx - 1], positions[first_idx]
        v0, v1 = values[first_idx - 1], values[first_idx]
        frac = 0.0 if v1 == v0 else (threshold - v0) / (v1 - v0)
        return float((p0 + frac * (p1 - p0)) % 1.0)

    def trail_braking_overlap(
        self,
        start: float,
        end: float,
        *,
        brake_threshold: float = 0.05,
        steer_threshold: float = 0.05,
    ) -> float:
        """Fraction (0..1) of ``[start, end]`` where brake and steering overlap.

        A high value means the driver was still on the brakes while turning
        the wheel (trail braking); ``0.0`` means braking and steering never
        happened at the same time in this window.
        """
        positions, brake, _, steer = self._segment(start, end)
        if positions.size < 2:
            return 0.0
        both = (brake >= brake_threshold) & (np.abs(steer) >= steer_threshold)
        return float(np.count_nonzero(both) / both.size)

    def steering_reversals(
        self, start: float, end: float, *, deadband: float = 0.02
    ) -> int:
        """Count of steering-direction reversals within ``[start, end]``.

        A rough proxy for correction/smoothness: a clean, committed corner has
        zero or one reversal (turn-in, maybe one correction); several
        reversals indicate the driver was fighting the car (over-correcting,
        catching a slide, or hesitant steering).
        """
        _, _, _, steer = self._segment(start, end)
        if steer.size < 3:
            return 0
        signs = np.sign(np.where(np.abs(steer) < deadband, 0.0, steer))
        nonzero = signs[signs != 0]
        if nonzero.size < 2:
            return 0
        return int(np.count_nonzero(np.diff(nonzero) != 0))
