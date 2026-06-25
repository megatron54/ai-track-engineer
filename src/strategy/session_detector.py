"""Session detection: track the active session type and its transitions.

Reads the session type from the graphics page and reports when it changes
(Practice -> Qualify -> Race), with support for a manual override (e.g. from a
future voice command) that takes precedence over the auto-detected value.
"""

from __future__ import annotations

from src.telemetry.models import ACGraphics
from src.telemetry.shm_structs import ACSessionType


class SessionModeTracker:
    """Track the current session type and surface transitions."""

    def __init__(self) -> None:
        self._detected: ACSessionType | None = None
        self._override: ACSessionType | None = None

    @property
    def current(self) -> ACSessionType | None:
        """The effective session type (override if set, else detected)."""
        return self._override if self._override is not None else self._detected

    def update(self, graphics: ACGraphics) -> ACSessionType | None:
        """Feed a graphics frame; return the new effective mode if it changed."""
        previous = self.current
        self._detected = graphics.session_type
        new = self.current
        return new if new != previous else None

    def set_override(self, mode: ACSessionType | None) -> ACSessionType | None:
        """Force a mode (or clear with ``None``); return the new effective mode."""
        previous = self.current
        self._override = mode
        new = self.current
        return new if new != previous else None
