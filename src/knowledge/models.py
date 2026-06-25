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


class MapProjection(BaseModel):
    """World-to-pixel projection for an Assetto Corsa track minimap.

    Maps a car's world ``(x, z)`` coordinates onto the track's ``map.png`` image
    using the parameters from ``data/map.ini``. The image is ``width`` x
    ``height`` pixels (origin top-left).
    """

    model_config = ConfigDict(frozen=True)

    width: float
    height: float
    x_offset: float
    z_offset: float
    scale_factor: float = 1.0

    def to_pixel(self, x: float, z: float) -> tuple[float, float]:
        """Project world ``(x, z)`` coordinates to map pixel ``(px, py)``."""
        return (
            (x + self.x_offset) * self.scale_factor,
            (z + self.z_offset) * self.scale_factor,
        )


class TrackInfo(BaseModel):
    """Static knowledge about a track layout."""

    model_config = ConfigDict(frozen=True)

    track_id: str
    name: str
    layout: str = ""
    length_m: float = 0.0
    corners: tuple[Corner, ...] = ()
    map: MapProjection | None = None

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
