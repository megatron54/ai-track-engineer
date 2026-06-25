"""Domain models for the processing layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Lap(BaseModel):
    """A completed lap with timing and validity metadata.

    ``lap_number`` is the 1-based index reported by Assetto Corsa when the lap
    finished. ``sector_times_ms`` holds the per-sector times captured during the
    lap (best-effort: it depends on the game emitting sector splits).
    """

    model_config = ConfigDict(frozen=True)

    lap_number: int
    lap_time_ms: int
    sector_times_ms: tuple[int, ...] = ()
    valid: bool = True
    started_at: float = 0.0
    ended_at: float = 0.0

    @property
    def lap_time_seconds(self) -> float:
        """Lap time in seconds."""
        return self.lap_time_ms / 1000.0
