"""Tests for the corner coach."""

from __future__ import annotations

from src.knowledge.models import Corner, TrackInfo
from src.processing.corner_coach import CornerCoach
from src.processing.lap_trace import LapTrace
from src.processing.message_queue import MessagePriority

_TRACK = TrackInfo(
    track_id="t",
    name="T",
    corners=(
        Corner(index=1, name="T1", entry=0.1, exit=0.2),
        Corner(index=2, name="T2", entry=0.5, exit=0.6),
    ),
)


def _linear_trace(duration: float = 100.0) -> LapTrace:
    return LapTrace(1, [(p / 10.0, duration * p / 10.0, 150.0) for p in range(11)])


def test_post_corner_feedback_on_exit() -> None:
    coach = CornerCoach(_TRACK)
    coach.set_reference(_linear_trace())
    # Enter T1.
    msgs = coach.process(position=0.15, speed_kmh=100, elapsed_s=15.0, timestamp=1.0)
    assert msgs == []
    # Exit T1 — elapsed much longer than reference -> lost time.
    msgs = coach.process(position=0.25, speed_kmh=150, elapsed_s=30.0, timestamp=2.0)
    assert len(msgs) == 1
    assert "T1" in msgs[0].text
    assert "lost" in msgs[0].text


def test_no_feedback_within_threshold() -> None:
    coach = CornerCoach(_TRACK, delta_threshold=1.0)
    coach.set_reference(_linear_trace())
    coach.process(position=0.15, speed_kmh=100, elapsed_s=15.0, timestamp=1.0)
    # Exit with a delta below threshold -> no message.
    msgs = coach.process(position=0.25, speed_kmh=150, elapsed_s=20.1, timestamp=2.0)
    assert msgs == []


def test_brake_warning_when_too_fast() -> None:
    # Build a reference with a slow speed at position 0.08 (just before T1 entry).
    trace = LapTrace(1, [(0.0, 0.0, 200.0), (0.08, 8.0, 100.0), (1.0, 100.0, 200.0)])
    coach = CornerCoach(_TRACK)
    coach.set_reference(trace)
    # Car is at 0.08 going 140 km/h vs reference 100 -> brake earlier.
    msgs = coach.process(position=0.08, speed_kmh=140.0, elapsed_s=8.0, timestamp=1.0)
    assert any("brake earlier" in m.text for m in msgs)
    assert msgs[0].priority is MessagePriority.HIGH


def test_no_coaching_without_reference() -> None:
    coach = CornerCoach(_TRACK)
    msgs = coach.process(position=0.15, speed_kmh=100, elapsed_s=15.0, timestamp=1.0)
    assert msgs == []
