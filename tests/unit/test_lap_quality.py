"""Tests for the lap-quality guardrails (trainable-lap selection)."""

from __future__ import annotations

from src.ml.lap_quality import DropReason, LapQualityConfig, assess_laps
from src.ml.recorded_session import TelemetrySample


def _lap(
    lap: int,
    *,
    frames: int = 600,
    duration: float = 100.0,
    span: tuple[float, float] = (0.0, 1.0),
    tyre: float = 95.0,
    start: float = 0.0,
) -> list[TelemetrySample]:
    """Build a synthetic lap of samples with controllable quality knobs.

    Defaults model a clean ~100 s lap sampled densely enough (no large frame
    gaps) that only the knob under test trips a guardrail.
    """
    out: list[TelemetrySample] = []
    for i in range(frames):
        frac = i / (frames - 1)
        out.append(
            TelemetrySample(
                lap=lap,
                lap_pos=span[0] + (span[1] - span[0]) * frac,
                timestamp=start + duration * frac,
                speed_kmh=200.0,
                gear=4,
                brake=0.0,
                g_lat=0.0,
                tyre_temp_avg=tyre,
            )
        )
    return out


def test_good_lap_is_trainable() -> None:
    report = assess_laps({1: _lap(1)})
    assert report.trainable_laps == (1,)
    assert report.kept_count == 1
    assert report.dropped() == ()


def test_out_lap_dropped() -> None:
    report = assess_laps({0: _lap(0)})
    assert DropReason.OUT_LAP in report.assessments[0].reasons
    assert report.trainable_laps == ()


def test_cold_tyres_dropped() -> None:
    report = assess_laps({1: _lap(1, tyre=70.0)})
    assert DropReason.COLD_TYRES in report.assessments[0].reasons


def test_incomplete_lap_dropped() -> None:
    report = assess_laps({1: _lap(1, span=(0.0, 0.4))})
    assert DropReason.INCOMPLETE in report.assessments[0].reasons


def test_too_short_lap_dropped() -> None:
    report = assess_laps({1: _lap(1, duration=30.0)})
    assert DropReason.TOO_SHORT in report.assessments[0].reasons


def test_sparse_lap_dropped_for_few_frames() -> None:
    report = assess_laps({1: _lap(1, frames=40)})
    assert DropReason.SPARSE in report.assessments[0].reasons


def test_sparse_lap_dropped_for_large_gap() -> None:
    base = _lap(1)
    gapped = [
        TelemetrySample(
            lap=1,
            lap_pos=s.lap_pos,
            timestamp=s.timestamp + (3.0 if i >= 60 else 0.0),
            speed_kmh=s.speed_kmh,
            gear=s.gear,
            brake=s.brake,
            g_lat=s.g_lat,
            tyre_temp_avg=s.tyre_temp_avg,
        )
        for i, s in enumerate(base)
    ]
    report = assess_laps({1: gapped})
    assert DropReason.SPARSE in report.assessments[0].reasons


def test_invalid_lap_from_external_source() -> None:
    report = assess_laps({1: _lap(1)}, invalid_laps={1})
    assert DropReason.INVALID in report.assessments[0].reasons
    assert report.trainable_laps == ()


def test_slow_outlier_flagged_against_clean_median() -> None:
    laps = {i: _lap(i, duration=100.0, start=i * 200.0) for i in range(1, 7)}
    laps[7] = _lap(7, duration=150.0, start=1400.0)  # far slower than the median
    report = assess_laps(laps)
    verdicts = {a.lap: a for a in report.assessments}
    assert verdicts[7].kept is False
    assert DropReason.SLOW_OUTLIER in verdicts[7].reasons
    assert 1 in report.trainable_laps
    assert 6 in report.trainable_laps


def test_no_slow_outlier_below_min_sample() -> None:
    # Two laps is below min_outlier_sample, so no slow-outlier judgement is made.
    report = assess_laps({1: _lap(1, duration=100.0), 2: _lap(2, duration=140.0, start=400.0)})
    assert all(DropReason.SLOW_OUTLIER not in a.reasons for a in report.assessments)


def test_multiple_reasons_and_dropped_view() -> None:
    report = assess_laps({0: _lap(0, tyre=70.0, duration=30.0)})
    assessment = report.assessments[0]
    assert {DropReason.OUT_LAP, DropReason.COLD_TYRES, DropReason.TOO_SHORT} <= set(
        assessment.reasons
    )
    assert report.dropped() == (assessment,)


def test_custom_config_thresholds() -> None:
    # A street-tyre window keeps a lap that the slick default would reject as cold.
    cold_lap = {1: _lap(1, tyre=72.0)}
    assert assess_laps(cold_lap).trainable_laps == ()
    cfg = LapQualityConfig(tyre_window_low=70.0)
    assert assess_laps(cold_lap, config=cfg).trainable_laps == (1,)
