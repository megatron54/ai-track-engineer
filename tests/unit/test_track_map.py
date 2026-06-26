"""Tests for track map (map.ini) parsing and projection."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.knowledge import load_track, map_png_path, parse_map_ini
from src.knowledge.models import MapProjection

# Real ks_laguna_seca / spa map.ini parameters.
_SPA_MAP_INI = """
[PARAMETERS]
WIDTH=1004.83
HEIGHT=1593.82
MARGIN=20
SCALE_FACTOR=1.3
X_OFFSET=664.529
Z_OFFSET=982.854
DRAWING_SIZE=10
"""


def test_parse_map_ini_extracts_parameters() -> None:
    projection = parse_map_ini(_SPA_MAP_INI)
    assert projection is not None
    assert projection.width == pytest.approx(1004.83)
    assert projection.scale_factor == pytest.approx(1.3)
    assert projection.x_offset == pytest.approx(664.529)


def test_parse_map_ini_missing_section() -> None:
    assert parse_map_ini("[OTHER]\nFOO=1\n") is None


def test_to_pixel_matches_real_spa_projection() -> None:
    projection = parse_map_ini(_SPA_MAP_INI)
    assert projection is not None
    # Real captured Spa car coords -> verified pixel.
    # AC formula: px = (x + X_OFFSET) / SCALE_FACTOR + MARGIN
    px, py = projection.to_pixel(-188.59, -254.52)
    # Expected: ((-188.59+664.529)/1.3 + 20, (-254.52+982.854)/1.3 + 20) = (386.1, 580.3)
    assert px == pytest.approx(386.1, abs=1.0)
    assert py == pytest.approx(580.3, abs=1.0)
    assert 0 <= px <= projection.width
    assert 0 <= py <= projection.height


def test_scale_factor_defaults_to_one() -> None:
    projection = MapProjection(width=100, height=100, x_offset=10, z_offset=20)
    assert projection.scale_factor == 1.0
    assert projection.to_pixel(0.0, 0.0) == (10.0, 20.0)


def _make_track_with_map(root: Path) -> Path:
    (root / "data").mkdir(parents=True)
    (root / "data" / "map.ini").write_text(_SPA_MAP_INI, encoding="utf-8")
    (root / "map.png").write_bytes(b"\x89PNG\r\n")
    (root / "ui").mkdir()
    (root / "ui" / "ui_track.json").write_text('{"name": "Spa"}', encoding="utf-8")
    return root


def test_load_track_populates_map(tmp_path: Path) -> None:
    track_dir = _make_track_with_map(tmp_path / "spa")
    track = load_track(track_dir)
    assert track.map is not None
    assert track.map.scale_factor == pytest.approx(1.3)


def test_map_png_path_resolves(tmp_path: Path) -> None:
    track_dir = _make_track_with_map(tmp_path / "spa")
    found = map_png_path(track_dir)
    assert found is not None
    assert found.name == "map.png"
    assert map_png_path(tmp_path / "no-track") is None
