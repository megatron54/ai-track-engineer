"""Tests for the telemetry source abstraction (stream + context manager)."""

from __future__ import annotations

import time

import pytest
from src.telemetry.models import ACStaticInfo, TelemetryFrame
from src.telemetry.source import TelemetrySource, TelemetrySourceError

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


class _FlakySource(_CountingSource):
    """Raises a telemetry error on a configured set of read indices."""

    def __init__(self, fail_on: set[int]) -> None:
        super().__init__()
        self._fail_on = fail_on

    def read_frame(self) -> TelemetryFrame:
        self.reads += 1
        if self.reads in self._fail_on:
            raise TelemetrySourceError(f"bad read #{self.reads}")
        return make_frame(timestamp=float(self.reads))


async def test_stream_raises_on_read_error_by_default() -> None:
    source = _FlakySource(fail_on={2})
    with pytest.raises(TelemetrySourceError, match="bad read #2"):
        async for _ in source.stream(1000, max_frames=5):
            pass


async def test_stream_skips_read_errors_when_configured() -> None:
    source = _FlakySource(fail_on={2, 4})
    frames = [
        frame
        async for frame in source.stream(1000, max_frames=3, on_error="skip")
    ]
    # 3 good frames despite 2 transient failures (reads 2 and 4 skipped).
    assert len(frames) == 3
    assert source.reads == 5


class _SlowSource(_CountingSource):
    """A source whose read takes longer than the stream period."""

    def read_frame(self) -> TelemetryFrame:
        time.sleep(0.005)
        return super().read_frame()


async def test_stream_stays_stable_when_reads_fall_behind() -> None:
    # period = 1ms but each read takes ~5ms -> scheduler must resync, not burst.
    source = _SlowSource()
    frames = [frame async for frame in source.stream(1000, max_frames=4)]
    assert len(frames) == 4
    assert source.reads == 4
