"""Read recorded-session CSVs into typed samples for offline ML work.

The dashboard's :class:`~src.storage.session_recorder.SessionRecorder` writes one
CSV row per telemetry frame. This module reads back just the channels the ML
lap-selection and corner-feature steps need, as immutable
:class:`TelemetrySample` objects, and groups them by lap.

It uses only the standard library so it runs in the base install (no pandas or
numpy needed) - consistent with :mod:`src.ml.features`; only the training script
pulls in the heavier ML extras.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_TYRE_TEMP_COLUMNS = ("tyre_temp_fl", "tyre_temp_fr", "tyre_temp_rl", "tyre_temp_rr")


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    """One recorded telemetry frame, reduced to the channels ML selection needs.

    ``lap`` is Assetto Corsa's *completed-laps* counter at capture time, so all
    frames of the out-lap carry ``lap == 0`` and each subsequent flying lap is a
    contiguous run sharing one ``lap`` value. ``lap_pos`` is the normalised
    ``[0, 1)`` position around the track.
    """

    lap: int
    lap_pos: float
    timestamp: float
    speed_kmh: float
    gear: int
    brake: float
    g_lat: float
    tyre_temp_avg: float


def _sample_from_row(row: dict[str, str]) -> TelemetrySample:
    temps = [float(row[col]) for col in _TYRE_TEMP_COLUMNS]
    return TelemetrySample(
        lap=int(row["lap"]),
        lap_pos=float(row["lap_pos"]),
        timestamp=float(row["timestamp"]),
        speed_kmh=float(row["speed_kmh"]),
        gear=int(row["gear"]),
        brake=float(row["brake"]),
        g_lat=float(row["g_lat"]),
        tyre_temp_avg=sum(temps) / len(temps),
    )


def read_samples(path: str | Path) -> list[TelemetrySample]:
    """Read a recorded-session CSV into a list of samples, in file (time) order."""
    with open(path, newline="", encoding="utf-8") as handle:
        return [_sample_from_row(row) for row in csv.DictReader(handle)]


def group_by_lap(
    samples: Iterable[TelemetrySample],
) -> dict[int, list[TelemetrySample]]:
    """Group samples by their lap index, preserving per-lap (time) order."""
    laps: dict[int, list[TelemetrySample]] = defaultdict(list)
    for sample in samples:
        laps[sample.lap].append(sample)
    return dict(laps)
