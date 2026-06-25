"""Configuration layer: settings loading and Assetto Corsa path discovery."""

from __future__ import annotations

from src.config.ac_paths import find_ac_install
from src.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings", "find_ac_install"]
