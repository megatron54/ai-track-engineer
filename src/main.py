"""Application entry point and command-line interface.

Phase 0 provides the CLI skeleton and an environment ``doctor`` command. The
real-time telemetry orchestration is wired in from Phase 1 onwards.
"""

from __future__ import annotations

import asyncio

import typer

from src import __version__
from src.config import find_ac_install, get_settings
from src.observability import configure_logging, get_logger
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
    seconds: float = typer.Option(
        3.0, "--seconds", min=0.0, help="How long to stream a telemetry preview."
    ),
) -> None:
    """Start the engineer (telemetry loop, dashboard, optional voice).

    The full pipeline is implemented incrementally across phases. This command
    currently connects a telemetry source and streams a short preview to the
    log so the capture path can be exercised end to end (with ``--mock`` it
    needs no running game).
    """
    settings = get_settings()
    configure_logging(settings.app.log_level)
    log = get_logger("run")

    if voice:
        log.warning("voice-not-implemented", note="voice arrives in Phase 6")

    source: TelemetrySource = (
        MockTelemetrySource() if mock else SharedMemoryTelemetrySource()
    )
    log.info("startup", mode="mock" if mock else "live", poll_hz=settings.app.telemetry_poll_hz)
    frames = asyncio.run(
        _preview_stream(source, hz=settings.app.telemetry_poll_hz, seconds=seconds)
    )
    typer.echo(f"Streamed {frames} telemetry frames ({'mock' if mock else 'live'} source).")


async def _preview_stream(source: TelemetrySource, *, hz: int, seconds: float) -> int:
    """Stream telemetry for a fixed duration, logging a periodic summary.

    Returns the number of frames streamed. Connection and cleanup are always
    paired so the source is released even if streaming fails.
    """
    log = get_logger("telemetry")
    max_frames = int(hz * seconds)
    count = 0
    try:
        static_info = source.connect()
        log.info("connected", track=static_info.track, car=static_info.car_model)
        async for frame in source.stream(hz, max_frames=max_frames):
            count += 1
            if count % hz == 0:  # roughly once per second
                physics = frame.physics
                log.info(
                    "telemetry",
                    lap_pos=round(frame.graphics.normalized_car_position, 3),
                    speed_kmh=round(physics.speed_kmh, 1),
                    rpm=physics.rpm,
                    gear=physics.gear_label,
                )
    finally:
        source.close()
    return count


if __name__ == "__main__":  # pragma: no cover
    app()
