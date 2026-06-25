"""Tests for the lap comparator."""

from __future__ import annotations

import pytest
from src.analysis.lap_comparator import LapComparison
from src.knowledge.models import Corner, TrackInfo
from src.processing.lap_trace import LapTrace


def _linear_trace(lap_number: int, duration: float) -> LapTrace:
    """A trace where time advances linearly from 0 to *duration* over the lap."""
    samples = [(p / 10.0, duration * p / 10.0, 150.0) for p in range(11)]
    return LapTrace(lap_number, samples)


def test_final_delta_reflects_lap_time_gap() -> None:
    reference = _linear_trace(1, 90.0)
    current = _linear_trace(2, 91.0)
    comparison = LapComparison(reference, current)
    assert comparison.final_delta() == pytest.approx(1.0, abs=1e-6)


def test_time_delta_grows_through_lap() -> None:
    comparison = LapComparison(_linear_trace(1, 90.0), _linear_trace(2, 90.9))
    assert comparison.time_delta_at(0.5) == pytest.approx(0.45, abs=1e-6)


def test_delta_curve_samples_overlap() -> None:
    comparison = LapComparison(_linear_trace(1, 90.0), _linear_trace(2, 92.0))
    curve = comparison.delta_curve(samples=5)
    assert len(curve) == 5
    assert curve[0][1] == pytest.approx(0.0, abs=1e-6)
    assert curve[-1][1] == pytest.approx(2.0, abs=1e-6)


def test_delta_curve_rejects_too_few_samples() -> None:
    comparison = LapComparison(_linear_trace(1, 90.0), _linear_trace(2, 90.0))
    with pytest.raises(ValueError, match="samples must be >= 2"):
        comparison.delta_curve(samples=1)


def test_corner_delta_for_normal_corner() -> None:
    # Reference even pace; current loses time specifically between 0.2 and 0.4.
    reference = _linear_trace(1, 100.0)
    current = LapTrace(
        2,
        [
            (0.0, 0.0, 150.0),
            (0.2, 20.0, 150.0),
            (0.4, 45.0, 120.0),  # 25s for this 0.2 segment vs 20s reference -> +5s
            (0.6, 65.0, 150.0),
            (1.0, 105.0, 150.0),
        ],
    )
    comparison = LapComparison(reference, current)
    corner = Corner(index=1, name="T2", entry=0.2, exit=0.4)
    delta = comparison.corner_delta(corner)
    assert delta.corner_name == "T2"
    assert delta.delta_s == pytest.approx(5.0, abs=1e-6)
    assert delta.lost_time is True


def test_corner_delta_handles_wrap() -> None:
    reference = _linear_trace(1, 100.0)
    current = _linear_trace(2, 100.0)
    comparison = LapComparison(reference, current)
    wrap_corner = Corner(index=0, name="T1", entry=0.9, exit=0.1)
    # Identical laps -> zero delta even across the wrap.
    assert comparison.corner_delta(wrap_corner).delta_s == pytest.approx(0.0, abs=1e-6)


def test_biggest_losses_ranks_worst_corners() -> None:
    reference = _linear_trace(1, 100.0)
    current = LapTrace(
        2,
        [
            (0.0, 0.0, 150.0),
            (0.2, 22.0, 150.0),  # +2s in T1 (0.0-0.2)
            (0.5, 52.0, 150.0),  # +1s more by 0.5
            (0.7, 78.0, 150.0),  # +5s in T3 (0.5-0.7)
            (1.0, 108.0, 150.0),
        ],
    )
    track = TrackInfo(
        track_id="t",
        name="T",
        corners=(
            Corner(index=1, name="T1", entry=0.0, exit=0.2),
            Corner(index=2, name="T2", entry=0.2, exit=0.5),
            Corner(index=3, name="T3", entry=0.5, exit=0.7),
        ),
    )
    comparison = LapComparison(reference, current)
    losses = comparison.biggest_losses(track, limit=2)
    assert [d.corner_name for d in losses] == ["T3", "T1"]
    assert losses[0].delta_s > losses[1].delta_s
