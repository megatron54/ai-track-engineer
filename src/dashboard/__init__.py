"""Web dashboard: FastAPI app, fan-out hub, session state and orchestration."""

from __future__ import annotations

from src.dashboard.api import create_app
from src.dashboard.hub import TelemetryHub
from src.dashboard.pump import run_session
from src.dashboard.serialization import lap_event, session_event, telemetry_event
from src.dashboard.state import DashboardState

__all__ = [
    "DashboardState",
    "TelemetryHub",
    "create_app",
    "lap_event",
    "run_session",
    "session_event",
    "telemetry_event",
]
