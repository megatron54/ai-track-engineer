"""Tolerant parser for Assetto Corsa ``.ini`` car/track files.

AC ini files use inline ``;`` comments, trailing whitespace/tabs, and
occasionally duplicate keys. This wraps :mod:`configparser` with settings that
tolerate those quirks and returns a plain nested ``{section: {key: value}}``
dict with values stripped.
"""

from __future__ import annotations

import configparser


class _CaseSensitiveParser(configparser.ConfigParser):
    """ConfigParser that preserves key case (AC keys are upper-case)."""

    def optionxform(self, optionstr: str) -> str:
        return optionstr


def parse_ini(text: str) -> dict[str, dict[str, str]]:
    """Parse INI text into ``{section: {key: value}}`` (values stripped)."""
    parser = _CaseSensitiveParser(
        strict=False,
        inline_comment_prefixes=(";", "//"),
        interpolation=None,
    )
    parser.read_string(text)
    return {
        section: {key: value.strip() for key, value in parser.items(section)}
        for section in parser.sections()
    }


def get_float(section: dict[str, str], key: str, default: float = 0.0) -> float:
    """Read a float from a parsed section, tolerating bad values."""
    try:
        return float(section[key])
    except (KeyError, ValueError):
        return default


def get_int(section: dict[str, str], key: str, default: int = 0) -> int:
    """Read an int from a parsed section, tolerating bad values."""
    try:
        return int(float(section[key]))
    except (KeyError, ValueError):
        return default
