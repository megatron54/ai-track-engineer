"""Tests for the dashboard FastAPI app (health, index, WebSocket)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi.testclient import TestClient
from src import __version__
from src.dashboard.api import create_app
from src.dashboard.hub import TelemetryHub
from src.dashboard.pump import capture_to_hub
from src.telemetry.mock import MockTelemetrySource


def test_health_endpoint() -> None:
    app = create_app(TelemetryHub())
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_index_serves_html() -> None:
    app = create_app(TelemetryHub())
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "AI-TrackEngineer" in response.text
    assert "text/html" in response.headers["content-type"]


def _mock_producer(hub: TelemetryHub) -> Callable[[], Coroutine[Any, Any, None]]:
    async def producer() -> None:
        # Unbounded stream (cancelled on app shutdown) so a connecting client
        # always has frames waiting, regardless of timing.
        await capture_to_hub(MockTelemetrySource(), hub, hz=200)

    return producer


def test_websocket_streams_telemetry() -> None:
    hub = TelemetryHub(queue_size=50)
    app = create_app(hub, producer=_mock_producer(hub))
    with TestClient(app) as client, client.websocket_connect("/ws/telemetry") as websocket:
        payload = websocket.receive_json()
    assert "speed_kmh" in payload
    assert "rpm" in payload
    assert payload["status"] == "LIVE"


def test_websocket_unsubscribes_on_disconnect() -> None:
    hub = TelemetryHub(queue_size=50)
    app = create_app(hub, producer=_mock_producer(hub))
    with TestClient(app) as client, client.websocket_connect("/ws/telemetry") as websocket:
        websocket.receive_json()
        # After the client disconnects the handler must drop its subscription.
        # (Allow the server task to process the disconnect.)
    assert hub.subscriber_count == 0
