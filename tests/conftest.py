"""Shared pytest fixtures and test configuration."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from src.config import ac_paths
from src.config import settings as settings_module

# Environment variables that can leak a developer's real configuration into the
# test run. They are cleared before each test for deterministic behaviour.
_AC_ENV_VARS = (
    "AC_INSTALL_PATH",
    "LOG_LEVEL",
    "INFLUXDB__TOKEN",
    "INFLUXDB__URL",
    "OLLAMA__MODEL",
    "OLLAMA__URL",
    "APP__LOG_LEVEL",
    "APP__AC_INSTALL_PATH",
)


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate settings from the host environment and config cache.

    Clears relevant environment variables, disables ``.env`` loading, and resets
    the cached settings instance so each test starts from defaults.
    """
    for var in _AC_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    # Prevent pydantic-settings from reading a real local .env during tests so
    # results stay deterministic regardless of the developer's machine.
    monkeypatch.setitem(settings_module.Settings.model_config, "env_file", None)
    # Neutralise probing of real Steam install locations so unit tests do not
    # depend on whether Assetto Corsa happens to be installed on the host.
    monkeypatch.setattr(ac_paths, "_COMMON_STEAM_ROOTS", ())
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture
def clean_environ(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Provide a snapshot of os.environ for assertions in tests."""
    return dict(os.environ)
