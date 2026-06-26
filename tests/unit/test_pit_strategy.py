"""Tests for pit strategy."""

from __future__ import annotations

from src.strategy.fuel_strategy import FuelReport, FuelStatus
from src.strategy.pit_strategy import PitAdvice, pit_recommendation
from src.strategy.tyre_strategy import TyreAdvice, TyreStrategyReport


def _fuel(status: FuelStatus, laps: float | None = None) -> FuelReport:
    return FuelReport(
        fuel_remaining=30.0,
        consumption_per_lap=2.5,
        laps_remaining=laps,
        status=status,
        margin_laps=None,
        message=f"fuel {status.value}",
    )


def _tyres(advice: TyreAdvice, laps: float | None = None) -> TyreStrategyReport:
    return TyreStrategyReport(
        avg_wear_pct=80.0,
        wear_rate_per_lap=2.0,
        laps_until_critical=laps,
        advice=advice,
        message=f"tyres {advice.value}",
    )


def test_critical_fuel_triggers_box_now() -> None:
    result = pit_recommendation(
        current_lap=10,
        fuel=_fuel(FuelStatus.CRITICAL, 1.0),
        tyres=_tyres(TyreAdvice.STAY_OUT, 20.0),
    )
    assert result.advice is PitAdvice.BOX_NOW
    assert result.trigger == "fuel"


def test_critical_tyres_triggers_box_now() -> None:
    result = pit_recommendation(
        current_lap=10,
        fuel=_fuel(FuelStatus.OK, 20.0),
        tyres=_tyres(TyreAdvice.PIT_NOW, 2.0),
    )
    assert result.advice is PitAdvice.BOX_NOW
    assert result.trigger == "tyres"


def test_plan_stop_when_deadline_close() -> None:
    result = pit_recommendation(
        current_lap=10,
        fuel=_fuel(FuelStatus.OK, 4.0),
        tyres=_tyres(TyreAdvice.STAY_OUT, 20.0),
    )
    assert result.advice is PitAdvice.PLAN_STOP
    assert result.recommended_lap is not None


def test_no_stop_when_both_healthy() -> None:
    result = pit_recommendation(
        current_lap=5,
        fuel=_fuel(FuelStatus.OK, 15.0),
        tyres=_tyres(TyreAdvice.STAY_OUT, 20.0),
    )
    assert result.advice is PitAdvice.NO_STOP


def test_no_stop_without_data() -> None:
    result = pit_recommendation(
        current_lap=1,
        fuel=_fuel(FuelStatus.OK, None),
        tyres=_tyres(TyreAdvice.STAY_OUT, None),
    )
    assert result.advice is PitAdvice.NO_STOP
    assert "gathering" in result.message.lower() or "No stop" in result.message
