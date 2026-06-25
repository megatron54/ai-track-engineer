"""In-memory telemetry fan-out hub.

The capture loop publishes frames to a :class:`TelemetryHub`; each connected
dashboard client subscribes to its own bounded queue. Telemetry is loss-tolerant
for display, so when a slow client's queue is full the oldest frame is dropped
rather than blocking the 60 Hz producer.
"""

from __future__ import annotations

import asyncio
import contextlib

from src.telemetry.models import TelemetryFrame

_DEFAULT_QUEUE_SIZE = 5


class TelemetryHub:
    """Fan out telemetry frames to any number of subscribers."""

    def __init__(self, queue_size: int = _DEFAULT_QUEUE_SIZE) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size must be positive")
        self._queue_size = queue_size
        self._subscribers: set[asyncio.Queue[TelemetryFrame]] = set()

    @property
    def subscriber_count(self) -> int:
        """Number of currently-subscribed clients."""
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue[TelemetryFrame]:
        """Register a new subscriber and return its frame queue."""
        queue: asyncio.Queue[TelemetryFrame] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[TelemetryFrame]) -> None:
        """Remove a subscriber (idempotent)."""
        self._subscribers.discard(queue)

    def publish(self, frame: TelemetryFrame) -> None:
        """Deliver a frame to all subscribers, dropping oldest if a queue is full."""
        for queue in self._subscribers:
            if queue.full():
                # Drop the oldest frame to make room; telemetry is loss-tolerant.
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(frame)
