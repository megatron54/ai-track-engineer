"""Engine power-curve analysis from ``power.lut``.

``power.lut`` lists engine torque (Nm) against RPM. From it we derive the power
curve (power = torque x angular velocity), the peak-torque and peak-power
points, and the usable power band - the inputs a setup tool needs for gearing
and shift-point advice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.knowledge.car_physics.lut import Lut

# Convert RPM to angular velocity (rad/s): rpm * 2*pi / 60.
_RPM_TO_RAD_S = 2.0 * math.pi / 60.0


@dataclass(frozen=True)
class PowerPoint:
    """A single point on the engine curve."""

    rpm: float
    torque_nm: float
    power_w: float

    @property
    def power_hp(self) -> float:
        """Power in metric horsepower."""
        return self.power_w / 735.49875


class PowerCurve:
    """Engine torque and power as a function of RPM."""

    def __init__(self, torque_lut: Lut) -> None:
        self._lut = torque_lut

    @classmethod
    def from_text(cls, text: str) -> PowerCurve:
        """Build a power curve from ``power.lut`` content."""
        return cls(Lut.from_text(text))

    @property
    def max_rpm(self) -> float:
        return self._lut.x_max

    def torque_at(self, rpm: float) -> float:
        """Engine torque (Nm) at *rpm*."""
        return self._lut.value_at(rpm)

    def power_at(self, rpm: float) -> float:
        """Engine power (W) at *rpm*."""
        return self.torque_at(rpm) * rpm * _RPM_TO_RAD_S

    def _point(self, rpm: float) -> PowerPoint:
        return PowerPoint(rpm=rpm, torque_nm=self.torque_at(rpm), power_w=self.power_at(rpm))

    @property
    def peak_torque(self) -> PowerPoint:
        """The point of maximum torque."""
        best = max(self._lut.points, key=lambda p: p[1])
        return self._point(best[0])

    @property
    def peak_power(self) -> PowerPoint:
        """The point of maximum power (sampled across the curve)."""
        best_rpm = max(
            (p[0] for p in self._lut.points),
            key=self.power_at,
        )
        return self._point(best_rpm)

    def power_band(self, fraction: float = 0.9) -> tuple[float, float]:
        """RPM range where power is at least *fraction* of peak power.

        Returns ``(low_rpm, high_rpm)``. Useful for choosing shift points that
        keep the engine in its strongest range.
        """
        if not 0.0 < fraction <= 1.0:
            raise ValueError("fraction must be in (0, 1]")
        threshold = self.peak_power.power_w * fraction
        in_band = [p[0] for p in self._lut.points if self.power_at(p[0]) >= threshold]
        if not in_band:
            peak = self.peak_power.rpm
            return (peak, peak)
        return (min(in_band), max(in_band))
