"""Shared dashboard session state.

Holds the latest session envelope (track + map metadata), the path to the
track's map image, and a small replay buffer of "sticky" engineer events (lap
history, latest strategy / mode / gap). This lets HTTP endpoints and
newly-connected (or reconnected/refreshed) WebSocket clients be served the
current context immediately, independently of the capture loop — so the
dashboard is never blank after a reload mid-session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Cap the replayed lap history so a long stint cannot grow state without bound.
_MAX_LAPS = 60
# Engineer event types whose *latest* value is replayed on connect.
_STICKY_TYPES = ("mode", "strategy", "gap")


class DashboardState:
    """Mutable, process-wide snapshot of the current session for the dashboard."""

    def __init__(self) -> None:
        self._session: dict[str, Any] | None = None
        self._map_png: Path | None = None
        self._laps: list[dict[str, Any]] = []
        self._sticky: dict[str, dict[str, Any]] = {}

    @property
    def session(self) -> dict[str, Any] | None:
        """The latest ``session`` envelope, or ``None`` before a session starts."""
        return self._session

    @property
    def map_png(self) -> Path | None:
        """Path to the current track's ``map.png``, if available."""
        return self._map_png

    def set_session(self, message: dict[str, Any]) -> None:
        """Set the active session, clearing any buffered events from a prior one."""
        self._session = message
        self._laps.clear()
        self._sticky.clear()

    def set_map_png(self, path: Path | None) -> None:
        self._map_png = path

    def remember(self, message: dict[str, Any]) -> None:
        """Buffer an engineer event so it can be replayed to new clients.

        ``lap`` events accumulate (bounded) to rebuild the lap table and feed;
        ``mode`` / ``strategy`` / ``gap`` keep only their latest value.
        """
        kind = message.get("type")
        if kind == "lap":
            self._laps.append(message)
            if len(self._laps) > _MAX_LAPS:
                del self._laps[0]
        elif kind in _STICKY_TYPES:
            self._sticky[kind] = message

    def replay(self) -> list[dict[str, Any]]:
        """Ordered events to send a freshly-connected client after ``session``.

        Order: mode (header), laps oldest-first (rebuilds table + cards), then the
        latest strategy and gap so those panels populate without waiting a lap.
        """
        events: list[dict[str, Any]] = []
        if "mode" in self._sticky:
            events.append(self._sticky["mode"])
        events.extend(self._laps)
        for kind in ("strategy", "gap"):
            if kind in self._sticky:
                events.append(self._sticky[kind])
        return events
