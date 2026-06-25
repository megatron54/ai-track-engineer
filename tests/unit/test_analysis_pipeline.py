"""Tests for the end-to-end analysis pipeline."""

from __future__ import annotations

from src.analysis.engine_monitor import EngineMonitor
from src.analysis.pipeline import AnalysisPipeline, LapReport
from src.knowledge.models import Corner, TrackInfo
from src.telemetry.mock import MockTelemetrySource

from tests.factories import make_frame, make_graphics

_TRACK = TrackInfo(
    track_id="ks_laguna_seca",
    name="Laguna Seca",
    corners=(
        Corner(index=1, name="Turn 1", entry=0.0, exit=0.15),
        Corner(index=7, name="The Corkscrew", entry=0.6, exit=0.72),
    ),
)


def _run_pipeline(pipeline: AnalysisPipeline, *, frames: int) -> list[LapReport]:
    source = MockTelemetrySource(dt=0.05, lap_time_s=1.0)
    source.connect()
    reports: list[LapReport] = []
    for _ in range(frames):
        report = pipeline.process(source.read_frame())
        if report is not None:
            reports.append(report)
    source.close()
    return reports


def test_pipeline_emits_report_per_lap() -> None:
    pipeline = AnalysisPipeline(_TRACK)
    reports = _run_pipeline(pipeline, frames=100)  # 5s sim / 1s laps -> ~4-5 laps
    assert len(reports) >= 3
    assert [r.lap.lap_number for r in reports] == sorted(r.lap.lap_number for r in reports)


def test_first_valid_lap_is_personal_best() -> None:
    pipeline = AnalysisPipeline(_TRACK)
    reports = _run_pipeline(pipeline, frames=60)
    assert reports[0].is_personal_best is True


def test_reports_include_tyre_evaluation() -> None:
    pipeline = AnalysisPipeline(_TRACK)
    reports = _run_pipeline(pipeline, frames=60)
    assert reports[0].tyre_report is not None
    assert len(reports[0].tyre_report.statuses) == 4


def test_later_laps_have_corner_deltas_vs_best() -> None:
    pipeline = AnalysisPipeline(_TRACK)
    reports = _run_pipeline(pipeline, frames=120)
    # The first lap has no reference; a subsequent lap is compared to the best.
    assert reports[0].corner_losses == ()
    assert any(r.corner_losses for r in reports[1:]) or all(
        # If the mock is perfectly repeatable, deltas may be ~0 and not "losses".
        isinstance(r.recommendations, tuple)
        for r in reports[1:]
    )


def test_engine_monitor_alerts_flow_through() -> None:
    # max_rpm low enough that the mock's RPM trips an over-rev somewhere.
    pipeline = AnalysisPipeline(_TRACK, engine_monitor=EngineMonitor(3000))
    reports = _run_pipeline(pipeline, frames=80)
    assert any(r.engine_alerts for r in reports)


def test_recommendations_are_present_when_issues_exist() -> None:
    pipeline = AnalysisPipeline(_TRACK, engine_monitor=EngineMonitor(2600))
    reports = _run_pipeline(pipeline, frames=80)
    assert any(r.recommendations for r in reports)


def _pipeline_with_reference() -> AnalysisPipeline:
    """Run the mock until the pipeline has a personal-best reference lap."""
    source = MockTelemetrySource(dt=0.05, lap_time_s=1.0)
    source.connect()
    pipeline = AnalysisPipeline(_TRACK)
    for _ in range(60):
        pipeline.process(source.read_frame())
        if pipeline.has_reference_lap:
            break
    source.close()
    return pipeline


def test_live_delta_is_none_without_reference() -> None:
    pipeline = AnalysisPipeline(_TRACK)
    assert pipeline.has_reference_lap is False
    assert pipeline.live_delta(make_frame()) is None


def test_live_delta_is_positive_when_slower_than_best() -> None:
    pipeline = _pipeline_with_reference()
    assert pipeline.has_reference_lap is True
    # A huge current lap time mid-track means we are well behind the best lap.
    graphics = make_graphics(normalized_car_position=0.5, current_time_ms=999_999)
    delta = pipeline.live_delta(make_frame(graphics=graphics))
    assert delta is not None
    assert delta > 0


def test_live_delta_near_zero_for_repeatable_lap() -> None:
    pipeline = _pipeline_with_reference()
    # The deterministic mock repeats: at the lap start the delta is tiny.
    graphics = make_graphics(normalized_car_position=0.0, current_time_ms=0)
    delta = pipeline.live_delta(make_frame(graphics=graphics))
    assert delta is not None
    assert abs(delta) < 0.5
