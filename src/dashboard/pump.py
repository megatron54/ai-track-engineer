"""Capture orchestration: drive a session and broadcast its events.

``run_session`` is the tested glue between a telemetry source and the dashboard:
it streams frames from an already-connected source, runs the analysis pipeline,
and publishes ``session`` / ``telemetry`` / ``lap`` envelopes to the hub. It owns
closing the source.
"""

from __future__ import annotations

import asyncio

from src.ai.advisor import RaceEngineerAdvisor
from src.analysis.engine_monitor import EngineMonitor
from src.analysis.pipeline import AnalysisPipeline, LapReport
from src.dashboard.hub import TelemetryHub
from src.dashboard.serialization import lap_event, session_event, telemetry_event
from src.dashboard.state import DashboardState
from src.knowledge.models import TrackInfo
from src.storage.sqlite_client import SqliteStore
from src.telemetry.models import ACStaticInfo
from src.telemetry.source import TelemetrySource


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
    max_frames: int | None = None,
    telemetry_every: int = 1,
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

    Returns:
        The number of frames processed.
    """
    if telemetry_every < 1:
        raise ValueError("telemetry_every must be >= 1")

    pipeline = AnalysisPipeline(track, engine_monitor=engine_monitor)
    state.set_session(session_event(track, car=static.car_model))
    if state.session is not None:
        hub.publish(state.session)

    advice_tasks: set[asyncio.Task[None]] = set()
    frames = 0
    try:
        async for frame in source.stream(hz, max_frames=max_frames, on_error="skip"):
            report = pipeline.process(frame)
            frames += 1
            if frames % telemetry_every == 0:
                hub.publish(telemetry_event(frame, delta=pipeline.live_delta(frame)))
            if report is not None:
                hub.publish(lap_event(report))
                if store is not None and session_id is not None:
                    await store.record_lap(session_id, report.lap)
                if advisor is not None:
                    task = asyncio.create_task(_publish_ai_advice(advisor, report, track, hub))
                    advice_tasks.add(task)
                    task.add_done_callback(advice_tasks.discard)
        # Let any in-flight advice finish on normal completion (e.g. tests).
        if advice_tasks:
            await asyncio.gather(*advice_tasks, return_exceptions=True)
    finally:
        for task in advice_tasks:
            if not task.done():
                task.cancel()
        source.close()
    return frames

