"""Analysis layer: lap comparison and tyre/engine monitors.

The higher-level ``AnalysisPipeline`` (which also uses the AI advisor) lives in
``src.analysis.pipeline`` and is imported from there directly, so this package
stays free of an ``src.ai`` dependency.
"""

from __future__ import annotations

from src.analysis.engine_monitor import AlertSeverity, EngineAlert, EngineMonitor
from src.analysis.input_analyzer import (
    CornerInputDelta,
    CornerInputProfile,
    compare_corner_inputs,
    corner_input_profile,
)
from src.analysis.lap_comparator import LapComparison
from src.analysis.models import CornerDelta
from src.analysis.pattern_detector import CornerPattern, PatternReport, detect_patterns
from src.analysis.session_report import SessionReport, build_session_report
from src.analysis.tyre_model import ThermalStatus, TyreThermalModel, TyreThermalReport

__all__ = [
    "AlertSeverity",
    "CornerDelta",
    "CornerInputDelta",
    "CornerInputProfile",
    "CornerPattern",
    "EngineAlert",
    "EngineMonitor",
    "LapComparison",
    "PatternReport",
    "SessionReport",
    "ThermalStatus",
    "TyreThermalModel",
    "TyreThermalReport",
    "build_session_report",
    "compare_corner_inputs",
    "corner_input_profile",
    "detect_patterns",
]
