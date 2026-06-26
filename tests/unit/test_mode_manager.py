"""Tests for session mode manager."""

from __future__ import annotations

from src.strategy.mode_manager import EngineerMode, mode_from_session, profile_for
from src.telemetry.shm_structs import ACSessionType


def test_mode_mapping() -> None:
    assert mode_from_session(ACSessionType.PRACTICE) is EngineerMode.PRACTICE
    assert mode_from_session(ACSessionType.QUALIFY) is EngineerMode.QUALIFYING
    assert mode_from_session(ACSessionType.RACE) is EngineerMode.RACE
    assert mode_from_session(ACSessionType.HOTLAP) is EngineerMode.PRACTICE


def test_profiles_exist_and_differ() -> None:
    practice = profile_for(EngineerMode.PRACTICE)
    qualifying = profile_for(EngineerMode.QUALIFYING)
    race = profile_for(EngineerMode.RACE)
    assert practice.personality != qualifying.personality
    assert qualifying.silence_during_hotlap is True
    assert race.max_messages_per_lap < practice.max_messages_per_lap
