"""Engine monitoring from telemetry.

Assetto Corsa's shared memory does not expose water/oil temperature, so this
monitor focuses on what *is* observable and actionable: over-revving and
approaching the rev limiter, judged against the car's ``max_rpm``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from src.telemetry.models import ACPhysics

_DEFAULT_REDLINE_FRACTION = 0.97


class AlertSeverity(StrEnum):
    """Severity of an engine alert."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EngineAlert(BaseModel):
    """A single engine alert raised for a telemetry frame."""

    model_config = ConfigDict(frozen=True)

    kind: str
    severity: AlertSeverity
    message: str
    rpm: int


class EngineMonitor:
    """Raise alerts for over-rev and rev-limiter proximity."""

    def __init__(
        self, max_rpm: int, *, redline_fraction: float = _DEFAULT_REDLINE_FRACTION
    ) -> None:
        if max_rpm <= 0:
            raise ValueError("max_rpm must be positive")
        if not 0.0 < redline_fraction <= 1.0:
            raise ValueError("redline_fraction must be in (0, 1]")
        self._max_rpm = max_rpm
        self._redline_rpm = int(max_rpm * redline_fraction)

    @property
    def redline_rpm(self) -> int:
        """RPM at which a redline warning is raised."""
        return self._redline_rpm

    def check(self, physics: ACPhysics) -> list[EngineAlert]:
        """Return any engine alerts for a physics frame."""
        rpm = physics.rpm
        if rpm > self._max_rpm:
            return [
                EngineAlert(
                    kind="over_rev",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Over-rev: {rpm} rpm exceeds limit {self._max_rpm}",
                    rpm=rpm,
                )
            ]
        if rpm >= self._redline_rpm:
            return [
                EngineAlert(
                    kind="redline",
                    severity=AlertSeverity.WARNING,
                    message=f"Approaching limiter: {rpm} rpm",
                    rpm=rpm,
                )
            ]
        return []
