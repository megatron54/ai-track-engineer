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
from typing import Literal

from src.observability import get_logger
from src.telemetry.models import ACStaticInfo, TelemetryFrame

_log = get_logger("telemetry.source")


class TelemetrySourceError(RuntimeError):
    """Base error for telemetry sources."""


class SourceNotConnectedError(TelemetrySourceError):
    """Raised when reading from a source that has not been connected."""


class SessionChangedError(TelemetrySourceError):
    """Raised mid-stream when the static page reports a new track/car/config.

    Carries the freshly-read static info so the caller can tear down the old
    session (recorder, DB session, track) and start a new one without a restart.
    """

    def __init__(self, new_static: ACStaticInfo) -> None:
        super().__init__(
            f"session changed to track={new_static.track!r} "
            f"config={new_static.track_configuration!r} car={new_static.car_model!r}"
        )
        self.new_static = new_static


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

    def read_static(self) -> ACStaticInfo:
        """Re-read the static page (track / car / config) without reconnecting.

        Sources backed by a live session (shared memory) override this to detect
        a mid-stream session change. The default declares it unsupported.
        """
        raise NotImplementedError("this source does not support read_static()")

    async def stream(
        self,
        hz: int,
        *,
        max_frames: int | None = None,
        on_error: Literal["raise", "skip"] = "raise",
    ) -> AsyncIterator[TelemetryFrame]:
        """Yield frames at a fixed rate using a drift-corrected scheduler.

        Args:
            hz: Target sampling rate in frames per second (must be > 0).
            max_frames: Optional cap on the number of frames yielded; ``None``
                streams indefinitely.
            on_error: How to handle a :class:`TelemetrySourceError` from
                :meth:`read_frame`. ``"raise"`` (default) propagates it;
                ``"skip"`` logs the error and continues to the next tick — useful
                for long unattended sessions that must survive a transient bad
                read without tearing down the loop.

        Yields:
            Telemetry frames spaced as close to ``1/hz`` seconds apart as the
            host allows. If a read falls behind schedule the clock resynchronises
            instead of bursting to catch up. Skipped frames (on read errors) do
            not count towards ``max_frames``.
        """
        if hz <= 0:
            raise ValueError(f"hz must be positive, got {hz}")

        period = 1.0 / hz
        next_tick = time.perf_counter()
        emitted = 0
        while max_frames is None or emitted < max_frames:
            try:
                frame = self.read_frame()
            except TelemetrySourceError:
                if on_error == "raise":
                    raise
                _log.warning("telemetry-read-failed", action="skip", exc_info=True)
            else:
                emitted += 1
                yield frame
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
