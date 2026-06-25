"""Web dashboard: FastAPI app, telemetry hub, fan-out and capture orchestration."""

from __future__ import annotations

from src.dashboard.api import create_app
from src.dashboard.hub import TelemetryHub
from src.dashboard.pump import capture_to_hub
from src.dashboard.serialization import frame_to_payload

__all__ = ["TelemetryHub", "capture_to_hub", "create_app", "frame_to_payload"]
