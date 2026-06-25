"""Application entry point and command-line interface.

Phase 0 provides the CLI skeleton and an environment ``doctor`` command. The
real-time telemetry orchestration is wired in from Phase 1 onwards.
"""

from __future__ import annotations

import typer
from fastapi import FastAPI

from src import __version__
from src.config import find_ac_install, get_settings
from src.dashboard import TelemetryHub, capture_to_hub, create_app
from src.observability import configure_logging, get_logger
from src.processing import LapSegmenter
from src.processing.models import Lap
from src.telemetry import (
    MockTelemetrySource,
    SharedMemoryTelemetrySource,
    TelemetrySource,
)

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
    segmenter = LapSegmenter()
    lap_log = get_logger("lap")

    async def on_lap(lap: Lap) -> None:
        lap_log.info(
            "lap-completed",
            number=lap.lap_number,
            time_ms=lap.lap_time_ms,
            valid=lap.valid,
        )

    async def producer() -> None:
        await capture_to_hub(
            source,
            hub,
            hz=settings.app.telemetry_poll_hz,
            segmenter=segmenter,
            on_lap=on_lap,
        )

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


if __name__ == "__main__":  # pragma: no cover
    app()
