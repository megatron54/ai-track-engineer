"""Observability layer: structured logging (and, later, metrics/tracing)."""

from __future__ import annotations

from src.observability.logging import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
