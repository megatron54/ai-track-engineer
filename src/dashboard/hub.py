"""In-memory message fan-out hub for the dashboard.

The capture loop publishes JSON-serialisable event envelopes
(``{"type": "telemetry"|"lap"|"session", ...}``); each connected client
subscribes to its own bounded queue. Messages are loss-tolerant: when a slow
client's queue is full the oldest message is dropped rather than blocking the
producer.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

Message = dict[str, Any]

_DEFAULT_QUEUE_SIZE = 16


class TelemetryHub:
    """Fan out event messages to any number of subscribers."""

    def __init__(self, queue_size: int = _DEFAULT_QUEUE_SIZE) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size must be positive")
        self._queue_size = queue_size
        self._subscribers: set[asyncio.Queue[Message]] = set()

    @property
    def subscriber_count(self) -> int:
        """Number of currently-subscribed clients."""
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue[Message]:
        """Register a new subscriber and return its message queue."""
        queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Message]) -> None:
        """Remove a subscriber (idempotent)."""
        self._subscribers.discard(queue)

    def publish(self, message: Message) -> None:
        """Deliver a message to all subscribers, dropping oldest if a queue is full."""
        for queue in self._subscribers:
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(message)
