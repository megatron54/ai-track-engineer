"""Session mode manager: adapt engineer personality to Practice/Qualify/Race.

Each mode defines the engineer's priorities and communication style. The mode
follows the auto-detected session type but can be overridden by a voice command.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.telemetry.shm_structs import ACSessionType


class EngineerMode(StrEnum):
    PRACTICE = "practice"
    QUALIFYING = "qualifying"
    RACE = "race"


@dataclass(frozen=True)
class ModeProfile:
    """The engineer's personality and priorities for a session mode."""

    mode: EngineerMode
    priority: str
    personality: str
    max_messages_per_lap: int
    silence_during_hotlap: bool


_PROFILES: dict[EngineerMode, ModeProfile] = {
    EngineerMode.PRACTICE: ModeProfile(
        mode=EngineerMode.PRACTICE,
        priority="Learning and experimentation",
        personality="Patient, exploratory, detailed",
        max_messages_per_lap=6,
        silence_during_hotlap=False,
    ),
    EngineerMode.QUALIFYING: ModeProfile(
        mode=EngineerMode.QUALIFYING,
        priority="One perfect lap",
        personality="Precise, focused, minimal",
        max_messages_per_lap=2,
        silence_during_hotlap=True,
    ),
    EngineerMode.RACE: ModeProfile(
        mode=EngineerMode.RACE,
        priority="Final position (result)",
        personality="Tactical, calm, decisive — F1 radio style",
        max_messages_per_lap=3,
        silence_during_hotlap=False,
    ),
}


def profile_for(mode: EngineerMode) -> ModeProfile:
    """Return the engineer profile for a session mode."""
    return _PROFILES[mode]


def mode_from_session(session_type: ACSessionType) -> EngineerMode:
    """Map an AC session type to an engineer mode."""
    if session_type is ACSessionType.QUALIFY:
        return EngineerMode.QUALIFYING
    if session_type is ACSessionType.RACE:
        return EngineerMode.RACE
    return EngineerMode.PRACTICE
