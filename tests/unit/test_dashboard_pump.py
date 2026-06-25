"""Tests for the session orchestration pump (run_session)."""

from __future__ import annotations

from src.analysis.engine_monitor import EngineMonitor
from src.dashboard.hub import TelemetryHub
from src.dashboard.pump import run_session
from src.dashboard.state import DashboardState
from src.knowledge.models import Corner, TrackInfo
from src.telemetry.mock import MockTelemetrySource

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
