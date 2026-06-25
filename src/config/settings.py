"""Application configuration.

Settings are layered: hard-coded defaults < ``config/settings.yaml`` <
environment variables / ``.env``. Secrets (tokens) only ever come from the
environment, never from the versioned YAML file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: <repo>/src/config/settings.py -> parents[2] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_YAML = _REPO_ROOT / "config" / "settings.yaml"


class InfluxSettings(BaseModel):
    """Connection settings for the InfluxDB time-series store."""

    url: str = "http://localhost:8086"
    org: str = "ai-track-engineer"
    bucket: str = "telemetry"
    token: str = Field(default="", repr=False)  # never echoed in logs/reprs


class OllamaSettings(BaseModel):
    """Connection settings for the local Ollama LLM server."""

    url: str = "http://localhost:11434"
    model: str = "mistral"


class AppSettings(BaseModel):
    """General application tunables."""

    log_level: str = "INFO"
    telemetry_poll_hz: int = 60
    dashboard_stream_hz: int = 30
    ac_install_path: str | None = None


def _load_yaml_defaults(path: Path | None = None) -> dict[str, Any]:
    """Load non-secret default values from the YAML config, if present.

    Args:
        path: Override for the YAML location. Defaults to the module-level
            ``_DEFAULT_YAML`` resolved at call time (so tests can patch it).
    """
    resolved = path if path is not None else _DEFAULT_YAML
    if not resolved.is_file():
        return {}
    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


class Settings(BaseSettings):
    """Root settings object, assembled from YAML defaults + environment.

    Environment variables use a double-underscore delimiter for nested values,
    e.g. ``INFLUXDB__TOKEN`` or ``OLLAMA__MODEL``. A few flat aliases
    (``AC_INSTALL_PATH``, ``LOG_LEVEL``) are also honoured for convenience.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    influxdb: InfluxSettings = Field(default_factory=InfluxSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)

    @classmethod
    def load(cls) -> Settings:
        """Build settings from YAML defaults overlaid with environment values."""
        defaults = _load_yaml_defaults()
        return cls(**defaults)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, process-wide :class:`Settings` instance."""
    return Settings.load()
