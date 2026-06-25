"""Parser for Assetto Corsa ``.lut`` lookup tables.

A LUT is a plain-text list of ``key|value`` pairs (one per line) used throughout
the car physics files (power curves, tyre grip vs temperature, etc.). This
parser reads them and interpolates between points.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


class Lut:
    """An interpolatable lookup table of ``(x, y)`` points."""

    def __init__(self, points: Sequence[tuple[float, float]]) -> None:
        if not points:
            raise ValueError("a LUT needs at least one point")
        ordered = sorted(points, key=lambda p: p[0])
        self._xs = np.asarray([p[0] for p in ordered], dtype=float)
        self._ys = np.asarray([p[1] for p in ordered], dtype=float)

    @classmethod
    def from_text(cls, text: str) -> Lut:
        """Parse ``key|value`` lines into a :class:`Lut` (ignores comments)."""
        points: list[tuple[float, float]] = []
        for raw in text.splitlines():
            line = raw.split(";", 1)[0].split("//", 1)[0].strip()
            if not line or "|" not in line:
                continue
            key, _, value = line.partition("|")
            try:
                points.append((float(key.strip()), float(value.strip())))
            except ValueError:
                continue
        return cls(points)

    @property
    def points(self) -> list[tuple[float, float]]:
        """The table's points as ``(x, y)`` tuples, ordered by x."""
        return list(zip(self._xs.tolist(), self._ys.tolist(), strict=True))

    @property
    def x_min(self) -> float:
        return float(self._xs[0])

    @property
    def x_max(self) -> float:
        return float(self._xs[-1])

    def value_at(self, x: float) -> float:
        """Interpolated value at *x* (clamped to the table's range)."""
        return float(np.interp(x, self._xs, self._ys))
