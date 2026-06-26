"""Record telemetry frames to CSV files for offline analysis and ML training.

Each session produces one CSV file under ``data/sessions/``. The recorder
converts :class:`~src.telemetry.models.TelemetryFrame` objects into flat rows
with all the channels an ML pipeline or post-session analyser would need.

CSV was chosen over Parquet because it needs **zero** extra dependencies
(no pyarrow/fastparquet) and is human-readable. A future upgrade to Parquet
is a drop-in change in :meth:`SessionRecorder.close`.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from src.telemetry.models import TelemetryFrame

_COLUMNS = [
    "timestamp",
    "lap",
    "lap_pos",
    "speed_kmh",
    "rpm",
    "gear",
    "gas",
    "brake",
    "clutch",
    "steer_angle",
    "fuel",
    "g_lat",
    "g_lon",
    "g_vert",
    "tyre_temp_fl",
    "tyre_temp_fr",
    "tyre_temp_rl",
    "tyre_temp_rr",
    "tyre_press_fl",
    "tyre_press_fr",
    "tyre_press_rl",
    "tyre_press_rr",
    "tyre_wear_fl",
    "tyre_wear_fr",
    "tyre_wear_rl",
    "tyre_wear_rr",
    "brake_temp_fl",
    "brake_temp_fr",
    "brake_temp_rl",
    "brake_temp_rr",
    "brake_bias",
    "car_x",
    "car_z",
    "sector",
    "position",
    "delta",
]


def _row(frame: TelemetryFrame, *, delta: float | None = None) -> list[object]:
    p = frame.physics
    g = frame.graphics
    return [
        round(frame.timestamp, 4),
        g.completed_laps,
        round(g.normalized_car_position, 5),
        round(p.speed_kmh, 2),
        p.rpm,
        p.gear,
        round(p.gas, 4),
        round(p.brake, 4),
        round(p.clutch, 4),
        round(p.steer_angle, 2),
        round(p.fuel, 3),
        round(p.g_force_lateral, 4),
        round(p.g_force_longitudinal, 4),
        round(p.g_force_vertical, 4),
        *[round(v, 2) for v in p.tyre_core_temp.as_tuple()],
        *[round(v, 3) for v in p.tyre_pressure.as_tuple()],
        *[round(v, 2) for v in p.tyre_wear.as_tuple()],
        *[round(v, 1) for v in p.brake_temp.as_tuple()],
        round(p.brake_bias, 4),
        round(g.car_coordinates[0], 2),
        round(g.car_coordinates[2], 2),
        g.current_sector_index,
        g.position,
        round(delta, 4) if delta is not None else "",
    ]


class SessionRecorder:
    """Write telemetry frames to a CSV file, one row per frame.

    Usage::

        recorder = SessionRecorder(Path("data/sessions"), "spa", "f2004", "abc123")
        recorder.open()
        recorder.write(frame, delta=0.12)
        ...
        recorder.close()   # flushes and finalises the file
    """

    def __init__(
        self, base_dir: Path, track: str, car: str, session_id: str
    ) -> None:
        self._path = base_dir / f"{track}_{car}_{session_id}.csv"
        self._buf: io.TextIOWrapper | None = None
        self._writer: csv.writer | None = None  # type: ignore[valid-type]
        self._rows = 0

    @property
    def path(self) -> Path:
        return self._path

    @property
    def rows_written(self) -> int:
        return self._rows

    def open(self) -> None:
        """Create the file and write the header row."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._buf = open(self._path, "w", newline="", encoding="utf-8")  # noqa: SIM115
        self._writer = csv.writer(self._buf)
        self._writer.writerow(_COLUMNS)

    def write(self, frame: TelemetryFrame, *, delta: float | None = None) -> None:
        """Append one frame as a CSV row."""
        if self._writer is None:
            raise RuntimeError("recorder is not open; call open() first")
        self._writer.writerow(_row(frame, delta=delta))
        self._rows += 1

    def close(self) -> None:
        """Flush and close the file."""
        if self._buf is not None:
            self._buf.close()
            self._buf = None
            self._writer = None

    def __enter__(self) -> SessionRecorder:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
