"""Tests for the priority message queue."""

from __future__ import annotations

import pytest
from src.processing.message_queue import MessagePriority, MessageQueue, PriorityMessage


def _msg(priority: MessagePriority, text: str = "t") -> PriorityMessage:
    return PriorityMessage(priority=priority, timestamp=0.0, text=text)


def test_invalid_cooldown() -> None:
    with pytest.raises(ValueError, match="cooldown"):
        MessageQueue(cooldown_s=-1)


def test_pop_empty() -> None:
    assert MessageQueue().pop(now=0.0) is None


def test_highest_urgency_first() -> None:
    q = MessageQueue(cooldown_s=0)
    q.push(_msg(MessagePriority.LOW, "low"))
    q.push(_msg(MessagePriority.CRITICAL, "crit"))
    q.push(_msg(MessagePriority.NORMAL, "norm"))
    assert q.pop(now=0.0).text == "crit"
    assert q.pop(now=0.0).text == "norm"
    assert q.pop(now=0.0).text == "low"


def test_cooldown_suppresses_non_critical() -> None:
    q = MessageQueue(cooldown_s=5.0)
    q.push(_msg(MessagePriority.NORMAL, "a"))
    q.push(_msg(MessagePriority.NORMAL, "b"))
    first = q.pop(now=0.0)
    assert first is not None and first.text == "a"
    assert q.pop(now=1.0) is None  # cooldown not elapsed
    second = q.pop(now=6.0)
    assert second is not None and second.text == "b"  # after cooldown


def test_critical_bypasses_cooldown() -> None:
    q = MessageQueue(cooldown_s=10.0)
    q.push(_msg(MessagePriority.NORMAL, "norm"))
    q.pop(now=0.0)  # deliver 'norm', starts cooldown
    q.push(_msg(MessagePriority.CRITICAL, "crit"))
    assert q.pop(now=0.5).text == "crit"  # delivered despite cooldown


def test_clear() -> None:
    q = MessageQueue()
    q.push(_msg(MessagePriority.LOW))
    q.push(_msg(MessagePriority.HIGH))
    q.clear()
    assert q.pending == 0
    assert q.pop(now=0.0) is None
