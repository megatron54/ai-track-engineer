"""Tests for the lap segmenter."""

from __future__ import annotations

from src.processing import Lap, LapSegmenter
from src.telemetry.mock import MockTelemetrySource

from tests.factories import make_frame, make_graphics


def _frame(
    ts: float,
    *,
    completed_laps: int,
    sector_index: int,
    last_sector_ms: int = 0,
    last_time_ms: int = 0,
    in_pit: bool = False,
):
    graphics = make_graphics(
        completed_laps=completed_laps,
        current_sector_index=sector_index,
        last_sector_time_ms=last_sector_ms,
        last_time_ms=last_time_ms,
        is_in_pit=in_pit,
        is_in_pit_lane=in_pit,
    )
    return make_frame(timestamp=ts, graphics=graphics)


def test_first_frame_emits_no_lap() -> None:
    segmenter = LapSegmenter()
    assert segmenter.process(_frame(0.0, completed_laps=0, sector_index=0)) is None


def test_completed_lap_is_emitted_with_timing_and_sectors() -> None:
    segmenter = LapSegmenter()
    segmenter.process(_frame(0.0, completed_laps=0, sector_index=0))
    segmenter.process(_frame(1.0, completed_laps=0, sector_index=1, last_sector_ms=30_000))
    segmenter.process(_frame(2.0, completed_laps=0, sector_index=2, last_sector_ms=28_000))
    lap = segmenter.process(
        _frame(3.0, completed_laps=1, sector_index=0, last_sector_ms=30_000, last_time_ms=88_000)
    )

    assert lap is not None
    assert lap.lap_number == 1
    assert lap.lap_time_ms == 88_000
    assert lap.lap_time_seconds == 88.0
    assert lap.sector_times_ms == (30_000, 28_000, 30_000)
    assert lap.valid is True
    assert lap.started_at == 0.0
    assert lap.ended_at == 3.0


def test_lap_using_pit_is_marked_invalid() -> None:
    segmenter = LapSegmenter()
    segmenter.process(_frame(0.0, completed_laps=0, sector_index=0))
    segmenter.process(_frame(1.0, completed_laps=0, sector_index=1, in_pit=True))
    lap = segmenter.process(
        _frame(2.0, completed_laps=1, sector_index=0, last_time_ms=95_000)
    )
    assert lap is not None
    assert lap.valid is False


def test_multiple_laps_are_numbered_in_order() -> None:
    segmenter = LapSegmenter()
    segmenter.process(_frame(0.0, completed_laps=0, sector_index=0))
    laps = []
    for lap_index in range(1, 4):
        lap = segmenter.process(
            _frame(
                float(lap_index),
                completed_laps=lap_index,
                sector_index=0,
                last_time_ms=80_000 + lap_index,
            )
        )
        if lap is not None:
            laps.append(lap)
    assert [lap.lap_number for lap in laps] == [1, 2, 3]


def test_zero_sector_splits_are_ignored() -> None:
    segmenter = LapSegmenter()
    segmenter.process(_frame(0.0, completed_laps=0, sector_index=0))
    # Sector changes but the split time is unknown (0) -> not recorded.
    segmenter.process(_frame(1.0, completed_laps=0, sector_index=1, last_sector_ms=0))
    lap = segmenter.process(
        _frame(2.0, completed_laps=1, sector_index=0, last_time_ms=90_000)
    )
    assert lap is not None
    assert lap.sector_times_ms == ()


async def test_segment_over_mock_stream_yields_laps() -> None:
    source = MockTelemetrySource(dt=0.05, lap_time_s=2.0)
    source.connect()
    segmenter = LapSegmenter()
    laps: list[Lap] = [
        lap async for lap in segmenter.segment(source.stream(2000, max_frames=120))
    ]
    source.close()
    assert len(laps) >= 2
    assert all(lap.lap_time_ms > 0 for lap in laps)
    assert [lap.lap_number for lap in laps] == sorted(lap.lap_number for lap in laps)
