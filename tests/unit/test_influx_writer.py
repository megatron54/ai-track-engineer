"""Tests for telemetry point conversion and batched writing."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from src.storage.influx_client import (
    TELEMETRY_MEASUREMENT,
    BatchingTelemetryWriter,
    TelemetryPoint,
    frame_to_point,
)

from tests.factories import make_frame


class _FakeBackend:
    """Records written batches; never touches the network."""

    def __init__(self) -> None:
        self.batches: list[list[TelemetryPoint]] = []
        self.closed = False

    async def write(self, points: Sequence[TelemetryPoint]) -> None:
        self.batches.append(list(points))

    async def aclose(self) -> None:
        self.closed = True


def test_frame_to_point_maps_tags_and_fields() -> None:
    frame = make_frame(timestamp=12.5, speed_kmh=210.0, rpm=7200, gear=4)
    point = frame_to_point(frame, session_id="abc")

    assert point.measurement == TELEMETRY_MEASUREMENT
    assert point.tags["session"] == "abc"
    assert point.tags["track"] == "ks_laguna_seca"
    assert point.fields["speed_kmh"] == 210.0
    assert point.fields["rpm"] == 7200.0
    assert point.fields["gear"] == 4.0
    assert point.timestamp_s == 12.5
    assert "tyre_temp_fl" in point.fields


def test_batch_constructor_rejects_bad_size() -> None:
    with pytest.raises(ValueError, match="batch_size must be positive"):
        BatchingTelemetryWriter(_FakeBackend(), session_id="s", batch_size=0)


async def test_writer_flushes_when_batch_fills() -> None:
    backend = _FakeBackend()
    writer = BatchingTelemetryWriter(backend, session_id="s", batch_size=3)
    for _ in range(7):
        await writer.add(make_frame())
    # 7 points -> two full batches of 3 flushed, 1 still buffered.
    assert len(backend.batches) == 2
    assert all(len(batch) == 3 for batch in backend.batches)
    assert writer.buffered == 1


async def test_flush_is_noop_when_empty() -> None:
    backend = _FakeBackend()
    writer = BatchingTelemetryWriter(backend, session_id="s", batch_size=10)
    await writer.flush()
    assert backend.batches == []


async def test_aclose_flushes_remaining_and_closes_backend() -> None:
    backend = _FakeBackend()
    writer = BatchingTelemetryWriter(backend, session_id="s", batch_size=100)
    await writer.add(make_frame())
    await writer.add(make_frame())
    await writer.aclose()
    assert len(backend.batches) == 1
    assert len(backend.batches[0]) == 2
    assert backend.closed is True


async def test_context_manager_flushes_on_exit() -> None:
    backend = _FakeBackend()
    async with BatchingTelemetryWriter(backend, session_id="s", batch_size=100) as writer:
        await writer.add(make_frame())
    assert backend.closed is True
    assert len(backend.batches) == 1
