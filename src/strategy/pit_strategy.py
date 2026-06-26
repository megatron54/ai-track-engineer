"""Pit-stop strategy: predict the optimal pit window.

Combines fuel and tyre state to recommend when to pit. The decision is simple
and transparent: pit when the first resource (fuel or tyre life) will run out,
offset by the pit-stop time loss so the driver pits early enough.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.strategy.fuel_strategy import FuelReport, FuelStatus
from src.strategy.tyre_strategy import TyreAdvice, TyreStrategyReport


class PitAdvice(StrEnum):
    NO_STOP = "no_stop"
    PLAN_STOP = "plan_stop"
    BOX_NOW = "box_now"


@dataclass(frozen=True)
class PitReport:
    advice: PitAdvice
    trigger: str
    recommended_lap: int | None
    message: str


def pit_recommendation(
    *,
    current_lap: int,
    fuel: FuelReport,
    tyres: TyreStrategyReport,
) -> PitReport:
    """Combine fuel and tyre reports into a pit recommendation."""
    # Immediate box signals.
    if fuel.status is FuelStatus.CRITICAL:
        return PitReport(
            advice=PitAdvice.BOX_NOW,
            trigger="fuel",
            recommended_lap=current_lap,
            message=f"Box now — {fuel.message}",
        )
    if tyres.advice is TyreAdvice.PIT_NOW:
        return PitReport(
            advice=PitAdvice.BOX_NOW,
            trigger="tyres",
            recommended_lap=current_lap,
            message=f"Box now — {tyres.message}",
        )

    # Plan ahead: whichever resource runs out first.
    fuel_deadline: float | None = fuel.laps_remaining
    tyre_deadline: float | None = tyres.laps_until_critical

    deadlines: list[tuple[str, float]] = []
    if fuel_deadline is not None:
        deadlines.append(("fuel", fuel_deadline))
    if tyre_deadline is not None:
        deadlines.append(("tyres", tyre_deadline))

    if not deadlines:
        return PitReport(
            advice=PitAdvice.NO_STOP,
            trigger="none",
            recommended_lap=None,
            message="No stop needed (gathering data).",
        )

    trigger_name, laps = min(deadlines, key=lambda d: d[1])
    rec_lap = current_lap + max(0, int(laps) - 1)

    if laps <= 5:
        return PitReport(
            advice=PitAdvice.PLAN_STOP,
            trigger=trigger_name,
            recommended_lap=rec_lap,
            message=f"Plan stop lap {rec_lap} ({trigger_name}: ~{laps:.0f} laps left).",
        )
    return PitReport(
        advice=PitAdvice.NO_STOP,
        trigger=trigger_name,
        recommended_lap=rec_lap,
        message=f"Next stop around lap {rec_lap} ({trigger_name}). Stay out.",
    )
