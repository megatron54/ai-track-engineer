"""Tests for the message hub and dashboard event serialization."""

from __future__ import annotations

import asyncio

import pytest
from src.dashboard.hub import TelemetryHub
from src.dashboard.serialization import session_event
from src.knowledge.models import Corner, MapProjection, TrackInfo


def _msg(value: int) -> dict[str, int]:
    return {"type": "telemetry", "n": value}


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
    hub.publish(_msg(1))
    assert (await first.get())["n"] == 1
    assert (await second.get())["n"] == 1


def test_publish_drops_oldest_when_queue_full() -> None:
    hub = TelemetryHub(queue_size=2)
    queue = hub.subscribe()
    for index in range(4):
        hub.publish(_msg(index))
    assert queue.qsize() == 2
    assert queue.get_nowait()["n"] == 2
    assert queue.get_nowait()["n"] == 3


def test_publish_with_no_subscribers_is_safe() -> None:
    TelemetryHub().publish(_msg(0))  # must not raise


async def test_hub_handles_concurrent_publish() -> None:
    hub = TelemetryHub(queue_size=100)
    queue = hub.subscribe()
    for index in range(10):
        hub.publish(_msg(index))
        await asyncio.sleep(0)
    assert queue.qsize() == 10


# --- serialization -----------------------------------------------------------

_TRACK = TrackInfo(
    track_id="spa",
    name="Spa",
    length_m=6946.0,
    corners=(Corner(index=1, name="La Source", entry=0.0, exit=0.05),),
    map=MapProjection(
        width=1004.83, height=1593.82, x_offset=664.529, z_offset=982.854,
        scale_factor=1.3, margin=20.0,
    ),
)


def test_session_event_includes_corners_and_map() -> None:
    event = session_event(_TRACK, car="ks_ferrari_f2004")
    assert event["type"] == "session"
    assert event["track"] == "Spa"
    assert event["car"] == "ks_ferrari_f2004"
    assert event["corners"][0]["name"] == "La Source"
    assert event["map"]["scale_factor"] == pytest.approx(1.3)


def test_session_event_without_map() -> None:
    track = TrackInfo(track_id="t", name="T")
    assert session_event(track, car="c")["map"] is None
