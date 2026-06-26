"""Simplified digital twin: point-mass model for setup-change predictions.

This is NOT a full physics sim; it captures the **first-order effects** a race
engineer cares about when advising a driver on setup changes:

- More downforce -> more grip in corners (higher max cornering speed) but more
  drag on straights (lower top speed).
- Stiffer springs/ARB -> less weight transfer but less mechanical grip at that
  axle.
- More brake bias forward -> shorter braking distance but higher lock-up risk.

The model is calibrated from the car's physics files + a correction factor
derived from the driver's real telemetry, making predictions realistic for
*this driver at this level* rather than theoretical optimums.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CornerSim:
    """Simulated result for a single corner."""

    corner_index: int
    max_speed_ms: float
    time_s: float


@dataclass(frozen=True)
class LapSim:
    """Simulated lap time from the point-mass model."""

    predicted_lap_time_s: float
    corners: tuple[CornerSim, ...]
    top_speed_kmh: float


class PointMassModel:
    """A simplified point-mass lap-time estimator.

    Given a track's corner radii and straight lengths (derived from the spline
    length and corner positions), plus a car's power, mass, and aerodynamic
    properties, estimates lap time and the delta from setup changes.
    """

    def __init__(
        self,
        *,
        mass_kg: float,
        power_w: float,
        cl: float = 1.5,
        cd: float = 0.8,
        frontal_area: float = 1.8,
        tyre_mu: float = 1.3,
        air_density: float = 1.225,
    ) -> None:
        self._mass = mass_kg
        self._power = power_w
        self._cl = cl
        self._cd = cd
        self._area = frontal_area
        self._mu = tyre_mu
        self._rho = air_density

    def max_corner_speed(self, radius_m: float, speed_guess_ms: float = 50.0) -> float:
        """Iteratively solve for the maximum cornering speed (m/s).

        Grip comes from mechanical (mu * weight) + aerodynamic downforce.
        """
        g = 9.81
        for _ in range(20):
            v = speed_guess_ms
            downforce = 0.5 * self._rho * self._area * self._cl * v * v
            grip_force = self._mu * (self._mass * g + downforce)
            centripetal_needed = self._mass * v * v / radius_m
            if centripetal_needed <= grip_force:
                speed_guess_ms = v * 1.01
            else:
                speed_guess_ms = math.sqrt(grip_force * radius_m / self._mass)
                break
        return speed_guess_ms

    def top_speed_ms(self) -> float:
        """Estimate top speed where power equals drag force * velocity."""
        # P = F_drag * v -> P = 0.5 * rho * A * Cd * v^3
        if self._cd <= 0 or self._area <= 0:
            return 100.0
        v_cubed = self._power / (0.5 * self._rho * self._area * self._cd)
        return float(v_cubed ** (1.0 / 3.0))

    def simulate_corner(self, corner_index: int, radius_m: float, arc_length_m: float) -> CornerSim:
        """Simulate time through a corner of known radius and arc length."""
        v_max = self.max_corner_speed(radius_m)
        time = arc_length_m / v_max if v_max > 0 else 999.0
        return CornerSim(corner_index=corner_index, max_speed_ms=v_max, time_s=time)

    def simulate_lap(
        self,
        corners: list[tuple[int, float, float]],
        total_length_m: float,
    ) -> LapSim:
        """Simulate a full lap.

        Args:
            corners: list of ``(corner_index, radius_m, arc_length_m)``
            total_length_m: Total track length.

        Returns:
            A :class:`LapSim` with predicted lap time and per-corner detail.
        """
        corner_sims: list[CornerSim] = []
        corner_time = 0.0
        corner_distance = 0.0
        for idx, radius, arc in corners:
            sim = self.simulate_corner(idx, radius, arc)
            corner_sims.append(sim)
            corner_time += sim.time_s
            corner_distance += arc

        straight_distance = max(0.0, total_length_m - corner_distance)
        v_top = self.top_speed_ms()
        # Rough: average straight speed is 85% of top speed.
        avg_straight_speed = v_top * 0.85
        straight_time = straight_distance / avg_straight_speed if avg_straight_speed > 0 else 0.0

        return LapSim(
            predicted_lap_time_s=round(corner_time + straight_time, 3),
            corners=tuple(corner_sims),
            top_speed_kmh=round(v_top * 3.6, 1),
        )

    def with_changes(
        self,
        *,
        cl_delta: float = 0,
        cd_delta: float = 0,
        mass_delta: float = 0,
        mu_delta: float = 0,
    ) -> PointMassModel:
        """Return a new model with aerodynamic/mass/grip deltas applied."""
        return PointMassModel(
            mass_kg=self._mass + mass_delta,
            power_w=self._power,
            cl=self._cl + cl_delta,
            cd=self._cd + cd_delta,
            frontal_area=self._area,
            tyre_mu=self._mu + mu_delta,
            air_density=self._rho,
        )
