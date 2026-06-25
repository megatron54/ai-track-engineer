"""Telemetry capture layer.

Public API: validated domain models (:class:`TelemetryFrame` and its parts) and
the converters that build them from raw shared-memory structures. The raw
ctypes layout lives in :mod:`src.telemetry.shm_structs`.
"""

from __future__ import annotations

from src.telemetry.converters import frame_from_structs
from src.telemetry.models import (
    ACGraphics,
    ACPhysics,
    ACStaticInfo,
    TelemetryFrame,
    Wheels,
)
from src.telemetry.shm_structs import ACFlagType, ACSessionType, ACStatus

__all__ = [
    "ACFlagType",
    "ACGraphics",
    "ACPhysics",
    "ACSessionType",
    "ACStaticInfo",
    "ACStatus",
    "TelemetryFrame",
    "Wheels",
    "frame_from_structs",
]
