"""Tests for the race engineer advisor."""

from __future__ import annotations

import pytest
from src.ai.advisor import RaceEngineerAdvisor
from src.ai.models import Priority
from src.analysis.engine_monitor import AlertSeverity, EngineAlert
from src.analysis.input_analyzer import CornerInputDelta
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


def test_heuristic_advice_includes_input_point_detail() -> None:
    advisor = RaceEngineerAdvisor()
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.3)]
    input_deltas = [
        CornerInputDelta(
            corner_index=1,
            corner_name="T1",
            brake_point_delta=0.02,  # 2% of a 1000m track = 20m later
            throttle_point_delta=None,
            trail_braking_overlap_delta=0.0,
            steering_reversals_delta=0,
        )
    ]
    recs = advisor.heuristic_advice(
        corner_losses=losses, input_deltas=input_deltas, track_length_m=1000.0
    )
    assert any("braked 20m later" in r.message for r in recs)


def test_heuristic_advice_notes_improving_trend() -> None:
    advisor = RaceEngineerAdvisor()
    message = advisor.heuristic_advice(
        corner_losses=[CornerDelta(corner_index=1, corner_name="T1", delta_s=0.10)],
        corner_trends={"T1": "improving, was +0.30s"},
    )[0].message
    assert "improving" in message
    assert "0.30s" in message


async def test_advise_remembers_corner_trend_across_laps_heuristic() -> None:
    advisor = RaceEngineerAdvisor()
    first = await advisor.advise(
        lap=_LAP,
        track=_TRACK,
        corner_losses=[CornerDelta(corner_index=1, corner_name="T1", delta_s=0.40)],
    )
    assert not any("improving" in r.message or "regressing" in r.message for r in first)

    second = await advisor.advise(
        lap=_LAP,
        track=_TRACK,
        corner_losses=[CornerDelta(corner_index=1, corner_name="T1", delta_s=0.10)],
    )
    assert any("improving" in r.message for r in second)


async def test_advise_remembers_regressing_corner_trend() -> None:
    advisor = RaceEngineerAdvisor()
    await advisor.advise(
        lap=_LAP,
        track=_TRACK,
        corner_losses=[CornerDelta(corner_index=1, corner_name="T1", delta_s=0.10)],
    )
    second = await advisor.advise(
        lap=_LAP,
        track=_TRACK,
        corner_losses=[CornerDelta(corner_index=1, corner_name="T1", delta_s=0.40)],
    )
    assert any("regressing" in r.message for r in second)
    assert any("0.10s" in r.message for r in second)


async def test_advise_passes_corner_trend_into_llm_context() -> None:
    llm = _FakeLLM(reply="[T1] noted")
    advisor = RaceEngineerAdvisor(llm)

    captured: dict[str, str] = {}

    async def _capturing_complete(system: str, user: str) -> str:
        captured["user"] = user
        return "[T1] noted"

    llm.complete = _capturing_complete  # type: ignore[method-assign]

    await advisor.advise(
        lap=_LAP,
        track=_TRACK,
        corner_losses=[CornerDelta(corner_index=1, corner_name="T1", delta_s=0.40)],
    )
    await advisor.advise(
        lap=_LAP,
        track=_TRACK,
        corner_losses=[CornerDelta(corner_index=1, corner_name="T1", delta_s=0.10)],
    )
    assert "improving" in captured["user"]


async def test_answer_question_uses_llm_when_available() -> None:
    llm = _FakeLLM(reply="Tyres are in the window, keep pushing.")
    advisor = RaceEngineerAdvisor(llm)
    reply = await advisor.answer_question("how are my tyres?", track=_TRACK)
    assert reply == "Tyres are in the window, keep pushing."
    assert llm.calls == 1


async def test_answer_question_falls_back_to_heuristic_on_llm_error() -> None:
    llm = _FakeLLM(fail=True)
    advisor = RaceEngineerAdvisor(llm)
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.5)]
    reply = await advisor.answer_question("what's slow?", track=_TRACK, corner_losses=losses)
    assert "T1" in reply


async def test_answer_question_without_llm_uses_heuristic() -> None:
    advisor = RaceEngineerAdvisor()
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.5)]
    reply = await advisor.answer_question("what's slow?", track=_TRACK, corner_losses=losses)
    assert "T1" in reply


async def test_answer_question_with_no_data_says_so() -> None:
    advisor = RaceEngineerAdvisor()
    reply = await advisor.answer_question("how am I doing?", track=_TRACK)
    assert "not enough data" in reply.lower()


async def test_answer_question_does_not_affect_advise_trend_memory() -> None:
    # Asking a question mid-session must not pollute the per-lap trend memory
    # that advise() maintains.
    advisor = RaceEngineerAdvisor()
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.40)]
    await advisor.answer_question("what's slow?", track=_TRACK, corner_losses=losses)
    recs = await advisor.advise(lap=_LAP, track=_TRACK, corner_losses=losses)
    assert not any("improving" in r.message or "regressing" in r.message for r in recs)


async def test_answer_question_passes_question_and_data_into_llm_context() -> None:
    captured: dict[str, str] = {}

    class _CapturingLLM:
        async def complete(self, system: str, user: str) -> str:
            captured["system"] = system
            captured["user"] = user
            return "All good back there."

    advisor = RaceEngineerAdvisor(_CapturingLLM())
    losses = [CornerDelta(corner_index=1, corner_name="T1", delta_s=0.30)]
    reply = await advisor.answer_question(
        "how's turn one?", track=_TRACK, corner_losses=losses
    )
    assert reply == "All good back there."
    assert 'Driver asked: "how\'s turn one?"' in captured["user"]
    assert "T1: +0.300s" in captured["user"]
    assert captured["system"] != ""
