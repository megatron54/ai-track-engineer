"""Build a compact, token-efficient context block for the LLM.

Turning a lap and its analysis into a tight textual summary is the key to good,
cheap recommendations: the model should receive exactly the signals an engineer
would look at (lap time, biggest time losses by corner, *why* each one was
lost - brake point, throttle point, steering corrections - tyre state, and
engine alerts) and nothing else.
"""

from __future__ import annotations

from src.analysis.engine_monitor import EngineAlert
from src.analysis.input_analyzer import CornerInputDelta, format_input_detail
from src.analysis.models import CornerDelta
from src.analysis.tyre_model import TyreThermalReport
from src.knowledge.models import TrackInfo
from src.processing.models import Lap


def build_lap_context(
    *,
    lap: Lap,
    track: TrackInfo,
    corner_losses: list[CornerDelta] | None = None,
    input_deltas: list[CornerInputDelta] | None = None,
    tyre_report: TyreThermalReport | None = None,
    engine_alerts: list[EngineAlert] | None = None,
    corner_trends: dict[str, str] | None = None,
) -> str:
    """Compose a structured text summary of a lap for the LLM."""
    lines: list[str] = []
    lines.append(f"Track: {track.name} ({track.corner_count} corners)")
    lines.append(
        f"Lap {lap.lap_number}: {lap.lap_time_seconds:.3f}s "
        f"({'valid' if lap.valid else 'INVALID'})"
    )
    if lap.sector_times_ms:
        sectors = ", ".join(
            f"S{i + 1} {ms / 1000:.3f}s" for i, ms in enumerate(lap.sector_times_ms)
        )
        lines.append(f"Sectors: {sectors}")

    if corner_losses:
        lines.append("Biggest time losses vs reference:")
        input_by_corner = {delta.corner_index: delta for delta in input_deltas or []}
        for loss in corner_losses:
            line = f"  - {loss.corner_name}: +{loss.delta_s:.3f}s"
            detail_delta = input_by_corner.get(loss.corner_index)
            if detail_delta is not None and track.length_m > 0:
                detail = format_input_detail(detail_delta, track.length_m)
                if detail:
                    line += f" ({detail})"
            trend = (corner_trends or {}).get(loss.corner_name)
            if trend:
                line += f" [{trend}]"
            lines.append(line)
    else:
        lines.append("No reference lap yet (need more laps for corner deltas).")

    if tyre_report is not None:
        statuses = "/".join(status.value for status in tyre_report.statuses)
        lines.append(
            f"Tyres [FL/FR/RL/RR]: {statuses}; "
            f"front-rear balance {tyre_report.front_rear_delta:+.1f}C"
        )

    if engine_alerts:
        alerts = ", ".join(f"{alert.kind}@{alert.rpm}rpm" for alert in engine_alerts)
        lines.append(f"Engine alerts: {alerts}")

    return "\n".join(lines)
