"""Analysis layer: lap comparison and tyre/engine monitors.

The higher-level ``AnalysisPipeline`` (which also uses the AI advisor) lives in
``src.analysis.pipeline`` and is imported from there directly, so this package
stays free of an ``src.ai`` dependency.
"""

from __future__ import annotations

from src.analysis.engine_monitor import AlertSeverity, EngineAlert, EngineMonitor
from src.analysis.lap_comparator import LapComparison
from src.analysis.models import CornerDelta
from src.analysis.tyre_model import ThermalStatus, TyreThermalModel, TyreThermalReport

__all__ = [
    "AlertSeverity",
    "CornerDelta",
    "EngineAlert",
    "EngineMonitor",
    "LapComparison",
    "ThermalStatus",
    "TyreThermalModel",
    "TyreThermalReport",
]
