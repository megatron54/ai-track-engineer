"""Tests for the session orchestration pump (run_session)."""

from __future__ import annotations

from src.analysis.engine_monitor import EngineMonitor
from src.dashboard.hub import TelemetryHub
from src.dashboard.pump import _mode_event, _should_deliver, run_session
from src.dashboard.state import DashboardState
from src.knowledge.models import Corner, TrackInfo
from src.processing.message_queue import MessagePriority, PriorityMessage
from src.strategy.mode_manager import EngineerMode, profile_for
from src.telemetry.mock import MockTelemetrySource
from src.telemetry.shm_structs import ACSessionType

_TRACK = TrackInfo(
    track_id="ks_laguna_seca",
    name="Laguna Seca",
    corners=(Corner(index=1, name="Turn 1", entry=0.0, exit=0.15),),
)


def _drain(queue: object) -> list[dict]:
    messages: list[dict] = []
    q = queue
    while not q.empty():  # type: ignore[attr-defined]
        messages.append(q.get_nowait())  # type: ignore[attr-defined]
    return messages


async def test_run_session_publishes_session_and_telemetry() -> None:
    source = MockTelemetrySource()
    static = source.connect()
    hub = TelemetryHub(queue_size=1000)
    state = DashboardState()
    queue = hub.subscribe()

    frames = await run_session(source, hub, state, _TRACK, static, hz=2000, max_frames=10)

    assert frames == 10
    assert state.session is not None
    messages = _drain(queue)
    types = [m["type"] for m in messages]
    assert types[0] == "session"
    assert "telemetry" in types


async def test_run_session_throttles_telemetry() -> None:
    source = MockTelemetrySource()
    static = source.connect()
    hub = TelemetryHub(queue_size=1000)
    state = DashboardState()
    queue = hub.subscribe()

    await run_session(source, hub, state, _TRACK, static, hz=2000, max_frames=10, telemetry_every=5)

    telemetry = [m for m in _drain(queue) if m["type"] == "telemetry"]
    assert len(telemetry) == 2  # 10 frames / every 5


async def test_run_session_emits_lap_events() -> None:
    source = MockTelemetrySource(dt=0.05, lap_time_s=1.0)
    static = source.connect()
    hub = TelemetryHub(queue_size=5000)
    state = DashboardState()
    queue = hub.subscribe()

    await run_session(
        source, hub, state, _TRACK, static, hz=4000, max_frames=80,
        engine_monitor=EngineMonitor(static.max_rpm),
    )

    laps = [m for m in _drain(queue) if m["type"] == "lap"]
    assert len(laps) >= 2
    assert all(m["number"] > 0 for m in laps)


async def test_run_session_rejects_bad_throttle() -> None:
    source = MockTelemetrySource()
    static = source.connect()
    try:
        import pytest

        with pytest.raises(ValueError, match="telemetry_every"):
            await run_session(
                source, TelemetryHub(), DashboardState(), _TRACK, static, hz=60, telemetry_every=0
            )
    finally:
        source.close()


class _FakeLLM:
    async def complete(self, system: str, user: str) -> str:
        return "[Turn 1] Brake 5m later -> +0.2s"


async def test_run_session_publishes_ai_advice_events() -> None:
    from src.ai.advisor import RaceEngineerAdvisor

    source = MockTelemetrySource(dt=0.05, lap_time_s=1.0)
    static = source.connect()
    hub = TelemetryHub(queue_size=5000)
    state = DashboardState()
    queue = hub.subscribe()
    advisor = RaceEngineerAdvisor(_FakeLLM())

    await run_session(
        source, hub, state, _TRACK, static, hz=4000, max_frames=80, advisor=advisor
    )

    advice = [m for m in _drain(queue) if m["type"] == "advice"]
    assert len(advice) >= 2
    assert advice[0]["messages"] == ["[Turn 1] Brake 5m later -> +0.2s"]


async def test_run_session_persists_laps_to_store() -> None:
    from src.storage.sqlite_client import SqliteStore

    store = SqliteStore(":memory:")
    await store.connect()
    session = await store.create_session(track="ks_laguna_seca", car="c", started_at=0.0)
    source = MockTelemetrySource(dt=0.05, lap_time_s=1.0)
    static = source.connect()
    hub = TelemetryHub(queue_size=5000)
    state = DashboardState()

    await run_session(
        source, hub, state, _TRACK, static, hz=4000, max_frames=80,
        store=store, session_id=session.id,
    )

    laps = await store.laps_for_session(session.id)
    await store.close()
    assert len(laps) >= 2
    assert all(lap.lap_number > 0 for lap in laps)


def _coaching_message(priority: MessagePriority) -> PriorityMessage:
    return PriorityMessage(priority=priority, timestamp=0.0, text="brake later", corner=None)


def test_mode_event_maps_session_type() -> None:
    event = _mode_event(ACSessionType.QUALIFY)
    assert event["type"] == "mode"
    assert event["mode"] == "qualifying"
    assert event["max_messages_per_lap"] == 2
    assert _mode_event(ACSessionType.RACE)["mode"] == "race"
    assert _mode_event(ACSessionType.PRACTICE)["mode"] == "practice"


def test_should_deliver_caps_messages_per_lap() -> None:
    practice = profile_for(EngineerMode.PRACTICE)
    assert _should_deliver(practice, _coaching_message(MessagePriority.NORMAL), 0) is True
    assert (
        _should_deliver(
            practice, _coaching_message(MessagePriority.NORMAL), practice.max_messages_per_lap
        )
        is False
    )


def test_should_deliver_silences_low_priority_in_qualifying() -> None:
    quali = profile_for(EngineerMode.QUALIFYING)
    assert quali.silence_during_hotlap is True
    assert _should_deliver(quali, _coaching_message(MessagePriority.NORMAL), 0) is False
    assert _should_deliver(quali, _coaching_message(MessagePriority.HIGH), 0) is True


async def test_run_session_publishes_mode_event() -> None:
    source = MockTelemetrySource()
    static = source.connect()
    hub = TelemetryHub(queue_size=1000)
    state = DashboardState()
    queue = hub.subscribe()

    await run_session(source, hub, state, _TRACK, static, hz=2000, max_frames=10)

    modes = [m for m in _drain(queue) if m["type"] == "mode"]
    assert modes
    assert modes[0]["mode"] in {"practice", "qualifying", "race"}


async def test_run_session_publishes_gap_events() -> None:
    import struct

    from src.telemetry.opponents import OpponentReceiver

    header = struct.Struct("<ii")
    car = struct.Struct("<ifif")
    packet = (
        header.pack(0, 3)
        + car.pack(0, 0.50, 1, 180.0)  # me
        + car.pack(1, 0.55, 1, 190.0)  # ahead
        + car.pack(2, 0.45, 1, 170.0)  # behind
    )
    recv = OpponentReceiver()
    recv._make_protocol().datagram_received(packet, ("127.0.0.1", 1))  # noqa: SLF001

    source = MockTelemetrySource()
    static = source.connect().model_copy(update={"track_spline_length": 5000.0})
    hub = TelemetryHub(queue_size=1000)
    state = DashboardState()
    queue = hub.subscribe()

    await run_session(
        source, hub, state, _TRACK, static, hz=2000, max_frames=5,
        opponents=recv, gap_every=1,
    )

    gaps = [m for m in _drain(queue) if m["type"] == "gap"]
    assert gaps
    assert gaps[-1]["ahead_s"] is not None
    assert gaps[-1]["behind_s"] is not None
    assert gaps[-1]["trend_ahead"] in {"closing", "stable", "opening"}


async def test_run_session_without_opponents_emits_no_gap() -> None:
    source = MockTelemetrySource()
    static = source.connect()
    hub = TelemetryHub(queue_size=1000)
    state = DashboardState()
    queue = hub.subscribe()

    await run_session(source, hub, state, _TRACK, static, hz=2000, max_frames=10)

    assert not [m for m in _drain(queue) if m["type"] == "gap"]


async def test_run_session_rejects_bad_gap_every() -> None:
    import pytest

    source = MockTelemetrySource()
    static = source.connect()
    try:
        with pytest.raises(ValueError, match="gap_every"):
            await run_session(
                source, TelemetryHub(), DashboardState(), _TRACK, static, hz=60, gap_every=0
            )
    finally:
        source.close()


async def test_run_session_detects_mid_session_change() -> None:
    import pytest
    from src.telemetry.source import SessionChangedError

    source = MockTelemetrySource()
    static = source.connect()
    changed = static.model_copy(update={"car_model": "dallara_f317", "track": "imola"})
    reads = {"n": 0}

    def fake_read_static() -> object:
        reads["n"] += 1
        return changed if reads["n"] >= 2 else static

    source.read_static = fake_read_static  # type: ignore[method-assign]

    hub = TelemetryHub(queue_size=1000)
    state = DashboardState()
    with pytest.raises(SessionChangedError) as exc:
        await run_session(
            source, hub, state, _TRACK, static, hz=4000, max_frames=200,
            static_check_every=1,
        )
    assert exc.value.new_static.car_model == "dallara_f317"
    # the source is left open so the caller can rebuild the session without a reconnect
    assert source.read_frame() is not None
    source.close()
