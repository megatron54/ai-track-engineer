"""Read and write Assetto Corsa setup files.

AC setups are simple INI files where each parameter is a ``[SECTION]`` with a
single ``VALUE`` key. This module reads them into a flat ``{name: value}`` dict,
modifies values, and writes them back - always creating a backup before
overwriting.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.knowledge.car_physics.ini import parse_ini


def read_setup(path: str | Path) -> dict[str, str]:
    """Read an AC setup file into ``{SECTION_NAME: value}``."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    data = parse_ini(text)
    return {section: values.get("VALUE", "") for section, values in data.items()}


def write_setup(path: str | Path, setup: dict[str, str], *, backup: bool = True) -> Path:
    """Write a setup dict back to an AC setup file.

    Args:
        path: Target file path.
        setup: ``{SECTION_NAME: value}`` pairs.
        backup: If ``True`` and the file exists, create a ``.bak`` copy first.

    Returns:
        The path written to.
    """
    target = Path(path)
    if backup and target.is_file():
        shutil.copy2(target, target.with_suffix(".ini.bak"))
    lines: list[str] = []
    for section, value in setup.items():
        lines.append(f"[{section}]")
        lines.append(f"VALUE={value}")
        lines.append("")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def apply_changes(
    base: dict[str, str], changes: dict[str, str]
) -> dict[str, str]:
    """Return a new setup dict with *changes* applied over *base* (immutable)."""
    return {**base, **changes}
