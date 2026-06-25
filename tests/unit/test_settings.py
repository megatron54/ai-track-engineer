"""Tests for the layered settings loader."""

from __future__ import annotations

import pytest
from src.config import settings as settings_module
from src.config.settings import Settings, get_settings


def test_defaults_are_applied() -> None:
    settings = Settings()
    assert settings.app.telemetry_poll_hz == 60
    assert settings.influxdb.bucket == "telemetry"
    assert settings.ollama.model == "mistral"
    assert settings.influxdb.token == ""


def test_env_overrides_nested_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA__MODEL", "llama3")
    monkeypatch.setenv("INFLUXDB__TOKEN", "unit-test-token")
    settings = Settings()
    assert settings.ollama.model == "llama3"
    assert settings.influxdb.token == "unit-test-token"


def test_yaml_defaults_are_loaded(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("app:\n  log_level: DEBUG\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_DEFAULT_YAML", yaml_file)
    settings = Settings.load()
    assert settings.app.log_level == "DEBUG"


def test_missing_yaml_falls_back_to_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings_module, "_DEFAULT_YAML", tmp_path / "does-not-exist.yaml")
    settings = Settings.load()
    assert settings.app.log_level == "INFO"


def test_token_is_hidden_in_repr() -> None:
    settings = Settings(influxdb={"token": "super-secret"})  # type: ignore[arg-type]
    assert "super-secret" not in repr(settings.influxdb)


def test_get_settings_is_cached() -> None:
    first = get_settings()
    second = get_settings()
    assert first is second
