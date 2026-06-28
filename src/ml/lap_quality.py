"""Lap-quality guardrails: select trainable laps from a recorded session.

A predictive model is only as good as the laps it learns from. Training on
warm-up laps, out/in laps, cut laps, or one-off disasters (spins, traffic,
mistakes) teaches the model noise. :func:`assess_laps` scores every recorded lap
and keeps only the ones worth training on, attaching an explicit
:class:`DropReason` to each lap it rejects so the selection is auditable.

Guardrails applied (all derived from the recorded CSV, no game required):

* **out_lap** - AC reports ``lap == 0`` for the whole out-lap (pit exit to the
  first start/finish crossing); never a representative flying lap.
* **incomplete** - the lap does not cover most of the track (in-lap, pit entry,
  or a session that ended mid-lap).
* **cold_tyres** - average core temperature stayed below the compound's working
  window: a warm-up lap with no grip.
* **too_short** - a "lap" faster than physically possible for the circuit,
  which means a cut or a telemetry/lap-counter glitch.
* **slow_outlier** - far slower than the driver's own median (spin, traffic,
  big mistake), judged with a robust median + k*MAD threshold.
* **sparse** - too few frames or a large time gap, i.e. a pause or dropped data.
* **invalid** - flagged invalid by an external source (e.g. the lap store's
  track-cut flag), injected via ``invalid_laps``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from statistics import median

from src.ml.recorded_session import TelemetrySample


class DropReason(StrEnum):
    """Why a lap was excluded from the training set."""

    OUT_LAP = "out_lap"
    INCOMPLETE = "incomplete"
    COLD_TYRES = "cold_tyres"
    TOO_SHORT = "too_short"
    SLOW_OUTLIER = "slow_outlier"
    SPARSE = "sparse"
    INVALID = "invalid"


@dataclass(frozen=True)
class LapQualityConfig:
    """Thresholds for lap selection. Defaults suit F1-class slick-tyre cars."""

    tyre_window_low: float = 85.0
    """Average core temp (deg C) below which the lap is a warm-up lap."""
    min_lap_time_s: float = 60.0
    """A full lap faster than this is impossible for the circuit (a cut)."""
    min_lap_pos_span: float = 0.9
    """Fraction of the lap (0..1) that must be covered for it to count."""
    max_frame_gap_s: float = 0.5
    """A gap between consecutive frames larger than this means a pause."""
    min_frames: int = 100
    """Laps with fewer frames than this are too sparse to trust."""
    slow_outlier_k: float = 4.0
    """Drop laps slower than median + k * MAD of the driver's clean laps."""
    min_outlier_sample: int = 5
    """Need at least this many clean laps before judging slow outliers."""


@dataclass(frozen=True)
class LapAssessment:
    """The verdict for a single lap, with the reasons it was dropped (if any)."""

    lap: int
    frames: int
    lap_time_s: float | None
    avg_tyre_temp: float
    lap_pos_span: float
    kept: bool
    reasons: tuple[DropReason, ...]


@dataclass(frozen=True)
class LapQualityReport:
    """Per-lap verdicts plus convenience views over the selection."""

    assessments: tuple[LapAssessment, ...]
    config: LapQualityConfig

    @property
    def trainable_laps(self) -> tuple[int, ...]:
        """Lap indices that passed every guardrail, in ascending order."""
        return tuple(a.lap for a in self.assessments if a.kept)

    @property
    def kept_count(self) -> int:
        """How many laps survived selection."""
        return sum(1 for a in self.assessments if a.kept)

    def dropped(self) -> tuple[LapAssessment, ...]:
        """The laps that were rejected, with their reasons."""
        return tuple(a for a in self.assessments if not a.kept)


@dataclass(frozen=True)
class _LapStats:
    """Intermediate per-lap measurements used to decide quality."""

    lap: int
    frames: int
    lap_time_s: float | None
    avg_tyre_temp: float
    lap_pos_span: float
    max_frame_gap_s: float


def _compute_stats(lap: int, samples: list[TelemetrySample]) -> _LapStats:
    times = [s.timestamp for s in samples]
    positions = [s.lap_pos for s in samples]
    temps = [s.tyre_temp_avg for s in samples]
    lap_time = max(times) - min(times) if len(times) >= 2 else None
    max_gap = 0.0
    ordered = sorted(times)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        max_gap = max(max_gap, later - earlier)
    return _LapStats(
        lap=lap,
        frames=len(samples),
        lap_time_s=lap_time,
        avg_tyre_temp=sum(temps) / len(temps) if temps else 0.0,
        lap_pos_span=(max(positions) - min(positions)) if positions else 0.0,
        max_frame_gap_s=max_gap,
    )


def _slow_threshold(times: list[float], k: float, min_sample: int) -> float | None:
    """Robust upper bound on lap time (median + k*MAD), or ``None`` if too few."""
    if len(times) < min_sample:
        return None
    mid = median(times)
    mad = median([abs(t - mid) for t in times])
    # With near-identical lap times MAD collapses to ~0; fall back to a small
    # relative band so genuine consistency does not flag every lap as an outlier.
    spread = mad if mad > 1e-6 else 0.01 * mid
    return mid + k * spread


def _assess_one(
    stats: _LapStats,
    config: LapQualityConfig,
    invalid_laps: set[int],
    slow_threshold: float | None,
) -> LapAssessment:
    reasons: list[DropReason] = []
    if stats.lap in invalid_laps:
        reasons.append(DropReason.INVALID)
    if stats.lap == 0:
        reasons.append(DropReason.OUT_LAP)
    if stats.frames < config.min_frames or stats.max_frame_gap_s > config.max_frame_gap_s:
        reasons.append(DropReason.SPARSE)
    if stats.lap_pos_span < config.min_lap_pos_span:
        reasons.append(DropReason.INCOMPLETE)
    if stats.lap_time_s is None or stats.lap_time_s < config.min_lap_time_s:
        reasons.append(DropReason.TOO_SHORT)
    if stats.avg_tyre_temp < config.tyre_window_low:
        reasons.append(DropReason.COLD_TYRES)
    if (
        slow_threshold is not None
        and stats.lap_time_s is not None
        and stats.lap_time_s > slow_threshold
    ):
        reasons.append(DropReason.SLOW_OUTLIER)
    return LapAssessment(
        lap=stats.lap,
        frames=stats.frames,
        lap_time_s=stats.lap_time_s,
        avg_tyre_temp=stats.avg_tyre_temp,
        lap_pos_span=stats.lap_pos_span,
        kept=not reasons,
        reasons=tuple(reasons),
    )


def assess_laps(
    samples_by_lap: dict[int, list[TelemetrySample]],
    *,
    config: LapQualityConfig | None = None,
    invalid_laps: set[int] | None = None,
) -> LapQualityReport:
    """Score every lap in a recorded session and select the trainable ones.

    Args:
        samples_by_lap: Samples grouped by lap (see
            :func:`src.ml.recorded_session.group_by_lap`).
        config: Selection thresholds; sensible slick-tyre defaults if omitted.
        invalid_laps: Lap indices known to be invalid from an external source
            (e.g. the lap store's track-cut flag).

    Returns:
        A :class:`LapQualityReport` whose :attr:`~LapQualityReport.trainable_laps`
        lists the laps that passed every guardrail.
    """
    cfg = config or LapQualityConfig()
    invalid = invalid_laps or set()
    stats = [_compute_stats(lap, samples_by_lap[lap]) for lap in sorted(samples_by_lap)]

    # Judge slow outliers only against structurally-clean laps, so a single
    # disaster lap cannot drag the threshold and hide other bad laps.
    clean_times = [
        st.lap_time_s
        for st in stats
        if st.lap_time_s is not None
        and st.lap != 0
        and st.lap_pos_span >= cfg.min_lap_pos_span
        and st.lap_time_s >= cfg.min_lap_time_s
    ]
    slow_threshold = _slow_threshold(clean_times, cfg.slow_outlier_k, cfg.min_outlier_sample)

    assessments = tuple(
        _assess_one(st, cfg, invalid, slow_threshold) for st in stats
    )
    return LapQualityReport(assessments=assessments, config=cfg)
