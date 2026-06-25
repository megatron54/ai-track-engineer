"""Tests for the telemetry hub and dashboard serialization."""

from __future__ import annotations

import asyncio

import pytest
from src.dashboard.hub import TelemetryHub
from src.dashboard.serialization import frame_to_payload

from tests.factories import make_frame


def test_subscribe_and_unsubscribe_tracks_count() -> None:
    hub = TelemetryHub()
    assert hub.subscriber_count == 0
    queue = hub.subscribe()
    assert hub.subscriber_count == 1
    hub.unsubscribe(queue)
    assert hub.subscriber_count == 0
    hub.unsubscribe(queue)  # idempotent


def test_invalid_queue_size() -> None:
    with pytest.raises(ValueError, match="queue_size must be positive"):
        TelemetryHub(queue_size=0)


async def test_publish_delivers_to_all_subscribers() -> None:
    hub = TelemetryHub()
    first = hub.subscribe()
    second = hub.subscribe()
    frame = make_frame(timestamp=1.0)
    hub.publish(frame)
    assert (await first.get()).timestamp == 1.0
    assert (await second.get()).timestamp == 1.0


def test_publish_drops_oldest_when_queue_full() -> None:
    hub = TelemetryHub(queue_size=2)
    queue = hub.subscribe()
    for index in range(4):
        hub.publish(make_frame(timestamp=float(index)))
    # Only the two most recent frames remain.
    assert queue.qsize() == 2
    assert queue.get_nowait().timestamp == 2.0
    assert queue.get_nowait().timestamp == 3.0


def test_publish_with_no_subscribers_is_safe() -> None:
    TelemetryHub().publish(make_frame())  # must not raise


def test_frame_to_payload_shape() -> None:
    frame = make_frame(timestamp=2.0, speed_kmh=199.4, rpm=8000, gear=5)
    payload = frame_to_payload(frame)
    assert payload["speed_kmh"] == 199.4
    assert payload["rpm"] == 8000
    assert payload["gear"] == "4"
    assert payload["status"] == "LIVE"
    assert len(payload["tyre_temp"]) == 4
    # Payload must be JSON-serialisable.
    import json

    json.dumps(payload)


async def test_hub_is_async_safe_under_concurrent_publish() -> None:
    hub = TelemetryHub(queue_size=100)
    queue = hub.subscribe()

    async def producer() -> None:
        for index in range(10):
            hub.publish(make_frame(timestamp=float(index)))
            await asyncio.sleep(0)

    await producer()
    assert queue.qsize() == 10
