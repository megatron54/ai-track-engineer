"""Tyre thermal analysis.

Classifies each tyre as cold / optimal / hot against a configurable temperature
window and surfaces simple balance signals (front vs rear). Assetto Corsa's
shared memory exposes core and inner/middle/outer temperatures directly, so this
works from live telemetry without parsing car physics files.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from src.telemetry.models import ACPhysics, Wheels

_DEFAULT_OPTIMAL_MIN = 80.0
_DEFAULT_OPTIMAL_MAX = 100.0


class ThermalStatus(StrEnum):
    """Where a tyre sits relative to its optimal temperature window."""

    COLD = "cold"
    OPTIMAL = "optimal"
    HOT = "hot"


class TyreThermalReport(BaseModel):
    """Per-wheel thermal classification plus simple balance signals."""

    model_config = ConfigDict(frozen=True)

    statuses: tuple[ThermalStatus, ThermalStatus, ThermalStatus, ThermalStatus]
    core_temps: tuple[float, float, float, float]
    front_rear_delta: float

    @property
    def overheating(self) -> bool:
        """Whether any tyre is above its optimal window."""
        return any(status is ThermalStatus.HOT for status in self.statuses)

    @property
    def too_cold(self) -> bool:
        """Whether any tyre is below its optimal window."""
        return any(status is ThermalStatus.COLD for status in self.statuses)

    @property
    def all_optimal(self) -> bool:
        """Whether every tyre is within its optimal window."""
        return all(status is ThermalStatus.OPTIMAL for status in self.statuses)


class TyreThermalModel:
    """Classify tyre temperatures against an optimal window."""

    def __init__(
        self,
        optimal_min: float = _DEFAULT_OPTIMAL_MIN,
        optimal_max: float = _DEFAULT_OPTIMAL_MAX,
    ) -> None:
        if optimal_min >= optimal_max:
            raise ValueError("optimal_min must be below optimal_max")
        self._min = optimal_min
        self._max = optimal_max

    def classify(self, temperature: float) -> ThermalStatus:
        """Classify a single temperature value."""
        if temperature < self._min:
            return ThermalStatus.COLD
        if temperature > self._max:
            return ThermalStatus.HOT
        return ThermalStatus.OPTIMAL

    def evaluate(self, physics: ACPhysics) -> TyreThermalReport:
        """Build a thermal report from a physics frame."""
        temps: Wheels = physics.tyre_core_temp
        values = temps.as_tuple()
        statuses = (
            self.classify(values[0]),
            self.classify(values[1]),
            self.classify(values[2]),
            self.classify(values[3]),
        )
        return TyreThermalReport(
            statuses=statuses,
            core_temps=values,
            front_rear_delta=temps.front_axle_avg - temps.rear_axle_avg,
        )
