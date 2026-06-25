"""Tests for session detection."""

from __future__ import annotations

from src.strategy.session_detector import SessionModeTracker
from src.telemetry.shm_structs import ACSessionType

from tests.factories import make_graphics


def test_first_update_reports_mode() -> None:
    tracker = SessionModeTracker()
    assert tracker.current is None
    changed = tracker.update(make_graphics(session_type=ACSessionType.PRACTICE))
    assert changed is ACSessionType.PRACTICE
    assert tracker.current is ACSessionType.PRACTICE


def test_no_change_returns_none() -> None:
    tracker = SessionModeTracker()
    tracker.update(make_graphics(session_type=ACSessionType.RACE))
    assert tracker.update(make_graphics(session_type=ACSessionType.RACE)) is None


def test_transition_detected() -> None:
    tracker = SessionModeTracker()
    tracker.update(make_graphics(session_type=ACSessionType.PRACTICE))
    changed = tracker.update(make_graphics(session_type=ACSessionType.QUALIFY))
    assert changed is ACSessionType.QUALIFY


def test_override_takes_precedence() -> None:
    tracker = SessionModeTracker()
    tracker.update(make_graphics(session_type=ACSessionType.PRACTICE))
    changed = tracker.set_override(ACSessionType.RACE)
    assert changed is ACSessionType.RACE
    assert tracker.current is ACSessionType.RACE
    # Auto-detection no longer changes the effective mode while overridden.
    assert tracker.update(make_graphics(session_type=ACSessionType.QUALIFY)) is None
    # Clearing the override falls back to the detected value.
    assert tracker.set_override(None) is ACSessionType.QUALIFY
