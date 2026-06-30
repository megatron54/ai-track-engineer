"""Capture orchestration: drive a session and broadcast its events.

``run_session`` is the tested glue between a telemetry source and the dashboard:
it streams frames from an already-connected source, runs the analysis pipeline,
and publishes ``session`` / ``telemetry`` / ``lap`` envelopes to the hub. It owns
closing the source.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.ai.advisor import RaceEngineerAdvisor
from src.analysis.engine_monitor import EngineMonitor
from src.analysis.pipeline import AnalysisPipeline, LapReport
from src.dashboard.hub import TelemetryHub
from src.dashboard.serialization import gap_event, lap_event, session_event, telemetry_event
from src.dashboard.state import DashboardState
from src.knowledge.models import TrackInfo
from src.processing.corner_coach import CornerCoach
from src.processing.message_queue import MessagePriority, MessageQueue, PriorityMessage
from src.storage.session_recorder import SessionRecorder
from src.storage.sqlite_client import SqliteStore
from src.strategy.fuel_strategy import FuelStrategy
from src.strategy.gap_manager import GapManager
from src.strategy.mode_manager import ModeProfile, mode_from_session, profile_for
from src.strategy.pit_strategy import pit_recommendation
from src.strategy.session_detector import SessionModeTracker
from src.strategy.tyre_strategy import TyreStrategy
from src.telemetry.models import ACStaticInfo
from src.telemetry.opponents import OpponentReceiver, gaps_seconds
from src.telemetry.shm_structs import ACSessionType
from src.telemetry.source import SessionChangedError, TelemetrySource


def _mode_event(session_type: ACSessionType) -> dict[str, Any]:
    """Build a ``mode`` envelope describing the active engineer personality."""
    profile = profile_for(mode_from_session(session_type))
    return {
        "type": "mode",
        "mode": profile.mode.value,
        "priority": profile.priority,
        "personality": profile.personality,
        "max_messages_per_lap": profile.max_messages_per_lap,
    }


def _should_deliver(
    profile: ModeProfile, message: PriorityMessage, sent_this_lap: int
) -> bool:
    """Whether a coaching message fits the session mode's budget.

    Caps messages per lap and, when the mode asks for hotlap silence (qualifying),
    lets only high-urgency (CRITICAL/HIGH) messages through.
    """
    if sent_this_lap >= profile.max_messages_per_lap:
        return False
    return not (profile.silence_during_hotlap and message.priority > MessagePriority.HIGH)


async def _publish_ai_advice(
    advisor: RaceEngineerAdvisor, report: LapReport, track: TrackInfo, hub: TelemetryHub
) -> None:
    """Ask the advisor (LLM with heuristic fallback) and publish an advice event."""
    advice = await advisor.advise(
        lap=report.lap,
        track=track,
        corner_losses=list(report.corner_losses),
        tyre_report=report.tyre_report,
        engine_alerts=list(report.engine_alerts),
    )
    hub.publish(
        {
            "type": "advice",
            "lap": report.lap.lap_number,
            "messages": [rec.message for rec in advice],
        }
    )


async def run_session(
    source: TelemetrySource,
    hub: TelemetryHub,
    state: DashboardState,
    track: TrackInfo,
    static: ACStaticInfo,
    *,
    hz: int,
    advisor: RaceEngineerAdvisor | None = None,
    engine_monitor: EngineMonitor | None = None,
    store: SqliteStore | None = None,
    session_id: str | None = None,
    recorder: SessionRecorder | None = None,
    max_frames: int | None = None,
    telemetry_every: int = 1,
    best_ever_ms: int | None = None,
    opponents: OpponentReceiver | None = None,
    gap_every: int = 30,
    static_check_every: int = 0,
) -> int:
    """Stream a connected session, broadcasting analysis events to the hub.

    Args:
        source: An **already-connected** telemetry source (this function closes it).
        hub: The dashboard fan-out hub.
        state: Shared dashboard state to update with the session envelope.
        track: Loaded track knowledge for the session.
        static: Static info from the source connection.
        hz: Capture rate.
        advisor: Optional AI advisor. When provided, each completed lap spawns a
            non-blocking task that publishes an ``advice`` event (LLM coaching
            with heuristic fallback) without stalling the telemetry stream.
        engine_monitor: Optional engine monitor for over-rev alerts.
        store: Optional SQLite store; completed laps are persisted to it.
        session_id: Session id under which laps are recorded (with ``store``).
        max_frames: Optional cap (mainly for tests).
        telemetry_every: Publish a telemetry event every Nth frame (throttling).
        opponents: Optional opponent UDP receiver. When provided, gaps to the
            cars ahead and behind are published as ``gap`` events.
        gap_every: Sample gaps (and emit a ``gap`` event) every Nth frame. The
            default (~0.5s at 60Hz) keeps the trend window meaningful instead of
            reacting to single-frame jitter.
        static_check_every: Re-read the static page every Nth frame to detect a
            mid-stream car/track change; ``0`` disables it. On a change,
            :class:`SessionChangedError` is raised (the source is left open).

    Returns:
        The number of frames processed.
    """
    if telemetry_every < 1:
        raise ValueError("telemetry_every must be >= 1")
    if gap_every < 1:
        raise ValueError("gap_every must be >= 1")

    pipeline = AnalysisPipeline(track, engine_monitor=engine_monitor)
    state.set_session(session_event(track, car=static.car_model, best_ever_ms=best_ever_ms))
    if state.session is not None:
        hub.publish(state.session)

    # Strategy + real-time coaching (initialised here, not injected, to keep
    # the function signature stable; tests verify components individually).
    fuel = FuelStrategy()
    tyres = TyreStrategy()
    coach = CornerCoach(track)
    msg_queue = MessageQueue(cooldown_s=6.0)
    gap_manager = GapManager()

    # Engineer mode: Practice/Qualify/Race personality + per-lap message budget.
    mode_tracker = SessionModeTracker()
    messages_this_lap = 0
    last_message_lap = -1

    advice_tasks: set[asyncio.Task[None]] = set()
    keep_source_open = False
    frames = 0
    try:
        async for frame in source.stream(hz, max_frames=max_frames, on_error="skip"):
            report = pipeline.process(frame)
            delta = pipeline.live_delta(frame)
            frames += 1

            # Detect a mid-stream session change (driver swapped car/track in AC)
            # and stop so the caller can rebuild the session. Leave the source open.
            if static_check_every and frames % static_check_every == 0:
                fresh = source.read_static()
                if (fresh.track, fresh.track_configuration, fresh.car_model) != (
                    static.track, static.track_configuration, static.car_model
                ):
                    keep_source_open = True
                    raise SessionChangedError(fresh)

            # Engineer mode: publish on change, reset the per-lap budget on a
            # new lap, and adapt how many coaching messages get through.
            if mode_tracker.update(frame.graphics) is not None:
                mode_evt = _mode_event(frame.graphics.session_type)
                hub.publish(mode_evt)
                state.remember(mode_evt)
            profile = profile_for(mode_from_session(frame.graphics.session_type))
            if frame.graphics.completed_laps != last_message_lap:
                last_message_lap = frame.graphics.completed_laps
                messages_this_lap = 0

            # Corner coach: post-corner + brake warnings.
            if pipeline.has_reference_lap:
                coach_msgs = coach.process(
                    frame.graphics.normalized_car_position,
                    frame.physics.speed_kmh,
                    frame.graphics.current_time_ms / 1000.0,
                    frame.timestamp,
                )
                for msg in coach_msgs:
                    msg_queue.push(msg)

            # Drain the priority queue and publish coaching within the mode budget.
            delivered = msg_queue.pop(now=frame.timestamp)
            if delivered is not None and _should_deliver(profile, delivered, messages_this_lap):
                hub.publish({
                    "type": "coaching",
                    "priority": delivered.priority.name,
                    "text": delivered.text,
                    "corner": delivered.corner,
                })
                messages_this_lap += 1

            if frames % telemetry_every == 0:
                hub.publish(telemetry_event(frame, delta=delta))
            if opponents is not None and frames % gap_every == 0:
                snapshot = opponents.latest()
                if snapshot is not None:
                    ahead_s, behind_s = gaps_seconds(snapshot, static.track_spline_length)
                    gap_manager.update(gap_ahead_s=ahead_s, gap_behind_s=behind_s)
                    gap_evt = gap_event(gap_manager.report())
                    hub.publish(gap_evt)
                    state.remember(gap_evt)
            if recorder is not None:
                recorder.write(frame, delta=delta)
            if report is not None:
                lap_evt = lap_event(report)
                hub.publish(lap_evt)
                state.remember(lap_evt)

                # Per-lap strategy updates.
                fuel.record_lap_fuel(frame.physics.fuel)
                wear = frame.physics.tyre_wear
                tyres.record_wear(sum(wear.as_tuple()) / 4.0)
                fuel_report = fuel.report()
                tyre_report = tyres.report()
                pit = pit_recommendation(
                    current_lap=report.lap.lap_number,
                    fuel=fuel_report,
                    tyres=tyre_report,
                )
                strategy_evt = {
                    "type": "strategy",
                    "lap": report.lap.lap_number,
                    "fuel": {
                        "remaining": fuel_report.fuel_remaining,
                        "per_lap": fuel_report.consumption_per_lap,
                        "laps_left": fuel_report.laps_remaining,
                        "status": fuel_report.status.value,
                        "message": fuel_report.message,
                    },
                    "tyres": {
                        "wear_pct": tyre_report.avg_wear_pct,
                        "rate": tyre_report.wear_rate_per_lap,
                        "advice": tyre_report.advice.value,
                        "message": tyre_report.message,
                    },
                    "pit": {
                        "advice": pit.advice.value,
                        "trigger": pit.trigger,
                        "lap": pit.recommended_lap,
                        "message": pit.message,
                    },
                }
                hub.publish(strategy_evt)
                state.remember(strategy_evt)

                # Update corner coach reference on new PB.
                if report.is_personal_best and pipeline._best_trace is not None:  # noqa: SLF001
                    coach.set_reference(pipeline._best_trace)  # noqa: SLF001

                if store is not None and session_id is not None:
                    await store.record_lap(session_id, report.lap)
                if advisor is not None:
                    task = asyncio.create_task(
                        _publish_ai_advice(advisor, report, track, hub)
                    )
                    advice_tasks.add(task)
                    task.add_done_callback(advice_tasks.discard)
        # Let any in-flight advice finish on normal completion (e.g. tests).
        if advice_tasks:
            await asyncio.gather(*advice_tasks, return_exceptions=True)
    finally:
        for task in advice_tasks:
            if not task.done():
                task.cancel()
        if not keep_source_open:
            source.close()
    return frames

