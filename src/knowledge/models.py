"""Domain models for track knowledge (corners and track metadata)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Corner(BaseModel):
    """A named track section / corner with normalised entry and exit positions.

    Positions are in the same ``[0, 1)`` space as
    ``ACGraphics.normalized_car_position``, so a corner can be matched directly
    against live telemetry. A corner "wraps" the start/finish line when
    ``entry > exit`` (e.g. Turn 1 just before the line).
    """

    model_config = ConfigDict(frozen=True)

    index: int
    name: str
    entry: float
    exit: float

    def contains(self, position: float) -> bool:
        """Whether a normalised track position falls within this corner."""
        if self.entry <= self.exit:
            return self.entry <= position < self.exit
        # Wraps past the start/finish line.
        return position >= self.entry or position < self.exit


class TrackInfo(BaseModel):
    """Static knowledge about a track layout."""

    model_config = ConfigDict(frozen=True)

    track_id: str
    name: str
    layout: str = ""
    length_m: float = 0.0
    corners: tuple[Corner, ...] = ()

    @property
    def corner_count(self) -> int:
        """Number of known corners/sections."""
        return len(self.corners)

    def corner_at(self, position: float) -> Corner | None:
        """Return the corner containing *position*, or ``None`` if on a straight."""
        for corner in self.corners:
            if corner.contains(position):
                return corner
        return None
