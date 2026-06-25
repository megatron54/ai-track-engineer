"""Shared dashboard session state.

Holds the latest session envelope (track + map metadata) and the path to the
track's map image, so HTTP endpoints and newly-connected WebSocket clients can
be served the current context immediately, independently of the capture loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class DashboardState:
    """Mutable, process-wide snapshot of the current session for the dashboard."""

    def __init__(self) -> None:
        self._session: dict[str, Any] | None = None
        self._map_png: Path | None = None

    @property
    def session(self) -> dict[str, Any] | None:
        """The latest ``session`` envelope, or ``None`` before a session starts."""
        return self._session

    @property
    def map_png(self) -> Path | None:
        """Path to the current track's ``map.png``, if available."""
        return self._map_png

    def set_session(self, message: dict[str, Any]) -> None:
        self._session = message

    def set_map_png(self, path: Path | None) -> None:
        self._map_png = path
