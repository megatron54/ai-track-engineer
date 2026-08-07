"""The race engineer advisor: turn lap analysis into recommendations.

The advisor always has a deterministic heuristic path (the "cold start"
behaviour: useful from lap one, no model required). When a local LLM is
configured it is used for richer, natural-language coaching, with the heuristic
as a transparent fallback if the model errors out.
"""

from __future__ import annotations

import structlog

from src.ai.context_builder import build_lap_context, build_question_context
from src.ai.llm import LLMClient
from src.ai.models import SYSTEM_PROMPT, VOICE_SYSTEM_PROMPT, Priority, Recommendation
from src.analysis.engine_monitor import AlertSeverity, EngineAlert
from src.analysis.input_analyzer import CornerInputDelta, format_input_detail
from src.analysis.models import CornerDelta
from src.analysis.tyre_model import TyreThermalReport
from src.knowledge.models import TrackInfo
from src.processing.models import Lap

_log = structlog.get_logger("ai.advisor")

# A corner's delta must move by more than this (seconds) between laps to be
# called "improving"/"regressing" - smaller swings are noise, not a trend.
_TREND_EPSILON_S = 0.02


class RaceEngineerAdvisor:
    """Produce driver recommendations from lap analysis.

    Keeps a short session memory (the last delta seen per corner) so advice
    can note *progress* rather than repeating the same static observation lap
    after lap - e.g. "still losing 0.10s (improving, was +0.30s)" instead of
    just restating the current number every time.
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm
        self._last_corner_delta_s: dict[str, float] = {}

    def _corner_trends(self, corner_losses: list[CornerDelta] | None) -> dict[str, str]:
        """Compare this lap's corner deltas against the last lap's, per corner."""
        trends: dict[str, str] = {}
        for loss in corner_losses or []:
            previous = self._last_corner_delta_s.get(loss.corner_name)
            if previous is None:
                continue
            if loss.delta_s < previous - _TREND_EPSILON_S:
                trends[loss.corner_name] = f"improving, was +{previous:.2f}s"
            elif loss.delta_s > previous + _TREND_EPSILON_S:
                trends[loss.corner_name] = f"regressing, was +{previous:.2f}s"
        return trends

    def _remember(self, corner_losses: list[CornerDelta] | None) -> None:
        # Note: entries are never evicted, so a corner that drops out of the
        # top-3 losses for many laps and later reappears is compared against
        # a stale delta. Bounded by the track's corner count (never grows
        # unbounded), and a slightly stale trend is a minor cosmetic risk, not
        # a correctness one - acceptable for now.
        for loss in corner_losses or []:
            self._last_corner_delta_s[loss.corner_name] = loss.delta_s

    def heuristic_advice(
        self,
        *,
        corner_losses: list[CornerDelta] | None = None,
        input_deltas: list[CornerInputDelta] | None = None,
        track_length_m: float = 0.0,
        tyre_report: TyreThermalReport | None = None,
        engine_alerts: list[EngineAlert] | None = None,
        corner_trends: dict[str, str] | None = None,
    ) -> list[Recommendation]:
        """Deterministic recommendations derived directly from the analysis."""
        recommendations: list[Recommendation] = []

        for alert in engine_alerts or []:
            if alert.severity is AlertSeverity.CRITICAL:
                recommendations.append(
                    Recommendation(priority=Priority.CRITICAL, message=alert.message)
                )

        if tyre_report is not None and tyre_report.overheating:
            recommendations.append(
                Recommendation(
                    priority=Priority.HIGH,
                    message=(
                        "Tyres overheating - ease entry aggression and avoid sustained "
                        "slip to bring temperatures back into the window."
                    ),
                )
            )

        input_by_corner = {delta.corner_index: delta for delta in input_deltas or []}
        for index, loss in enumerate(corner_losses or []):
            priority = Priority.HIGH if index == 0 else Priority.NORMAL
            prefix = (
                f"[{loss.corner_name}] Losing {loss.delta_s:.2f}s vs your reference"
            )
            detail_delta = input_by_corner.get(loss.corner_index)
            detail = (
                format_input_detail(detail_delta, track_length_m)
                if detail_delta is not None and track_length_m > 0
                else None
            )
            message = (
                f"{prefix} - {detail}."
                if detail
                else f"{prefix} - focus your braking and apex here."
            )
            trend = (corner_trends or {}).get(loss.corner_name)
            if trend:
                message += f" ({trend})"
            recommendations.append(
                Recommendation(priority=priority, corner=loss.corner_name, message=message)
            )

        return recommendations

    async def llm_advice(self, context_text: str) -> list[Recommendation]:
        """Ask the configured LLM for advice, one recommendation per line."""
        if self._llm is None:
            raise RuntimeError("no LLM configured")
        reply = await self._llm.complete(SYSTEM_PROMPT, context_text)
        return [
            Recommendation(priority=Priority.NORMAL, message=line.strip())
            for line in reply.splitlines()
            if line.strip()
        ]

    async def advise(
        self,
        *,
        lap: Lap,
        track: TrackInfo,
        corner_losses: list[CornerDelta] | None = None,
        input_deltas: list[CornerInputDelta] | None = None,
        tyre_report: TyreThermalReport | None = None,
        engine_alerts: list[EngineAlert] | None = None,
    ) -> list[Recommendation]:
        """Return recommendations, preferring the LLM and falling back cleanly."""
        trends = self._corner_trends(corner_losses)
        if self._llm is not None:
            context = build_lap_context(
                lap=lap,
                track=track,
                corner_losses=corner_losses,
                input_deltas=input_deltas,
                tyre_report=tyre_report,
                engine_alerts=engine_alerts,
                corner_trends=trends,
            )
            try:
                advice = await self.llm_advice(context)
                if advice:
                    self._remember(corner_losses)
                    return advice
            except Exception:  # noqa: BLE001 - any LLM failure falls back to heuristics
                _log.warning("llm-advice-failed", action="fallback-to-heuristic", exc_info=True)

        result = self.heuristic_advice(
            corner_losses=corner_losses,
            input_deltas=input_deltas,
            track_length_m=track.length_m,
            tyre_report=tyre_report,
            engine_alerts=engine_alerts,
            corner_trends=trends,
        )
        self._remember(corner_losses)
        return result

    async def answer_question(
        self,
        question: str,
        *,
        track: TrackInfo,
        lap: Lap | None = None,
        corner_losses: list[CornerDelta] | None = None,
        input_deltas: list[CornerInputDelta] | None = None,
        tyre_report: TyreThermalReport | None = None,
        engine_alerts: list[EngineAlert] | None = None,
    ) -> str:
        """Answer a driver's spoken (transcribed) question in one short reply.

        Used by the voice assistant (:mod:`src.voice`): reuses this same local
        LLM integration rather than a second model, with the same heuristic
        fallback discipline as :meth:`advise`. Returns plain text meant to be
        read aloud by TTS - no corner-tag formatting, no lists.

        Does not update the per-corner trend memory (:meth:`_remember`) -
        that happens exactly once per lap, in :meth:`advise`, to avoid a
        question asked mid-lap skewing the next lap's improving/regressing
        comparison.
        """
        trends = self._corner_trends(corner_losses)
        if self._llm is not None:
            context = build_question_context(
                question,
                track=track,
                lap=lap,
                corner_losses=corner_losses,
                input_deltas=input_deltas,
                tyre_report=tyre_report,
                engine_alerts=engine_alerts,
                corner_trends=trends,
            )
            try:
                reply = await self._llm.complete(VOICE_SYSTEM_PROMPT, context)
                if reply.strip():
                    return reply.strip()
            except Exception:  # noqa: BLE001 - any LLM failure falls back to heuristics
                _log.warning(
                    "voice-llm-failed", action="fallback-to-heuristic", exc_info=True
                )

        return self._heuristic_answer(
            corner_losses=corner_losses,
            input_deltas=input_deltas,
            track_length_m=track.length_m,
            tyre_report=tyre_report,
            engine_alerts=engine_alerts,
            corner_trends=trends,
        )

    def _heuristic_answer(
        self,
        *,
        corner_losses: list[CornerDelta] | None,
        input_deltas: list[CornerInputDelta] | None,
        track_length_m: float,
        tyre_report: TyreThermalReport | None,
        engine_alerts: list[EngineAlert] | None,
        corner_trends: dict[str, str] | None,
    ) -> str:
        """Deterministic spoken-style fallback when no LLM is available/working."""
        recommendations = self.heuristic_advice(
            corner_losses=corner_losses,
            input_deltas=input_deltas,
            track_length_m=track_length_m,
            tyre_report=tyre_report,
            engine_alerts=engine_alerts,
            corner_trends=corner_trends,
        )
        if not recommendations:
            return "Not enough data yet - complete a few more laps and ask again."
        # Speak the single highest-priority item; a list read aloud is unusable.
        return recommendations[0].message
