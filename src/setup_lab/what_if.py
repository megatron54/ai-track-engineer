"""What-if simulator: predict the delta from a setup change.

Uses the :class:`~src.setup_lab.digital_twin.PointMassModel` to answer "what
happens if I add 1 click of rear wing?" — comparing the simulated lap time
before and after the change.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.setup_lab.digital_twin import LapSim, PointMassModel


@dataclass(frozen=True)
class WhatIfResult:
    """The predicted effect of a setup change."""

    delta_s: float  # positive = slower
    before: LapSim
    after: LapSim
    explanation: str


def what_if(
    baseline: PointMassModel,
    corners: list[tuple[int, float, float]],
    total_length_m: float,
    *,
    cl_delta: float = 0,
    cd_delta: float = 0,
    mass_delta: float = 0,
    mu_delta: float = 0,
    description: str = "setup change",
) -> WhatIfResult:
    """Simulate the effect of a parameter change on lap time.

    Args:
        baseline: The current car model.
        corners: Track corners as ``(index, radius_m, arc_length_m)``.
        total_length_m: Track length.
        cl_delta: Change in lift coefficient.
        cd_delta: Change in drag coefficient.
        mass_delta: Change in mass (kg).
        mu_delta: Change in tyre grip coefficient.
        description: Human-readable description of the change.
    """
    before = baseline.simulate_lap(corners, total_length_m)
    changed = baseline.with_changes(
        cl_delta=cl_delta, cd_delta=cd_delta, mass_delta=mass_delta, mu_delta=mu_delta
    )
    after = changed.simulate_lap(corners, total_length_m)
    delta = after.predicted_lap_time_s - before.predicted_lap_time_s
    direction = "slower" if delta > 0 else "faster"
    explanation = f"{description}: {abs(delta):.3f}s {direction} predicted."
    return WhatIfResult(
        delta_s=round(delta, 3), before=before, after=after, explanation=explanation
    )
