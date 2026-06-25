"""Domain models and the system prompt for the AI race engineer."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Priority(StrEnum):
    """Recommendation priority, highest first."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Recommendation(BaseModel):
    """A single piece of engineering advice for the driver."""

    model_config = ConfigDict(frozen=True)

    priority: Priority
    message: str
    corner: str | None = None


# The engineer's persona and rules. Kept terse and racing-specific so a small
# local model stays on-task. Adapted from the project plan.
SYSTEM_PROMPT = """You are a professional race engineer with 20 years of \
experience in GT3, GTE and Formula. Your driver depends on you to improve their \
lap times.

RULES:
- Be CONCISE. Maximum 2-3 sentences per recommendation.
- PRIORITISE changes that save the most time. Always state the estimated delta.
- Use correct racing TERMINOLOGY: trail braking, understeer, oversteer, \
rotation, apex, track-out, traction zone, lift-off, threshold braking, weight \
transfer.
- NEVER give generic advice. Always reference the specific corner (by name or \
number), the concrete speed and the exact point.
- If you do not have enough data for concrete advice, do NOT invent it. Say you \
need more laps.
- Format: "[Corner X] Concrete action -> expected result (estimated delta)".
- Priority: 1) Braking 2) Line 3) Throttle application 4) Consistency.
"""
