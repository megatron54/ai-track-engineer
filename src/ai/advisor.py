"""The race engineer advisor: turn lap analysis into recommendations.

The advisor always has a deterministic heuristic path (the "cold start"
behaviour: useful from lap one, no model required). When a local LLM is
configured it is used for richer, natural-language coaching, with the heuristic
as a transparent fallback if the model errors out.
"""

from __future__ import annotations

import structlog

from src.ai.context_builder import build_lap_context
from src.ai.llm import LLMClient
from src.ai.models import SYSTEM_PROMPT, Priority, Recommendation
from src.analysis.engine_monitor import AlertSeverity, EngineAlert
from src.analysis.models import CornerDelta
from src.analysis.tyre_model import TyreThermalReport
from src.knowledge.models import TrackInfo
from src.processing.models import Lap

_log = structlog.get_logger("ai.advisor")


class RaceEngineerAdvisor:
    """Produce driver recommendations from lap analysis."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm

    def heuristic_advice(
        self,
        *,
        corner_losses: list[CornerDelta] | None = None,
        tyre_report: TyreThermalReport | None = None,
        engine_alerts: list[EngineAlert] | None = None,
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

        for index, loss in enumerate(corner_losses or []):
            priority = Priority.HIGH if index == 0 else Priority.NORMAL
            recommendations.append(
                Recommendation(
                    priority=priority,
                    corner=loss.corner_name,
                    message=(
                        f"[{loss.corner_name}] Losing {loss.delta_s:.2f}s vs your reference - "
                        "focus your braking and apex here."
                    ),
                )
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
        tyre_report: TyreThermalReport | None = None,
        engine_alerts: list[EngineAlert] | None = None,
    ) -> list[Recommendation]:
        """Return recommendations, preferring the LLM and falling back cleanly."""
        if self._llm is not None:
            context = build_lap_context(
                lap=lap,
                track=track,
                corner_losses=corner_losses,
                tyre_report=tyre_report,
                engine_alerts=engine_alerts,
            )
            try:
                advice = await self.llm_advice(context)
                if advice:
                    return advice
            except Exception:  # noqa: BLE001 - any LLM failure falls back to heuristics
                _log.warning("llm-advice-failed", action="fallback-to-heuristic", exc_info=True)

        return self.heuristic_advice(
            corner_losses=corner_losses,
            tyre_report=tyre_report,
            engine_alerts=engine_alerts,
        )
