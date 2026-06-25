"""Application entry point and command-line interface.

Phase 0 provides the CLI skeleton and an environment ``doctor`` command. The
real-time telemetry orchestration is wired in from Phase 1 onwards.
"""

from __future__ import annotations

import typer
from fastapi import FastAPI

from src import __version__
from src.analysis import EngineMonitor
from src.analysis.pipeline import AnalysisPipeline
from src.config import find_ac_install, get_settings
from src.dashboard import TelemetryHub, create_app
from src.knowledge import TrackInfo, load_track
from src.observability import configure_logging, get_logger
from src.telemetry import (
    MockTelemetrySource,
    SharedMemoryTelemetrySource,
    TelemetrySource,
)
from src.telemetry.models import ACStaticInfo

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
    lap_log = get_logger("analysis")

    async def producer() -> None:
        await _capture_and_analyze(source, hub, hz=settings.app.telemetry_poll_hz, log=lap_log)

    app_instance = create_app(hub, producer=producer)
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


def _load_track_info(static: ACStaticInfo) -> TrackInfo:  # pragma: no cover - integration
    """Load track knowledge for the active session, with a safe fallback."""
    from pathlib import Path

    settings = get_settings()
    ac_path = find_ac_install(settings.app.ac_install_path)
    if ac_path is not None and static.track:
        track_dir = Path(ac_path) / "content" / "tracks" / static.track
        if track_dir.is_dir():
            return load_track(track_dir, layout=static.track_configuration or "")
    label = static.track or "unknown"
    return TrackInfo(track_id=label, name=label)


async def _capture_and_analyze(  # pragma: no cover - integration entry point
    source: TelemetrySource,
    hub: TelemetryHub,
    *,
    hz: int,
    log: object,
) -> None:
    """Stream telemetry, fan it out, and run the per-lap analysis pipeline."""
    static = source.connect()
    track = _load_track_info(static)
    engine_monitor = EngineMonitor(static.max_rpm) if static.max_rpm > 0 else None
    pipeline = AnalysisPipeline(track, engine_monitor=engine_monitor)
    bound_log = get_logger("analysis")
    bound_log.info("session", track=track.name, car=static.car_model, corners=track.corner_count)
    try:
        async for frame in source.stream(hz, on_error="skip"):
            hub.publish(frame)
            report = pipeline.process(frame)
            if report is not None:
                bound_log.info(
                    "lap-report",
                    lap=report.lap.lap_number,
                    time_ms=report.lap.lap_time_ms,
                    personal_best=report.is_personal_best,
                    advice=[rec.message for rec in report.recommendations][:3],
                )
    finally:
        source.close()


if __name__ == "__main__":  # pragma: no cover
    app()
