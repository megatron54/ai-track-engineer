"""Tests for the shared-memory telemetry reader using in-memory buffers."""

from __future__ import annotations

import io
import sys

import pytest
from src.telemetry.shm_reader import (
    SharedMemoryTelemetrySource,
    UnsupportedPlatformError,
    open_windows_shared_memory,
)
from src.telemetry.shm_structs import (
    GRAPHICS_MAP_NAME,
    PHYSICS_MAP_NAME,
    STATIC_MAP_NAME,
    ACStatus,
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)
from src.telemetry.source import SourceNotConnectedError, TelemetrySourceError


class _TrackingBuffer(io.BytesIO):
    """A BytesIO that records whether it was closed."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.was_closed = False

    def close(self) -> None:
        self.was_closed = True
        super().close()


class _FakeMaps:
    """An opener backed by in-memory copies of the three pages."""

    def __init__(
        self,
        physics: SPageFilePhysics,
        graphics: SPageFileGraphic,
        static: SPageFileStatic,
    ) -> None:
        self._by_name = {
            PHYSICS_MAP_NAME: _TrackingBuffer(bytes(physics)),
            GRAPHICS_MAP_NAME: _TrackingBuffer(bytes(graphics)),
            STATIC_MAP_NAME: _TrackingBuffer(bytes(static)),
        }

    def opener(self, name: str, size: int) -> io.BytesIO:
        return self._by_name[name]


def test_connect_reads_static_and_read_frame_maps_values() -> None:
    physics = SPageFilePhysics()
    physics.rpms = 6500
    physics.speedKmh = 150.0
    physics.gear = 3
    graphics = SPageFileGraphic()
    graphics.status = ACStatus.LIVE
    graphics.normalizedCarPosition = 0.33
    static = SPageFileStatic()
    static.track = "ks_monza"
    static.maxRpm = 9000

    fake = _FakeMaps(physics, graphics, static)
    source = SharedMemoryTelemetrySource(opener=fake.opener, clock=lambda: 1.0)

    static_info = source.connect()
    assert static_info.track == "ks_monza"
    assert static_info.max_rpm == 9000

    frame = source.read_frame()
    assert frame.timestamp == 1.0
    assert frame.physics.rpm == 6500
    assert frame.physics.gear_label == "2"
    assert frame.graphics.normalized_car_position == pytest.approx(0.33, abs=1e-4)
    assert frame.is_live is True


def test_read_before_connect_raises() -> None:
    source = SharedMemoryTelemetrySource(opener=lambda name, size: io.BytesIO(b"\x00" * size))
    with pytest.raises(SourceNotConnectedError):
        source.read_frame()


def test_short_read_raises_telemetry_error() -> None:
    def short_opener(name: str, size: int) -> io.BytesIO:
        return io.BytesIO(b"\x00" * (size - 1))

    source = SharedMemoryTelemetrySource(opener=short_opener)
    with pytest.raises(TelemetrySourceError, match="short read"):
        source.connect()


def test_close_is_idempotent() -> None:
    fake = _FakeMaps(SPageFilePhysics(), SPageFileGraphic(), SPageFileStatic())
    source = SharedMemoryTelemetrySource(opener=fake.opener)
    source.connect()
    source.close()
    source.close()  # must not raise


def test_default_opener_rejects_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(UnsupportedPlatformError):
        open_windows_shared_memory(PHYSICS_MAP_NAME, 16)


def test_partial_connect_failure_closes_opened_maps() -> None:
    """If a later page fails to open, earlier maps must be closed, not leaked."""
    physics_buffer = _TrackingBuffer(bytes(SPageFilePhysics()))
    calls = {"n": 0}

    def flaky_opener(name: str, size: int) -> io.BytesIO:
        calls["n"] += 1
        if calls["n"] == 1:
            return physics_buffer
        raise OSError("mapping unavailable")

    source = SharedMemoryTelemetrySource(opener=flaky_opener)
    with pytest.raises(OSError, match="mapping unavailable"):
        source.connect()
    assert physics_buffer.was_closed is True

