"""Tests for the dashboard replay state (remember / replay buffering)."""

from __future__ import annotations

from src.dashboard.state import DashboardState


def _session() -> dict[str, object]:
    return {"type": "session", "car": "x"}


def test_replay_empty_before_any_events() -> None:
    assert DashboardState().replay() == []


def test_replay_orders_mode_then_laps_then_strategy_then_gap() -> None:
    state = DashboardState()
    state.set_session(_session())
    state.remember({"type": "lap", "number": 1})
    state.remember({"type": "gap", "ahead_s": 1.0})
    state.remember({"type": "mode", "mode": "race"})
    state.remember({"type": "lap", "number": 2})
    state.remember({"type": "strategy", "lap": 2})

    replay = state.replay()
    assert [e["type"] for e in replay] == ["mode", "lap", "lap", "strategy", "gap"]
    assert [e["number"] for e in replay if e["type"] == "lap"] == [1, 2]


def test_sticky_events_keep_only_latest() -> None:
    state = DashboardState()
    state.remember({"type": "strategy", "lap": 1})
    state.remember({"type": "strategy", "lap": 5})
    strategy = [e for e in state.replay() if e["type"] == "strategy"]
    assert len(strategy) == 1
    assert strategy[0]["lap"] == 5


def test_set_session_clears_prior_buffer() -> None:
    state = DashboardState()
    state.remember({"type": "lap", "number": 1})
    state.remember({"type": "mode", "mode": "race"})
    state.set_session(_session())
    assert state.replay() == []


def test_lap_history_is_bounded() -> None:
    state = DashboardState()
    for i in range(80):
        state.remember({"type": "lap", "number": i})
    laps = [e for e in state.replay() if e["type"] == "lap"]
    assert len(laps) == 60
    assert laps[0]["number"] == 20  # the oldest 20 laps were dropped
    assert laps[-1]["number"] == 79


def test_unknown_event_type_is_ignored() -> None:
    state = DashboardState()
    state.remember({"type": "telemetry", "speed_kmh": 100})
    assert state.replay() == []
