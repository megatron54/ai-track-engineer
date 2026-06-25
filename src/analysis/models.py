"""Domain models for the analysis layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CornerDelta(BaseModel):
    """Time gained or lost in a corner relative to a reference lap.

    ``delta_s`` is *current minus reference*: positive means the current lap was
    slower through this corner (time lost), negative means faster (time gained).
    """

    model_config = ConfigDict(frozen=True)

    corner_index: int
    corner_name: str
    delta_s: float

    @property
    def lost_time(self) -> bool:
        """Whether time was lost (current slower than reference)."""
        return self.delta_s > 0
