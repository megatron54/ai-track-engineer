"""Application entry point and command-line interface.

Phase 0 provides the CLI skeleton and an environment ``doctor`` command. The
real-time telemetry orchestration is wired in from Phase 1 onwards.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import typer
from fastapi import FastAPI

from src import __version__
from src.ai import OllamaClient, RaceEngineerAdvisor
from src.analysis import EngineMonitor
from src.config import find_ac_install, get_settings
from src.dashboard import DashboardState, TelemetryHub, create_app, run_session
from src.knowledge import TrackInfo, load_track, map_png_path
from src.observability import configure_logging, get_logger
from src.storage import SqliteStore
from src.storage.session_recorder import SessionRecorder
from src.telemetry import (
    MockTelemetrySource,
    SharedMemoryTelemetrySource,
    TelemetrySource,
)
from src.telemetry.models import ACStaticInfo
from src.telemetry.opponents import OpponentReceiver
from src.telemetry.shm_reader import SharedMemoryUnavailableError

app = typer.Typer(
    name="ai-track-engineer",
    help="AI-powered race engineer for Assetto Corsa.",
    add_completion=False,
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed version and exit."""
    typer.echo(f"ai-track-engineer {__version__}")


@app.command()
def report() -> None:
    """Print a summary of the most recent recorded session."""
    settings = get_settings()
    configure_logging(settings.app.log_level)
    asyncio.run(_print_latest_report(settings.app.database_path))


async def _print_latest_report(database_path: str) -> None:  # pragma: no cover - integration
    """Load the latest session from SQLite and print its report."""
    from src.analysis import build_session_report

    async with SqliteStore(database_path) as store:
        session = await store.latest_session()
        if session is None:
            typer.echo("No recorded sessions found.")
            return
        laps = await store.laps_for_session(session.id)
    summary = build_session_report(laps)
    typer.echo(f"Session on {session.track} ({session.car})")
    typer.echo(f"  Laps: {summary.valid_laps} valid / {summary.total_laps} total")
    if summary.best_lap_seconds is not None:
        typer.echo(f"  Best lap: {summary.best_lap_seconds:.3f}s")
    if summary.average_lap_ms is not None:
        typer.echo(f"  Average: {summary.average_lap_ms / 1000:.3f}s")
    if summary.consistency_stdev_ms is not None:
        typer.echo(f"  Consistency (stdev): {summary.consistency_stdev_ms / 1000:.3f}s")
    if summary.theoretical_best_ms is not None:
        typer.echo(f"  Theoretical best: {summary.theoretical_best_ms / 1000:.3f}s")


@app.command()
def doctor() -> None:
    """Check the local environment (settings, Assetto Corsa, services)."""
    settings = get_settings()
    configure_logging(settings.app.log_level)
    log = get_logger("doctor")

    ac_path = find_ac_install(settings.app.ac_install_path)
    log.info(
        "environment-check",
        version=__version__,
        ac_install="found" if ac_path else "not-found",
        ac_path=str(ac_path) if ac_path else None,
        influx_url=settings.influxdb.url,
        ollama_url=settings.ollama.url,
        ollama_model=settings.ollama.model,
    )
    if ac_path is None:
        typer.echo(
            "Assetto Corsa installation not found. Set AC_INSTALL_PATH in .env "
            "to point at your installation."
        )


@app.command()
def run(
    mock: bool = typer.Option(
        False, "--mock", help="Use simulated telemetry instead of a live session."
    ),
    voice: bool = typer.Option(
        False, "--voice", help="Enable the bidirectional voice assistant."
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Dashboard bind address."),
    port: int = typer.Option(8000, "--port", help="Dashboard port."),
) -> None:
    """Start the engineer: capture telemetry and serve the live dashboard.

    Connects a telemetry source (live or ``--mock``), fans frames out to the web
    dashboard, and segments laps. Open http://HOST:PORT to view live telemetry.
    Press Ctrl+C to stop.
    """
    settings = get_settings()
    configure_logging(settings.app.log_level)
    log = get_logger("run")

    if voice:
        log.warning("voice-not-implemented", note="voice arrives in Phase 6")

    source: TelemetrySource = (
        MockTelemetrySource() if mock else SharedMemoryTelemetrySource()
    )
    hub = TelemetryHub()
    state = DashboardState()

    async def producer() -> None:
        await _capture_and_analyze(source, hub, state, hz=settings.app.telemetry_poll_hz)

    app_instance = create_app(hub, state, producer=producer)
    log.info(
        "startup",
        mode="mock" if mock else "live",
        dashboard=f"http://{host}:{port}",
        poll_hz=settings.app.telemetry_poll_hz,
    )
    _serve(app_instance, host=host, port=port, log_level=settings.app.log_level)


def _serve(  # pragma: no cover - integration entry point
    app_instance: FastAPI, *, host: str, port: int, log_level: str
) -> None:
    """Run the ASGI app with uvicorn (integration entry point)."""
    import uvicorn

    uvicorn.run(app_instance, host=host, port=port, log_level=log_level.lower())


def _track_dir_for(static: ACStaticInfo) -> Path | None:  # pragma: no cover - integration
    """Resolve the Assetto Corsa content directory for the active track."""
    settings = get_settings()
    ac_path = find_ac_install(settings.app.ac_install_path)
    if ac_path is not None and static.track:
        track_dir = Path(ac_path) / "content" / "tracks" / static.track
        if track_dir.is_dir():
            return track_dir
    return None


def _load_track_info(static: ACStaticInfo) -> TrackInfo:  # pragma: no cover - integration
    """Load track knowledge for the active session, with a safe fallback."""
    track_dir = _track_dir_for(static)
    if track_dir is not None:
        return load_track(track_dir, layout=static.track_configuration or "")
    label = static.track or "unknown"
    return TrackInfo(track_id=label, name=label)


async def _connect_when_ready(  # pragma: no cover - integration entry point
    source: TelemetrySource, *, poll_seconds: float = 2.0
) -> ACStaticInfo:
    """Connect to *source*, waiting for Assetto Corsa if it is not ready yet.

    The live shared-memory source raises :class:`SharedMemoryUnavailableError`
    until AC has created its regions, so we poll instead of failing. This lets
    the operator start the dashboard before or after launching the game, and it
    never pre-creates the shared-memory regions (which would crash AC).
    """
    log = get_logger("analysis")
    waiting = False
    while True:
        try:
            return source.connect()
        except SharedMemoryUnavailableError:
            if not waiting:
                log.info(
                    "waiting-for-ac",
                    note="start Assetto Corsa and enter a session to begin",
                )
                waiting = True
            await asyncio.sleep(poll_seconds)


async def _capture_and_analyze(  # pragma: no cover - integration entry point
    source: TelemetrySource,
    hub: TelemetryHub,
    state: DashboardState,
    *,
    hz: int,
) -> None:
    """Connect, load track + map, and stream the session's events to the hub."""
    static = await _connect_when_ready(source)
    track = _load_track_info(static)
    track_dir = _track_dir_for(static)
    if track_dir is not None:
        state.set_map_png(map_png_path(track_dir, layout=static.track_configuration or ""))
    engine_monitor = EngineMonitor(static.max_rpm) if static.max_rpm > 0 else None
    settings = get_settings()
    advisor = RaceEngineerAdvisor(OllamaClient.from_settings(settings.ollama))
    log = get_logger("analysis")

    db_path = Path(settings.app.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with SqliteStore(str(db_path)) as store:
        session = await store.create_session(
            track=track.track_id,
            car=static.car_model,
            started_at=time.time(),
            track_config=static.track_configuration or "",
        )
        log.info(
            "session",
            track=track.name,
            car=static.car_model,
            corners=track.corner_count,
            ai_model=settings.ollama.model,
            session_id=session.id,
        )
        best_ever_ms = await store.best_lap_ms_for(
            track=track.track_id, car=static.car_model
        )
        sessions_dir = Path("data/sessions")
        recorder = SessionRecorder(
            sessions_dir, track.track_id, static.car_model, session.id
        )
        with recorder:
            log.info("recording-telemetry", path=str(recorder.path))
            receiver = OpponentReceiver()
            opponents: OpponentReceiver | None
            try:
                await receiver.start()
                log.info(
                    "opponent-bridge-listening",
                    host=receiver.host,
                    port=receiver.port,
                )
                opponents = receiver
            except OSError as exc:
                log.warning("opponent-bridge-unavailable", error=str(exc))
                opponents = None
            try:
                await run_session(
                    source,
                    hub,
                    state,
                    track,
                    static,
                    hz=hz,
                    advisor=advisor,
                    engine_monitor=engine_monitor,
                    store=store,
                    session_id=session.id,
                    recorder=recorder,
                    best_ever_ms=best_ever_ms,
                    opponents=opponents,
                )
            finally:
                if opponents is not None:
                    opponents.close()
            log.info("recording-complete", rows=recorder.rows_written)


if __name__ == "__main__":  # pragma: no cover
    app()
