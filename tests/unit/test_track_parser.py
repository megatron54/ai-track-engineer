"""Tests for track-knowledge parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.knowledge import load_track, parse_sections, parse_ui_track
from src.knowledge.models import Corner, TrackInfo

# Trimmed from a real ks_laguna_seca sections.ini.
_SECTIONS_INI = """
[SECTION_0]
IN=0.988
OUT=0.048
TEXT=Turn 1

[SECTION_1]
IN=0.111
OUT=0.163
TEXT=Andretti Hairpin

[SECTION_7]
IN=0.665
OUT=0.717
TEXT=The Corkscrew
"""

_UI_TRACK_JSON = '{"name": "Laguna Seca", "country": "USA", "length": "3.602"}'


def test_parse_sections_extracts_named_corners() -> None:
    corners = parse_sections(_SECTIONS_INI)
    assert [c.name for c in corners] == ["Turn 1", "Andretti Hairpin", "The Corkscrew"]
    assert corners[0].index == 0
    assert corners[2].entry == pytest.approx(0.665)
    assert corners[2].exit == pytest.approx(0.717)


def test_parse_sections_ignores_unknown_sections() -> None:
    text = "[HEADER]\nFOO=1\n[SECTION_0]\nIN=0.1\nOUT=0.2\nTEXT=T1\n"
    corners = parse_sections(text)
    assert len(corners) == 1
    assert corners[0].name == "T1"


def test_corner_contains_normal_and_wrapping() -> None:
    normal = Corner(index=1, name="x", entry=0.2, exit=0.3)
    assert normal.contains(0.25) is True
    assert normal.contains(0.35) is False

    wrapping = Corner(index=0, name="T1", entry=0.98, exit=0.05)
    assert wrapping.contains(0.99) is True
    assert wrapping.contains(0.02) is True
    assert wrapping.contains(0.5) is False


def test_track_info_corner_at() -> None:
    corners = parse_sections(_SECTIONS_INI)
    track = TrackInfo(track_id="t", name="T", corners=corners)
    assert track.corner_count == 3
    found = track.corner_at(0.68)
    assert found is not None
    assert found.name == "The Corkscrew"
    assert track.corner_at(0.5) is None


def test_parse_ui_track_handles_bad_json() -> None:
    assert parse_ui_track("{not json") == {}
    assert parse_ui_track('"a string"') == {}
    assert parse_ui_track(_UI_TRACK_JSON)["name"] == "Laguna Seca"


def _make_track_dir(root: Path, *, layout: str = "") -> Path:
    base = root / layout if layout else root
    (base / "data").mkdir(parents=True, exist_ok=True)
    (base / "data" / "sections.ini").write_text(_SECTIONS_INI, encoding="utf-8")
    ui_dir = (root / "ui" / layout) if layout else (root / "ui")
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "ui_track.json").write_text(_UI_TRACK_JSON, encoding="utf-8")
    return root


def test_load_track_single_layout(tmp_path: Path) -> None:
    track_dir = _make_track_dir(tmp_path / "ks_laguna_seca")
    track = load_track(track_dir)
    assert track.track_id == "ks_laguna_seca"
    assert track.name == "Laguna Seca"
    assert track.length_m == pytest.approx(3602.0)
    assert track.corner_count == 3


def test_load_track_multi_layout(tmp_path: Path) -> None:
    track_dir = _make_track_dir(tmp_path / "ks_red_bull_ring", layout="layout_gp")
    track = load_track(track_dir, layout="layout_gp")
    assert track.layout == "layout_gp"
    assert track.corner_count == 3
    assert track.name == "Laguna Seca"  # from the fixture ui_track.json


def test_load_track_missing_files_falls_back(tmp_path: Path) -> None:
    empty = tmp_path / "barebones"
    empty.mkdir()
    track = load_track(empty)
    assert track.track_id == "barebones"
    assert track.name == "barebones"
    assert track.corner_count == 0
    assert track.length_m == 0.0
