"""Tests for the race engineer advisor."""

from __future__ import annotations

import pytest
from src.ai.advisor import RaceEngineerAdvisor
from src.ai.models import Priority
from src.analysis.engine_monitor import AlertSeverity, EngineAlert
from src.analysis.models import CornerDelta
from src.analysis.tyre_model import ThermalStatus, TyreThermalReport
from src.knowledge.models import Corner, TrackInfo
from src.processing.models import Lap

_TRACK = TrackInfo(
    track_id="t",
    name="Test Track",
    corners=(Corner(index=1, name="T1", entry=0.0, exit=0.2),),
)
_LAP = Lap(lap_number=4, lap_time_ms=90_000)


class _FakeLLM:
    def __init__(self, reply: str = "", *, fail: bool = False) -> None:
        self._reply = reply
        self._fail = fail
        self.calls = 0

    async def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self._fail:
            raise RuntimeError("model unavailable")
        return self._reply


def _hot_tyres() -> TyreThermalReport:
    return TyreThermalReport(
        statuses=(
            ThermalStatus.HOT,
            ThermalStatus.HOT,
            ThermalStatus.OPTIMAL,
            ThermalStatus.OPTIMAL,
        ),
        core_temps=(110.0, 109.0, 95.0, 95.0),
        front_rear_delta=14.0,
    )


def test_heuristic_prioritises_critical_engine_alert() -> None:
    advisor = RaceEngineerAdvisor()
    alerts = [
        EngineAlert(kind="over_rev", severity=AlertSeverity.CRITICAL, message="Over-rev!", rpm=8200)
    ]
    recs = advisor.heuristic_advice(engine_alerts=alerts)
    assert recs[0].priority is Priority.CRITICAL
    assert "Over-rev" in recs[0].message


def test_heuristic_flags_overheating_and_corner_losses() -> None:
    advisor = RaceEngineerAdvisor()
    losses = [
        CornerDelta(corner_index=1, corner_name="T1", delta_s=0.5),
        CornerDelta(corner_index=2, corner_name="T2", delta_s=0.2),
    ]
    recs = advisor.heuristic_advice(corner_losses=losses, tyre_report=_hot_tyres())
    messages = [r.message for r in recs]
    assert any("overheating" in m.lower() for m in messages)
    assert any("T1" in m for m in messages)
    # First corner loss gets HIGH priority, the next NORMAL.
    corner_recs = [r for r in recs if r.corner is not None]
    assert corner_recs[0].priority is Priority.HIGH
    assert corner_recs[1].priority is Priority.NORMAL


async def test_advise_uses_llm_when_available() -> None:
    llm = _FakeLLM(reply="[T1] Brake 5m later -> +0.2s\nKeep tyres in window")
    advisor = RaceEngineerAdvisor(llm)
    recs = await advisor.advise(lap=_LAP, track=_TRACK)
    assert llm.calls == 1
    assert [r.message for r in recs] == [
        "[T1] Brake 5m later -> +0.2s",
        "Keep tyres in window",
    ]


async def test_advise_falls_back_to_heuristic_on_llm_error() -> None:
    llm = _FakeLLM(fail=True)
    advisor = RaceEngineerAdvisor(llm)
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.5)]
    recs = await advisor.advise(lap=_LAP, track=_TRACK, corner_losses=losses)
    assert llm.calls == 1
    assert any("T1" in r.message for r in recs)


async def test_advise_uses_heuristic_when_no_llm() -> None:
    advisor = RaceEngineerAdvisor()
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.5)]
    recs = await advisor.advise(lap=_LAP, track=_TRACK, corner_losses=losses)
    assert recs
    assert all(r.priority in Priority for r in recs)


async def test_llm_advice_requires_client() -> None:
    advisor = RaceEngineerAdvisor()
    with pytest.raises(RuntimeError, match="no LLM configured"):
        await advisor.llm_advice("context")


async def test_advise_falls_back_when_llm_returns_blank() -> None:
    llm = _FakeLLM(reply="   \n  ")
    advisor = RaceEngineerAdvisor(llm)
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.5)]
    recs = await advisor.advise(lap=_LAP, track=_TRACK, corner_losses=losses)
    # Blank LLM reply -> heuristic fallback still produces advice.
    assert any("T1" in r.message for r in recs)
