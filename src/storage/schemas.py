"""Storage schemas and metadata models.

The metadata store keeps lightweight, queryable records (sessions and laps) in
SQLite, while the bulk time-series telemetry goes to InfluxDB. These models and
DDL statements describe the SQLite side.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# DDL for the metadata tables. Applied idempotently on connect.
SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    started_at    REAL NOT NULL,
    track         TEXT NOT NULL,
    track_config  TEXT NOT NULL DEFAULT '',
    car           TEXT NOT NULL
)
"""

LAPS_DDL = """
CREATE TABLE IF NOT EXISTS laps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    lap_number      INTEGER NOT NULL,
    lap_time_ms     INTEGER NOT NULL,
    sector_times_ms TEXT NOT NULL DEFAULT '',
    valid           INTEGER NOT NULL DEFAULT 1,
    started_at      REAL NOT NULL DEFAULT 0,
    ended_at        REAL NOT NULL DEFAULT 0,
    UNIQUE(session_id, lap_number)
)
"""

LAPS_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_laps_session ON laps(session_id)
"""


class Session(BaseModel):
    """A recorded driving session (one track + car combination)."""

    model_config = ConfigDict(frozen=True)

    id: str
    started_at: float
    track: str
    car: str
    track_config: str = ""
