"""Tests for gap manager."""

from __future__ import annotations

import pytest
from src.strategy.gap_manager import GapManager, GapTrend


def test_invalid_window() -> None:
    with pytest.raises(ValueError, match="window must be >= 2"):
        GapManager(window=1)


def test_no_data_stable() -> None:
    report = GapManager().report()
    assert report.gap_ahead_s is None
    assert report.trend_ahead is GapTrend.STABLE
    assert "No gap data" in report.message


def test_closing_gap_predicts_contact() -> None:
    gm = GapManager(window=5)
    for gap in [3.0, 2.5, 2.0, 1.5, 1.0]:
        gm.update(gap_ahead_s=gap, gap_behind_s=None)
    report = gm.report()
    assert report.trend_ahead is GapTrend.CLOSING
    assert report.contact_ahead_laps is not None
    assert report.contact_ahead_laps > 0


def test_opening_gap() -> None:
    gm = GapManager(window=3)
    for gap in [1.0, 1.5, 2.0]:
        gm.update(gap_ahead_s=None, gap_behind_s=gap)
    assert gm.report().trend_behind is GapTrend.OPENING


def test_stable_gap() -> None:
    gm = GapManager(window=4)
    for gap in [2.0, 2.01, 2.0, 2.02]:
        gm.update(gap_ahead_s=gap, gap_behind_s=None)
    assert gm.report().trend_ahead is GapTrend.STABLE
