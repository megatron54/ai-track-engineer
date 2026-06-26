"""Priority message queue for real-time driver feedback.

Messages are classified by urgency. Consumers drain the queue and deliver the
most urgent items first. A configurable cooldown prevents overwhelming the
driver — after delivering a message, lower-priority messages are suppressed
for a short period.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from enum import IntEnum


class MessagePriority(IntEnum):
    """Message urgency (lower value = higher urgency, for min-heap ordering)."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True, frozen=True)
class PriorityMessage:
    """A message with a priority and a timestamp."""

    priority: MessagePriority
    timestamp: float = field(compare=False)
    text: str = field(compare=False)
    corner: str | None = field(default=None, compare=False)


class MessageQueue:
    """Priority queue with a cooldown between non-critical messages.

    ``CRITICAL`` messages bypass the cooldown entirely. All other priorities
    respect a minimum interval between deliveries.
    """

    def __init__(self, cooldown_s: float = 5.0) -> None:
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be >= 0")
        self._cooldown = cooldown_s
        self._heap: list[PriorityMessage] = []
        self._last_delivery: float = -1e9  # allow the very first pop immediately

    def push(self, message: PriorityMessage) -> None:
        """Add a message to the queue."""
        heapq.heappush(self._heap, message)

    def pop(self, now: float | None = None) -> PriorityMessage | None:
        """Return the most urgent deliverable message, or ``None``.

        A non-critical message is only returned if the cooldown has elapsed
        since the last delivery. ``CRITICAL`` messages are always returned.
        """
        if now is None:
            now = time.monotonic()
        if not self._heap:
            return None
        top = self._heap[0]
        if top.priority is MessagePriority.CRITICAL:
            self._last_delivery = now
            return heapq.heappop(self._heap)
        if now - self._last_delivery >= self._cooldown:
            self._last_delivery = now
            return heapq.heappop(self._heap)
        return None

    @property
    def pending(self) -> int:
        """Number of messages waiting in the queue."""
        return len(self._heap)

    def clear(self) -> None:
        """Drop all pending messages."""
        self._heap.clear()
