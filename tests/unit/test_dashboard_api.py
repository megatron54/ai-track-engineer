"""Tests for the dashboard FastAPI app (health, track, WebSocket)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi.testclient import TestClient
from src import __version__
from src.dashboard.api import create_app
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


def test_health_endpoint() -> None:
    with TestClient(create_app(TelemetryHub(), DashboardState())) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_track_endpoint_503_without_session() -> None:
    with TestClient(create_app(TelemetryHub(), DashboardState())) as client:
        assert client.get("/api/track").status_code == 503


def test_track_endpoint_returns_session_when_set() -> None:
    state = DashboardState()
    state.set_session({"type": "session", "track": "Spa"})
    with TestClient(create_app(TelemetryHub(), state)) as client:
        response = client.get("/api/track")
    assert response.status_code == 200
    assert response.json()["track"] == "Spa"


def test_map_endpoint_404_without_map() -> None:
    with TestClient(create_app(TelemetryHub(), DashboardState())) as client:
        assert client.get("/api/track/map.png").status_code == 404


def test_index_serves_html() -> None:
    with TestClient(create_app(TelemetryHub(), DashboardState())) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "AI-TrackEngineer" in response.text


def _producer(hub: TelemetryHub, state: DashboardState) -> Callable[[], Coroutine[Any, Any, None]]:
    async def producer() -> None:
        source = MockTelemetrySource()
        static = source.connect()
        await run_session(source, hub, state, _TRACK, static, hz=200)

    return producer


def test_websocket_streams_session_then_telemetry() -> None:
    hub = TelemetryHub(queue_size=200)
    state = DashboardState()
    app = create_app(hub, state, producer=_producer(hub, state))
    with TestClient(app) as client, client.websocket_connect("/ws/telemetry") as ws:
        # Collect a few messages and assert we see telemetry with live fields.
        seen_types = set()
        telemetry = None
        for _ in range(10):
            msg = ws.receive_json()
            seen_types.add(msg["type"])
            if msg["type"] == "telemetry":
                telemetry = msg
                break
    assert telemetry is not None
    assert "speed_kmh" in telemetry
    assert "coords" in telemetry


def test_websocket_unsubscribes_on_disconnect() -> None:
    hub = TelemetryHub(queue_size=200)
    state = DashboardState()
    app = create_app(hub, state, producer=_producer(hub, state))
    with TestClient(app) as client, client.websocket_connect("/ws/telemetry") as ws:
        ws.receive_json()
    assert hub.subscriber_count == 0
