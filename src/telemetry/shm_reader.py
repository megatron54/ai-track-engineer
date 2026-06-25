"""Live Assetto Corsa telemetry via Windows shared memory.

:class:`SharedMemoryTelemetrySource` maps the three ``acpmf_*`` shared-memory
pages and converts them into :class:`~src.telemetry.models.TelemetryFrame`
objects. The shared-memory access is injected through a small *opener* callable
so the read path can be unit-tested on any platform with in-memory buffers; the
default opener is Windows-only.

Note: when Assetto Corsa is not running, Windows still provides a zero-filled
mapping. ``connect`` therefore succeeds, and callers should wait for
``frame.is_live`` before trusting the data.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from ctypes import Structure
from typing import Protocol, TypeVar

from src.telemetry.converters import frame_from_structs, static_from_struct
from src.telemetry.models import ACStaticInfo, TelemetryFrame
from src.telemetry.shm_structs import (
    GRAPHICS_MAP_NAME,
    GRAPHICS_SIZE,
    PHYSICS_MAP_NAME,
    PHYSICS_SIZE,
    STATIC_MAP_NAME,
    STATIC_SIZE,
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)
from src.telemetry.source import (
    SourceNotConnectedError,
    TelemetrySource,
    TelemetrySourceError,
)


class ReadableBuffer(Protocol):
    """Minimal interface required of a mapped shared-memory page."""

    def seek(self, pos: int) -> object: ...
    def read(self, size: int) -> bytes: ...
    def close(self) -> None: ...


# An opener maps a named region of ``size`` bytes to a readable buffer.
MapOpener = Callable[[str, int], ReadableBuffer]

_S = TypeVar("_S", bound=Structure)


class UnsupportedPlatformError(TelemetrySourceError):
    """Raised when live shared memory is used on a non-Windows platform."""


def open_windows_shared_memory(name: str, size: int) -> ReadableBuffer:
    """Open an existing Windows named shared-memory region for reading."""
    if sys.platform != "win32":
        raise UnsupportedPlatformError(
            "live shared-memory telemetry is only available on Windows"
        )
    import mmap  # pragma: no cover - exercised only on Windows with AC running

    return mmap.mmap(  # pragma: no cover
        -1, size, tagname=name, access=mmap.ACCESS_READ
    )


class SharedMemoryTelemetrySource(TelemetrySource):
    """Read live telemetry from Assetto Corsa's shared-memory pages."""

    def __init__(
        self,
        *,
        opener: MapOpener | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._opener = opener or open_windows_shared_memory
        self._clock = clock
        self._physics_map: ReadableBuffer | None = None
        self._graphics_map: ReadableBuffer | None = None
        self._static_map: ReadableBuffer | None = None
        self._static: ACStaticInfo | None = None

    def connect(self) -> ACStaticInfo:
        self._physics_map = self._opener(PHYSICS_MAP_NAME, PHYSICS_SIZE)
        self._graphics_map = self._opener(GRAPHICS_MAP_NAME, GRAPHICS_SIZE)
        self._static_map = self._opener(STATIC_MAP_NAME, STATIC_SIZE)
        self._static = static_from_struct(self._read_static())
        return self._static

    def read_frame(self) -> TelemetryFrame:
        if self._physics_map is None or self._graphics_map is None or self._static is None:
            raise SourceNotConnectedError("call connect() before read_frame()")
        physics = self._read_struct(self._physics_map, SPageFilePhysics, PHYSICS_SIZE)
        graphics = self._read_struct(self._graphics_map, SPageFileGraphic, GRAPHICS_SIZE)
        static = self._read_static()
        return frame_from_structs(physics, graphics, static, timestamp=self._clock())

    def close(self) -> None:
        for buffer in (self._physics_map, self._graphics_map, self._static_map):
            if buffer is not None:
                buffer.close()
        self._physics_map = None
        self._graphics_map = None
        self._static_map = None

    # -- Internal helpers --------------------------------------------------
    def _read_static(self) -> SPageFileStatic:
        assert self._static_map is not None
        return self._read_struct(self._static_map, SPageFileStatic, STATIC_SIZE)

    @staticmethod
    def _read_struct(buffer: ReadableBuffer, struct_type: type[_S], size: int) -> _S:
        buffer.seek(0)
        data = buffer.read(size)
        if len(data) < size:
            raise TelemetrySourceError(
                f"short read from shared memory: expected {size} bytes, got {len(data)}"
            )
        return struct_type.from_buffer_copy(data)
