"""Tests for the session recorder (CSV telemetry writer)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from src.storage.session_recorder import SessionRecorder

from tests.factories import make_frame


def test_recorder_writes_header_and_rows(tmp_path: Path) -> None:
    with SessionRecorder(tmp_path, "spa", "f2004", "abc") as rec:
        rec.write(make_frame(timestamp=1.0, speed_kmh=200.0))
        rec.write(make_frame(timestamp=1.016, speed_kmh=201.0))
    assert rec.rows_written == 2

    with open(rec.path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["timestamp"] == "1.0"
    assert rows[0]["speed_kmh"] == "200.0"
    assert rows[1]["speed_kmh"] == "201.0"
    assert "tyre_temp_fl" in rows[0]
    assert "car_x" in rows[0]


def test_recorder_includes_delta(tmp_path: Path) -> None:
    with SessionRecorder(tmp_path, "t", "c", "s") as rec:
        rec.write(make_frame(), delta=-0.25)
        rec.write(make_frame(), delta=None)
    with open(rec.path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["delta"] == "-0.25"
    assert rows[1]["delta"] == ""


def test_recorder_creates_parent_dirs(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b"
    with SessionRecorder(deep, "t", "c", "s") as rec:
        rec.write(make_frame())
    assert rec.path.is_file()


def test_recorder_raises_if_not_open(tmp_path: Path) -> None:
    rec = SessionRecorder(tmp_path, "t", "c", "s")
    with pytest.raises(RuntimeError, match="not open"):
        rec.write(make_frame())


def test_recorder_close_is_idempotent(tmp_path: Path) -> None:
    rec = SessionRecorder(tmp_path, "t", "c", "s")
    rec.open()
    rec.close()
    rec.close()  # must not raise
