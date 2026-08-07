"""Tests for per-corner driver-input analysis (brake/throttle/steering)."""

from __future__ import annotations

from src.analysis.input_analyzer import (
    CornerInputDelta,
    compare_corner_inputs,
    corner_input_profile,
    format_input_detail,
)
from src.knowledge.models import Corner
from src.processing.lap_trace import LapTrace

# A simple, non-wrapping corner: entry at 0.40, exit at 0.50.
_CORNER = Corner(index=1, name="T1", entry=0.40, exit=0.50)


def _reference_trace() -> LapTrace:
    """A 'good' lap: brakes early (0.30), gets back on throttle early (0.44)."""
    return LapTrace(
        1,
        [
            (0.00, 0.0, 200.0, 0.0, 1.0, 0.0),
            (0.28, 2.8, 150.0, 0.0, 0.0, 0.0),
            (0.30, 3.0, 140.0, 0.6, 0.0, 0.0),
            (0.32, 3.2, 120.0, 1.0, 0.0, 0.10),
            (0.40, 4.0, 90.0, 0.8, 0.0, 0.30),
            (0.44, 4.4, 85.0, 0.0, 0.6, 0.20),
            (0.46, 4.6, 95.0, 0.0, 1.0, 0.10),
            (0.50, 5.0, 130.0, 0.0, 1.0, 0.0),
            (0.60, 6.0, 200.0, 0.0, 1.0, 0.0),
            (1.00, 10.0, 200.0, 0.0, 1.0, 0.0),
        ],
    )


def _worse_trace() -> LapTrace:
    """A 'worse' lap: brakes later (0.34), throttle back on later (0.48), and
    fights the wheel a bit more on entry (extra steering reversal)."""
    return LapTrace(
        2,
        [
            (0.00, 0.0, 200.0, 0.0, 1.0, 0.0),
            (0.28, 2.7, 160.0, 0.0, 0.0, 0.0),
            (0.34, 3.3, 150.0, 0.6, 0.0, 0.0),
            (0.36, 3.5, 125.0, 1.0, 0.0, 0.10),
            (0.40, 4.1, 100.0, 0.8, 0.0, -0.10),
            (0.42, 4.3, 95.0, 0.6, 0.0, 0.25),
            (0.46, 4.7, 88.0, 0.0, 0.4, 0.15),
            (0.48, 4.9, 92.0, 0.0, 1.0, 0.05),
            (0.50, 5.1, 128.0, 0.0, 1.0, 0.0),
            (0.60, 6.1, 200.0, 0.0, 1.0, 0.0),
            (1.00, 10.1, 200.0, 0.0, 1.0, 0.0),
        ],
    )


def test_corner_input_profile_finds_brake_and_throttle_points() -> None:
    profile = corner_input_profile(_reference_trace(), _CORNER)
    assert profile.corner_name == "T1"
    assert profile.brake_point is not None
    assert 0.27 < profile.brake_point < 0.29
    assert profile.throttle_point is not None
    assert 0.40 < profile.throttle_point < 0.41


def test_corner_input_profile_none_when_never_braked() -> None:
    flat_out = LapTrace(
        1,
        [
            (0.20, 2.0, 200.0, 0.0, 1.0, 0.0),
            (0.40, 4.0, 200.0, 0.0, 1.0, 0.0),
            (0.50, 5.0, 200.0, 0.0, 1.0, 0.0),
        ],
    )
    profile = corner_input_profile(flat_out, _CORNER)
    assert profile.brake_point is None


def test_compare_corner_inputs_detects_later_brake_point() -> None:
    delta = compare_corner_inputs(_worse_trace(), _reference_trace(), _CORNER)
    assert delta.corner_name == "T1"
    # The worse lap braked later -> positive delta (current minus reference).
    assert delta.brake_point_delta is not None
    assert delta.brake_point_delta > 0

    # Converted to metres on a 4000m track, it should be a plausible distance,
    # not a rounding artefact.
    metres = delta.brake_point_delta_m(4000.0)
    assert metres is not None
    assert metres > 0


def test_compare_corner_inputs_detects_later_throttle_point() -> None:
    delta = compare_corner_inputs(_worse_trace(), _reference_trace(), _CORNER)
    assert delta.throttle_point_delta is not None
    assert delta.throttle_point_delta > 0


def test_compare_corner_inputs_detects_more_steering_reversals() -> None:
    delta = compare_corner_inputs(_worse_trace(), _reference_trace(), _CORNER)
    assert delta.steering_reversals_delta > 0


def test_compare_corner_inputs_against_itself_is_zero() -> None:
    reference = _reference_trace()
    delta = compare_corner_inputs(reference, reference, _CORNER)
    assert delta.brake_point_delta == 0.0
    assert delta.throttle_point_delta == 0.0
    assert delta.steering_reversals_delta == 0
    assert delta.brake_point_delta_m(4000.0) == 0.0


def test_position_delta_helpers_return_none_without_a_track_length() -> None:
    delta = compare_corner_inputs(_worse_trace(), _reference_trace(), _CORNER)
    assert delta.brake_point_delta_m(0.0) is None


def _delta(**overrides: object) -> CornerInputDelta:
    base: dict[str, object] = {
        "corner_index": 1,
        "corner_name": "T1",
        "brake_point_delta": None,
        "throttle_point_delta": None,
        "trail_braking_overlap_delta": 0.0,
        "steering_reversals_delta": 0,
    }
    base.update(overrides)
    return CornerInputDelta(**base)  # type: ignore[arg-type]


def test_format_input_detail_reports_later_brake_point() -> None:
    detail = format_input_detail(_delta(brake_point_delta=0.01), 1000.0)
    assert detail == "braked 10m later"


def test_format_input_detail_reports_earlier_brake_point() -> None:
    detail = format_input_detail(_delta(brake_point_delta=-0.01), 1000.0)
    assert detail == "braked 10m earlier"


def test_format_input_detail_reports_throttle_point() -> None:
    detail = format_input_detail(_delta(throttle_point_delta=0.02), 1000.0)
    assert detail == "throttle 20m later"


def test_format_input_detail_combines_multiple_signals() -> None:
    detail = format_input_detail(
        _delta(brake_point_delta=0.01, steering_reversals_delta=2), 1000.0
    )
    assert detail == "braked 10m later, +2 steering corrections"


def test_format_input_detail_none_when_nothing_reportable() -> None:
    # Deltas exist but are below the minimum reportable distance.
    assert format_input_detail(_delta(brake_point_delta=0.0001), 1000.0) is None
    assert format_input_detail(_delta(), 1000.0) is None
