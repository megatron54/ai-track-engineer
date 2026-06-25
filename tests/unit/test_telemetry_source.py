"""Tests for the telemetry source abstraction (stream + context manager)."""

from __future__ import annotations

import pytest
from src.telemetry.models import ACStaticInfo, TelemetryFrame
from src.telemetry.source import TelemetrySource

from tests.factories import make_frame, make_static


class _CountingSource(TelemetrySource):
    """Minimal source that counts reads, for exercising the base class."""

    def __init__(self) -> None:
        self.connected = False
        self.closed = False
        self.reads = 0
        self._static = make_static()

    def connect(self) -> ACStaticInfo:
        self.connected = True
        return self._static

    def read_frame(self) -> TelemetryFrame:
        self.reads += 1
        return make_frame(timestamp=float(self.reads))

    def close(self) -> None:
        self.closed = True


async def test_stream_yields_requested_number_of_frames() -> None:
    source = _CountingSource()
    frames = [frame async for frame in source.stream(1000, max_frames=5)]
    assert len(frames) == 5
    assert source.reads == 5


async def test_stream_rejects_non_positive_hz() -> None:
    source = _CountingSource()
    with pytest.raises(ValueError, match="hz must be positive"):
        async for _ in source.stream(0, max_frames=1):
            pass


async def test_stream_can_be_unbounded_then_stopped() -> None:
    source = _CountingSource()
    collected = 0
    async for _frame in source.stream(1000):
        collected += 1
        if collected >= 3:
            break
    assert collected == 3


def test_context_manager_connects_and_closes() -> None:
    source = _CountingSource()
    with source as opened:
        assert opened.connected is True
        assert source.closed is False
    assert source.closed is True
