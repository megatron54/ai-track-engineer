"""Tests for the engine monitor."""

from __future__ import annotations

import pytest
from src.analysis.engine_monitor import AlertSeverity, EngineMonitor

from tests.factories import make_physics


def test_invalid_max_rpm() -> None:
    with pytest.raises(ValueError, match="max_rpm must be positive"):
        EngineMonitor(0)


def test_invalid_redline_fraction() -> None:
    with pytest.raises(ValueError, match="redline_fraction"):
        EngineMonitor(8000, redline_fraction=1.5)


def test_no_alert_below_redline() -> None:
    monitor = EngineMonitor(8000)
    assert monitor.check(make_physics(rpm=6000)) == []


def test_redline_warning() -> None:
    monitor = EngineMonitor(8000, redline_fraction=0.95)
    assert monitor.redline_rpm == 7600
    alerts = monitor.check(make_physics(rpm=7700))
    assert len(alerts) == 1
    assert alerts[0].kind == "redline"
    assert alerts[0].severity is AlertSeverity.WARNING


def test_over_rev_critical() -> None:
    monitor = EngineMonitor(8000)
    alerts = monitor.check(make_physics(rpm=8200))
    assert len(alerts) == 1
    assert alerts[0].kind == "over_rev"
    assert alerts[0].severity is AlertSeverity.CRITICAL
    assert alerts[0].rpm == 8200
