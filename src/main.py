"""Application entry point and command-line interface.

Phase 0 provides the CLI skeleton and an environment ``doctor`` command. The
real-time telemetry orchestration is wired in from Phase 1 onwards.
"""

from __future__ import annotations

import typer

from src import __version__
from src.config import find_ac_install, get_settings
from src.observability import configure_logging, get_logger

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
) -> None:
    """Start the engineer (telemetry loop, dashboard, optional voice).

    The full pipeline is implemented incrementally across phases; this command
    currently validates configuration and reports the selected mode.
    """
    settings = get_settings()
    configure_logging(settings.app.log_level)
    log = get_logger("run")
    log.info(
        "startup",
        mode="mock" if mock else "live",
        voice=voice,
        poll_hz=settings.app.telemetry_poll_hz,
    )
    typer.echo(
        "Telemetry pipeline is not implemented yet (arriving in Phase 1). "
        f"Selected mode: {'mock' if mock else 'live'}, voice={'on' if voice else 'off'}."
    )


if __name__ == "__main__":  # pragma: no cover
    app()
