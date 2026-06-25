"""Fuel strategy: consumption tracking, range estimation and alerts.

Fed the fuel level at the end of each lap, the calculator estimates per-lap
consumption (moving average), how many laps of fuel remain, and whether that is
enough to reach the end of the race - the questions a race engineer answers on
the radio.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

_DEFAULT_WINDOW = 5


class FuelStatus(StrEnum):
    """Fuel-margin status relative to the race distance."""

    OK = "ok"
    LOW = "low"
    CRITICAL = "critical"


@dataclass(frozen=True)
class FuelReport:
    """A snapshot of the fuel situation."""

    fuel_remaining: float
    consumption_per_lap: float | None
    laps_remaining: float | None
    status: FuelStatus
    margin_laps: float | None
    message: str


class FuelStrategy:
    """Track fuel consumption and estimate range from per-lap readings."""

    def __init__(self, window: int = _DEFAULT_WINDOW) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        self._window = window
        self._consumptions: deque[float] = deque(maxlen=window)
        self._last_fuel: float | None = None
        self._fuel_remaining: float = 0.0

    def record_lap_fuel(self, fuel_remaining: float) -> None:
        """Record the fuel level (litres) at the end of a lap."""
        if fuel_remaining < 0:
            raise ValueError("fuel_remaining cannot be negative")
        if self._last_fuel is not None:
            burned = self._last_fuel - fuel_remaining
            if burned > 0:  # ignore refuelling (fuel went up)
                self._consumptions.append(burned)
        self._last_fuel = fuel_remaining
        self._fuel_remaining = fuel_remaining

    @property
    def consumption_per_lap(self) -> float | None:
        """Average fuel burned per lap over the window, or ``None`` if unknown."""
        if not self._consumptions:
            return None
        return sum(self._consumptions) / len(self._consumptions)

    def laps_remaining(self) -> float | None:
        """Estimated laps of fuel left, or ``None`` if consumption is unknown."""
        consumption = self.consumption_per_lap
        if consumption is None or consumption <= 0:
            return None
        return self._fuel_remaining / consumption

    def fuel_for_laps(self, laps: int) -> float | None:
        """Fuel (litres) needed to complete *laps*, or ``None`` if unknown."""
        consumption = self.consumption_per_lap
        if consumption is None:
            return None
        return consumption * laps

    def report(self, laps_left: int | None = None) -> FuelReport:
        """Build a fuel report, optionally against the race laps remaining."""
        consumption = self.consumption_per_lap
        laps_rem = self.laps_remaining()
        status, margin, message = self._assess(laps_rem, laps_left)
        return FuelReport(
            fuel_remaining=round(self._fuel_remaining, 2),
            consumption_per_lap=round(consumption, 3) if consumption is not None else None,
            laps_remaining=round(laps_rem, 1) if laps_rem is not None else None,
            status=status,
            margin_laps=round(margin, 1) if margin is not None else None,
            message=message,
        )

    def _assess(
        self, laps_rem: float | None, laps_left: int | None
    ) -> tuple[FuelStatus, float | None, str]:
        if laps_rem is None:
            return (FuelStatus.OK, None, "Gathering fuel data...")
        if laps_left is not None:
            margin = laps_rem - laps_left
            if margin < 0:
                return (
                    FuelStatus.CRITICAL,
                    margin,
                    f"Short on fuel: {abs(margin):.1f} laps to save to finish.",
                )
            if margin < 1.0:
                return (FuelStatus.LOW, margin, f"Marginal fuel: {margin:.1f} laps spare.")
            return (FuelStatus.OK, margin, f"Fuel OK: {margin:.1f} laps spare at the end.")
        # No race distance known: judge by absolute range.
        if laps_rem < 2.0:
            return (FuelStatus.CRITICAL, None, f"Low fuel: ~{laps_rem:.1f} laps left.")
        if laps_rem < 5.0:
            return (FuelStatus.LOW, None, f"Fuel getting low: ~{laps_rem:.1f} laps left.")
        return (FuelStatus.OK, None, f"~{laps_rem:.1f} laps of fuel remaining.")
