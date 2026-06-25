"""Locate the Assetto Corsa installation.

The Setup Lab and track/car knowledge layers need to read content files from the
local Assetto Corsa installation. The path can be provided explicitly via the
``AC_INSTALL_PATH`` setting; otherwise we probe a list of common Steam library
locations. No path is hard-coded to a specific user profile so the logic stays
portable across machines.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

# Relative path of the Assetto Corsa app inside a Steam library folder.
_STEAM_APP_SUBPATH = Path("steamapps") / "common" / "assettocorsa"

# Common Steam roots, expressed as templates resolved at call time. Drive letters
# other than C/D are probed dynamically in :func:`candidate_install_paths`.
_COMMON_STEAM_ROOTS: tuple[Path, ...] = (
    Path(r"C:\Program Files (x86)\Steam"),
    Path(r"C:\Program Files\Steam"),
    Path(r"D:\Steam"),
    Path(r"D:\SteamLibrary"),
    Path(r"E:\Steam"),
    Path(r"E:\SteamLibrary"),
)


def _looks_like_ac_install(path: Path) -> bool:
    """Return ``True`` if *path* looks like a valid Assetto Corsa root.

    We check for the main executable and the ``content`` directory rather than
    trusting the folder name alone.
    """
    return (path / "AssettoCorsa.exe").is_file() and (path / "content").is_dir()


def candidate_install_paths(explicit: str | os.PathLike[str] | None = None) -> Iterable[Path]:
    """Yield candidate Assetto Corsa install paths, most likely first.

    Args:
        explicit: An optional explicit path (e.g. from ``AC_INSTALL_PATH``). When
            provided it is always yielded first.
    """
    if explicit:
        yield Path(explicit)
    for root in _COMMON_STEAM_ROOTS:
        yield root / _STEAM_APP_SUBPATH


def find_ac_install(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Return the first valid Assetto Corsa installation found, or ``None``.

    Args:
        explicit: An optional explicit path to check before probing defaults.

    Returns:
        The resolved installation :class:`~pathlib.Path`, or ``None`` if no valid
        installation could be located.
    """
    for candidate in candidate_install_paths(explicit):
        if _looks_like_ac_install(candidate):
            return candidate.resolve()
    return None
