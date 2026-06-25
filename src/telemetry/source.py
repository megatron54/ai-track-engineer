"""Telemetry source abstraction.

A :class:`TelemetrySource` produces :class:`~src.telemetry.models.TelemetryFrame`
objects. Concrete implementations include the live Assetto Corsa shared-memory
reader and a mock generator for development without the game running. Consumers
depend only on this interface, so sources are fully interchangeable.
"""

from __future__ import annotations

import abc
import asyncio
import time
from collections.abc import AsyncIterator

from src.telemetry.models import ACStaticInfo, TelemetryFrame


class TelemetrySourceError(RuntimeError):
    """Base error for telemetry sources."""


class SourceNotConnectedError(TelemetrySourceError):
    """Raised when reading from a source that has not been connected."""


class TelemetrySource(abc.ABC):
    """Abstract base class for telemetry producers.

    Implementations provide three primitives — :meth:`connect`,
    :meth:`read_frame` and :meth:`close` — and inherit a fixed-rate
    :meth:`stream` and async-context-manager support.
    """

    @abc.abstractmethod
    def connect(self) -> ACStaticInfo:
        """Open the source and return the session's static information."""

    @abc.abstractmethod
    def read_frame(self) -> TelemetryFrame:
        """Read and return the most recent telemetry frame."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release any resources held by the source. Must be idempotent."""

    async def stream(
        self, hz: int, *, max_frames: int | None = None
    ) -> AsyncIterator[TelemetryFrame]:
        """Yield frames at a fixed rate using a drift-corrected scheduler.

        Args:
            hz: Target sampling rate in frames per second (must be > 0).
            max_frames: Optional cap on the number of frames to yield; ``None``
                streams indefinitely.

        Yields:
            Telemetry frames spaced as close to ``1/hz`` seconds apart as the
            host allows. If a read falls behind schedule the clock resynchronises
            instead of bursting to catch up.
        """
        if hz <= 0:
            raise ValueError(f"hz must be positive, got {hz}")

        period = 1.0 / hz
        next_tick = time.perf_counter()
        emitted = 0
        while max_frames is None or emitted < max_frames:
            yield self.read_frame()
            emitted += 1
            if max_frames is not None and emitted >= max_frames:
                break
            next_tick += period
            delay = next_tick - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                # Behind schedule: drop the backlog and resync to now.
                next_tick = time.perf_counter()

    def __enter__(self) -> TelemetrySource:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
