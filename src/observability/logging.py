"""Structured logging via :mod:`structlog`.

A single :func:`configure_logging` call wires up structlog with sensible
defaults. Console rendering is used for development; JSON rendering can be
enabled for production/headless runs by passing ``json_logs=True``.
"""

from __future__ import annotations

import logging
import sys

import structlog

_configured = False


def configure_logging(level: str = "INFO", *, json_logs: bool = False) -> None:
    """Configure structlog and the stdlib logging bridge.

    Args:
        level: Minimum log level name (e.g. ``"INFO"``, ``"DEBUG"``).
        json_logs: When ``True`` emit newline-delimited JSON instead of the
            colourised console renderer.
    """
    global _configured

    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, configuring defaults on first use.

    Args:
        name: Optional logger name, typically ``__name__`` of the caller.
    """
    if not _configured:
        configure_logging()
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
