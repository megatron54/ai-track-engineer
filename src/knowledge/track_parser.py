"""Parse Assetto Corsa track files into track-knowledge models.

Reads the plain-text, stable formats shipped with every track:

* ``data/sections.ini`` - named sections/corners with normalised IN/OUT.
* ``ui/.../ui_track.json`` - display name and length.

Multi-layout tracks keep these inside a layout subfolder; :func:`load_track`
resolves the right location. (The binary ``ai/fast_lane.ai`` ideal line is a
separate, version-specific format handled elsewhere.)
"""

from __future__ import annotations

import configparser
import json
from pathlib import Path

from src.knowledge.models import Corner, MapProjection, TrackInfo


def parse_sections(text: str) -> tuple[Corner, ...]:
    """Parse ``sections.ini`` content into ordered corners."""
    parser = configparser.ConfigParser(
        strict=False, inline_comment_prefixes=(";", "//")
    )
    parser.read_string(text)

    corners: list[Corner] = []
    for section in parser.sections():
        if not section.upper().startswith("SECTION_"):
            continue
        try:
            index = int(section.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        corners.append(
            Corner(
                index=index,
                name=parser.get(section, "TEXT", fallback=f"Section {index}").strip(),
                entry=parser.getfloat(section, "IN", fallback=0.0),
                exit=parser.getfloat(section, "OUT", fallback=0.0),
            )
        )
    corners.sort(key=lambda corner: corner.index)
    return tuple(corners)


def parse_ui_track(text: str) -> dict[str, object]:
    """Parse ``ui_track.json`` into a plain dict (tolerant of bad JSON)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_map_ini(text: str) -> MapProjection | None:
    """Parse ``map.ini`` ``[PARAMETERS]`` into a :class:`MapProjection`."""
    parser = configparser.ConfigParser(
        strict=False, inline_comment_prefixes=(";", "//")
    )
    parser.read_string(text)
    if not parser.has_section("PARAMETERS"):
        return None
    section = "PARAMETERS"
    try:
        return MapProjection(
            width=parser.getfloat(section, "WIDTH"),
            height=parser.getfloat(section, "HEIGHT"),
            x_offset=parser.getfloat(section, "X_OFFSET"),
            z_offset=parser.getfloat(section, "Z_OFFSET"),
            scale_factor=parser.getfloat(section, "SCALE_FACTOR", fallback=1.0),
        )
    except (configparser.NoOptionError, ValueError):
        return None


def map_png_path(track_dir: str | Path, *, layout: str = "") -> Path | None:
    """Return the path to a track layout's ``map.png``, if it exists."""
    base = _resolve_layout_dir(Path(track_dir), layout)
    candidate = base / "map.png"
    return candidate if candidate.is_file() else None


def _length_to_metres(raw: object) -> float:
    """Best-effort conversion of a ui_track length to metres.

    Assetto Corsa stores length inconsistently (km for Kunos tracks, sometimes
    metres for mods). Values below 100 are treated as kilometres.
    """
    try:
        value = float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0
    return value * 1000.0 if 0 < value < 100 else value


def _resolve_layout_dir(track_dir: Path, layout: str) -> Path:
    candidate = track_dir / layout
    return candidate if layout and candidate.is_dir() else track_dir


def load_track(
    track_dir: str | Path, *, track_id: str | None = None, layout: str = ""
) -> TrackInfo:
    """Load a :class:`TrackInfo` from a track directory.

    Args:
        track_dir: Path to ``content/tracks/<track_id>``.
        track_id: Track identifier; defaults to the directory name.
        layout: Optional layout name for multi-layout tracks.
    """
    track_path = Path(track_dir)
    resolved_track_id = track_id or track_path.name
    base = _resolve_layout_dir(track_path, layout)

    sections_path = base / "data" / "sections.ini"
    corners: tuple[Corner, ...] = ()
    if sections_path.is_file():
        corners = parse_sections(sections_path.read_text(encoding="utf-8", errors="ignore"))

    ui_path = (
        track_path / "ui" / layout / "ui_track.json"
        if layout
        else track_path / "ui" / "ui_track.json"
    )
    name = resolved_track_id
    length_m = 0.0
    if ui_path.is_file():
        ui = parse_ui_track(ui_path.read_text(encoding="utf-8", errors="ignore"))
        name = str(ui.get("name") or resolved_track_id)
        length_m = _length_to_metres(ui.get("length", 0))

    map_path = base / "data" / "map.ini"
    projection: MapProjection | None = None
    if map_path.is_file():
        projection = parse_map_ini(map_path.read_text(encoding="utf-8", errors="ignore"))

    return TrackInfo(
        track_id=resolved_track_id,
        name=name,
        layout=layout,
        length_m=length_m,
        corners=corners,
        map=projection,
    )
