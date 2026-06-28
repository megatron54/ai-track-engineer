"""End-to-end per-lap analysis pipeline.

The :class:`AnalysisPipeline` is the product's core loop: feed it telemetry
frames and, each time a lap completes, it builds a position-indexed trace,
compares it against the driver's best lap so far, evaluates tyre and engine
state, and produces coaching recommendations. It keeps the best lap as the
rolling reference.

It uses the deterministic heuristic advisor by default so it works from the
first lap with no model; an LLM can enrich advice separately.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.ai.advisor import RaceEngineerAdvisor
from src.ai.models import Recommendation
from src.analysis.engine_monitor import EngineAlert, EngineMonitor
from src.analysis.lap_comparator import LapComparison
from src.analysis.models import CornerDelta
from src.analysis.tyre_model import TyreThermalModel, TyreThermalReport, window_for_compound
from src.knowledge.models import TrackInfo
from src.processing.lap_segmenter import LapSegmenter
from src.processing.lap_trace import LapTrace
from src.processing.models import Lap
from src.telemetry.models import TelemetryFrame

_MIN_TRACE_FRAMES = 2


class LapReport(BaseModel):
    """The analysis produced for one completed lap."""

    model_config = ConfigDict(frozen=True)

    lap: Lap
    is_personal_best: bool
    corner_losses: tuple[CornerDelta, ...] = ()
    tyre_report: TyreThermalReport | None = None
    engine_alerts: tuple[EngineAlert, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()


class AnalysisPipeline:
    """Turn a telemetry stream into per-lap analysis reports."""

    def __init__(
        self,
        track: TrackInfo,
        *,
        advisor: RaceEngineerAdvisor | None = None,
        tyre_model: TyreThermalModel | None = None,
        engine_monitor: EngineMonitor | None = None,
        min_lap_time_ms: int = 60_000,
    ) -> None:
        self._track = track
        self._advisor = advisor or RaceEngineerAdvisor()
        self._tyre_model = tyre_model or TyreThermalModel()
        self._engine_monitor = engine_monitor
        self._segmenter = LapSegmenter(min_lap_time_ms=min_lap_time_ms)
        self._buffer: list[TelemetryFrame] = []
        self._best_trace: LapTrace | None = None
        self._best_lap_time_ms: int | None = None
        self._lap_start_timestamp: float = 0.0
        self._last_position: float | None = None
        self._compound_detected: str | None = None

    def process(self, frame: TelemetryFrame) -> LapReport | None:
        """Feed a frame; return a :class:`LapReport` when a lap completes."""
        # Auto-detect tyre compound and adjust thermal thresholds once.
        compound = frame.graphics.tyre_compound
        if compound and compound != self._compound_detected:
            self._compound_detected = compound
            opt_min, opt_max = window_for_compound(compound)
            self._tyre_model = TyreThermalModel(optimal_min=opt_min, optimal_max=opt_max)

        # Re-anchor the live-delta clock whenever the car crosses the start/
        # finish line (normalised position wraps from ~1 back to ~0). This is
        # independent of lap *completion*, so the delta stays correct even when
        # a lap is restarted mid-flight (e.g. AC hotlap restart or a teleport),
        # where the segmenter never reports a finished lap.
        position = frame.graphics.normalized_car_position
        if self._last_position is not None and position + 0.5 < self._last_position:
            self._lap_start_timestamp = frame.timestamp
        self._last_position = position

        self._buffer.append(frame)
        lap = self._segmenter.process(frame)
        if lap is None:
            return None

        # Frames for the finished lap exclude the crossing frame (start of the
        # next lap), which is kept to seed the next buffer.
        lap_frames = self._buffer[:-1]
        report = self._build_report(lap, lap_frames)
        self._buffer = [frame]
        return report

    def live_delta(self, frame: TelemetryFrame) -> float | None:
        """Real-time delta vs the personal-best lap at the car's position.

        Returns the current lap's elapsed time minus the best lap's time at the
        same normalised track position: positive means losing time, negative
        means gaining. ``None`` until a best lap exists.

        Both sides use the same capture clock (``frame.timestamp``): the best
        trace is rebased to zero at its own lap start, and the current lap's
        elapsed time is measured from ``_lap_start_timestamp`` (set when the lap
        began). Using one monotonic clock avoids AC's ``iCurrentTime`` field,
        whose meaning is inconsistent across laps and session resets and which
        produced wildly wrong deltas.
        """
        if self._best_trace is None:
            return None
        position = frame.graphics.normalized_car_position
        current_elapsed = frame.timestamp - self._lap_start_timestamp
        if current_elapsed < 0:
            return None  # timestamp predates the lap start (seek / session reset)
        return current_elapsed - self._best_trace.time_at(position)

    @property
    def has_reference_lap(self) -> bool:
        """Whether a best lap is available to compare against."""
        return self._best_trace is not None

    def _build_report(self, lap: Lap, frames: list[TelemetryFrame]) -> LapReport:
        trace = self._build_trace(lap, frames)
        is_pb = self._is_personal_best(lap)

        corner_losses: tuple[CornerDelta, ...] = ()
        if trace is not None and self._best_trace is not None:
            comparison = LapComparison(self._best_trace, trace)
            corner_losses = tuple(comparison.biggest_losses(self._track, limit=3))

        tyre_report: TyreThermalReport | None = None
        engine_alerts: tuple[EngineAlert, ...] = ()
        if frames:
            tyre_report = self._tyre_model.evaluate(frames[-1].physics)
            engine_alerts = self._collect_engine_alerts(frames)

        recommendations = tuple(
            self._advisor.heuristic_advice(
                corner_losses=list(corner_losses),
                tyre_report=tyre_report,
                engine_alerts=list(engine_alerts),
            )
        )

        # Only a clean, complete lap may become the delta reference. A trace
        # stitched across a hotlap restart or teleport has non-monotonic time
        # and would corrupt the live delta, so it is rejected here.
        if lap.valid and is_pb and trace is not None and trace.is_clean:
            self._best_trace = trace
            self._best_lap_time_ms = lap.lap_time_ms

        return LapReport(
            lap=lap,
            is_personal_best=is_pb,
            corner_losses=corner_losses,
            tyre_report=tyre_report,
            engine_alerts=engine_alerts,
            recommendations=recommendations,
        )

    def _build_trace(self, lap: Lap, frames: list[TelemetryFrame]) -> LapTrace | None:
        if len(frames) < _MIN_TRACE_FRAMES:
            return None
        try:
            return LapTrace.from_frames(lap.lap_number, frames)
        except ValueError:
            return None

    def _is_personal_best(self, lap: Lap) -> bool:
        if not lap.valid:
            return False
        return self._best_lap_time_ms is None or lap.lap_time_ms < self._best_lap_time_ms

    def _collect_engine_alerts(self, frames: list[TelemetryFrame]) -> tuple[EngineAlert, ...]:
        if self._engine_monitor is None:
            return ()
        # Check the highest-RPM frame of the lap (most likely to alert).
        peak = max(frames, key=lambda frame: frame.physics.rpm)
        return tuple(self._engine_monitor.check(peak.physics))
