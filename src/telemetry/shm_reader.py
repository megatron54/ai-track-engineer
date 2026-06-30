"""Live Assetto Corsa telemetry via Windows shared memory.

:class:`SharedMemoryTelemetrySource` maps the three ``acpmf_*`` shared-memory
pages and converts them into :class:`~src.telemetry.models.TelemetryFrame`
objects. The shared-memory access is injected through a small *opener* callable
so the read path can be unit-tested on any platform with in-memory buffers; the
default opener is Windows-only.

Important: this reader only *opens* the shared-memory regions that Assetto
Corsa creates - it never creates them. If AC is not running (or not yet in a
session) the regions do not exist and :meth:`connect` raises
:class:`SharedMemoryUnavailableError`, which callers treat as "wait and retry".
This is deliberate: creating the regions from the reader (as ``mmap(-1, ...)``
does on Windows via ``CreateFileMapping``) registers a named section with the
reader's size/protection. When AC later starts it reuses that pre-existing
section and crashes inside ``SharedMemoryWriter::writeStatic`` while writing
into a region that is read-only or the wrong size. ``OpenFileMapping`` avoids
this entirely.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from ctypes import Structure
from typing import Protocol, TypeVar

from src.telemetry.converters import (
    graphics_from_struct,
    physics_from_struct,
    static_from_struct,
)
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


class SharedMemoryUnavailableError(TelemetrySourceError):
    """Raised when AC's shared-memory regions cannot be opened.

    This is the normal "Assetto Corsa is not running yet" signal: the named
    regions do not exist, so there is nothing to open. Callers should treat it
    as *wait and retry*, not a fatal error.
    """


class UnsupportedPlatformError(TelemetrySourceError):
    """Raised when live shared memory is used on a non-Windows platform."""


class _MappedView:  # pragma: no cover - Windows-only mapped view
    """Read-only, seekable view over a ``MapViewOfFile`` pointer.

    Exposes the minimal ``seek`` / ``read`` / ``close`` surface the reader needs.
    Reads copy bytes out of the mapping, so callers never retain a live pointer
    into shared memory.
    """

    def __init__(self, handle: int, address: int, size: int) -> None:
        self._handle: int | None = handle
        self._address: int | None = address
        self._size = size
        self._pos = 0

    def seek(self, pos: int) -> int:
        self._pos = pos
        return pos

    def read(self, size: int) -> bytes:
        import ctypes

        if self._address is None:
            raise TelemetrySourceError("read from a closed shared-memory view")
        count = max(0, min(size, self._size - self._pos))
        data = ctypes.string_at(self._address + self._pos, count)
        self._pos += count
        return data

    def close(self) -> None:
        if sys.platform != "win32":  # pragma: no cover - never constructed off Windows
            return
        import ctypes

        if self._address is not None:
            ctypes.windll.kernel32.UnmapViewOfFile(ctypes.c_void_p(self._address))
            self._address = None
        if self._handle is not None:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._handle))
            self._handle = None


def open_windows_shared_memory(name: str, size: int) -> ReadableBuffer:  # pragma: no cover
    """Open an *existing* Windows named shared-memory region for reading.

    Uses ``OpenFileMapping`` (never ``CreateFileMapping``), so the region is only
    ever opened, never created. If Assetto Corsa has not created it yet, this
    raises :class:`SharedMemoryUnavailableError` rather than silently creating a
    section that would later crash AC's shared-memory writer.
    """
    if sys.platform != "win32":
        raise UnsupportedPlatformError(
            "live shared-memory telemetry is only available on Windows"
        )
    import ctypes
    from ctypes import wintypes

    file_map_read = 0x0004
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_mapping = kernel32.OpenFileMappingW
    open_mapping.restype = wintypes.HANDLE
    open_mapping.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    handle = open_mapping(file_map_read, False, name)
    if not handle:
        err = ctypes.get_last_error()
        raise SharedMemoryUnavailableError(
            f"shared-memory region {name!r} is not available "
            f"(is Assetto Corsa running and in a session?); "
            f"OpenFileMapping failed (WinError {err})"
        )
    map_view = kernel32.MapViewOfFile
    map_view.restype = wintypes.LPVOID
    map_view.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_size_t,
    ]
    address = map_view(handle, file_map_read, 0, 0, size)
    if not address:
        err = ctypes.get_last_error()
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        raise SharedMemoryUnavailableError(
            f"could not map shared-memory region {name!r} (WinError {err})"
        )
    return _MappedView(int(handle), int(address), size)


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
        try:
            self._physics_map = self._opener(PHYSICS_MAP_NAME, PHYSICS_SIZE)
            self._graphics_map = self._opener(GRAPHICS_MAP_NAME, GRAPHICS_SIZE)
            self._static_map = self._opener(STATIC_MAP_NAME, STATIC_SIZE)
            raw_static = self._read_struct(self._static_map, SPageFileStatic, STATIC_SIZE)
            self._static = static_from_struct(raw_static)
        except Exception:
            # Never leak partially-opened maps if a later open or read fails.
            self.close()
            raise
        return self._static

    def read_frame(self) -> TelemetryFrame:
        if self._physics_map is None or self._graphics_map is None or self._static is None:
            raise SourceNotConnectedError("call connect() before read_frame()")
        physics = self._read_struct(self._physics_map, SPageFilePhysics, PHYSICS_SIZE)
        graphics = self._read_struct(self._graphics_map, SPageFileGraphic, GRAPHICS_SIZE)
        return TelemetryFrame(
            timestamp=self._clock(),
            physics=physics_from_struct(physics),
            graphics=graphics_from_struct(graphics),
            static_info=self._static,
        )

    def read_static(self) -> ACStaticInfo:
        """Re-read the static page so a mid-stream car/track change is detected.

        Assetto Corsa keeps the shared-memory regions alive for the whole game
        launch and rewrites the static page on each session load, so re-parsing
        the already-open mapping yields the current track and car.
        """
        if self._static_map is None:
            raise SourceNotConnectedError("call connect() before read_static()")
        raw_static = self._read_struct(self._static_map, SPageFileStatic, STATIC_SIZE)
        self._static = static_from_struct(raw_static)
        return self._static

    def close(self) -> None:
        for buffer in (self._physics_map, self._graphics_map, self._static_map):
            if buffer is not None:
                buffer.close()
        self._physics_map = None
        self._graphics_map = None
        self._static_map = None

    # -- Internal helpers --------------------------------------------------
    @staticmethod
    def _read_struct(buffer: ReadableBuffer, struct_type: type[_S], size: int) -> _S:
        buffer.seek(0)
        data = buffer.read(size)
        if len(data) < size:
            raise TelemetrySourceError(
                f"short read from shared memory: expected {size} bytes, got {len(data)}"
            )
        return struct_type.from_buffer_copy(data)
