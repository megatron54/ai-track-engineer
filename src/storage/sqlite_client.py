"""Async SQLite metadata store for sessions and laps.

This keeps small, relational records that are awkward to query in a time-series
store: which sessions exist, and the laps (with timing and validity) within
each. Bulk per-frame telemetry lives in InfluxDB instead.
"""

from __future__ import annotations

import uuid
from types import TracebackType

import aiosqlite

from src.processing.models import Lap
from src.storage.schemas import (
    LAPS_DDL,
    LAPS_INDEX_DDL,
    SESSIONS_DDL,
    Session,
)


def _encode_sectors(sector_times_ms: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in sector_times_ms)


def _decode_sectors(raw: str) -> tuple[int, ...]:
    if not raw:
        return ()
    return tuple(int(part) for part in raw.split(","))


class SqliteStore:
    """A connection-scoped async store for session and lap metadata."""

    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the database and apply the schema (idempotent)."""
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        for ddl in (SESSIONS_DDL, LAPS_DDL, LAPS_INDEX_DDL):
            await self._db.execute(ddl)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection if open."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create_session(
        self, *, track: str, car: str, started_at: float, track_config: str = ""
    ) -> Session:
        """Insert a new session and return it (with a generated id)."""
        db = self._require_db()
        session = Session(
            id=uuid.uuid4().hex,
            started_at=started_at,
            track=track,
            car=car,
            track_config=track_config,
        )
        await db.execute(
            "INSERT INTO sessions (id, started_at, track, track_config, car) "
            "VALUES (?, ?, ?, ?, ?)",
            (session.id, session.started_at, session.track, session.track_config, session.car),
        )
        await db.commit()
        return session

    async def record_lap(self, session_id: str, lap: Lap) -> None:
        """Persist a completed lap for a session (idempotent per lap number)."""
        db = self._require_db()
        await db.execute(
            "INSERT OR REPLACE INTO laps "
            "(session_id, lap_number, lap_time_ms, sector_times_ms, valid, started_at, ended_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                lap.lap_number,
                lap.lap_time_ms,
                _encode_sectors(lap.sector_times_ms),
                int(lap.valid),
                lap.started_at,
                lap.ended_at,
            ),
        )
        await db.commit()

    async def laps_for_session(self, session_id: str) -> list[Lap]:
        """Return all laps for a session, ordered by lap number."""
        db = self._require_db()
        async with db.execute(
            "SELECT lap_number, lap_time_ms, sector_times_ms, valid, started_at, ended_at "
            "FROM laps WHERE session_id = ? ORDER BY lap_number",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_lap(row) for row in rows]

    async def best_lap(self, session_id: str) -> Lap | None:
        """Return the fastest *valid* lap of a session, or ``None``."""
        db = self._require_db()
        async with db.execute(
            "SELECT lap_number, lap_time_ms, sector_times_ms, valid, started_at, ended_at "
            "FROM laps WHERE session_id = ? AND valid = 1 "
            "ORDER BY lap_time_ms ASC LIMIT 1",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_lap(row) if row is not None else None

    async def get_session(self, session_id: str) -> Session | None:
        """Return a session by id, or ``None`` if it does not exist."""
        db = self._require_db()
        async with db.execute(
            "SELECT id, started_at, track, track_config, car FROM sessions WHERE id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Session(
            id=row["id"],
            started_at=row["started_at"],
            track=row["track"],
            track_config=row["track_config"],
            car=row["car"],
        )

    async def latest_session(self) -> Session | None:
        """Return the most recently started session, or ``None`` if none exist."""
        db = self._require_db()
        async with db.execute(
            "SELECT id, started_at, track, track_config, car "
            "FROM sessions ORDER BY started_at DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Session(
            id=row["id"],
            started_at=row["started_at"],
            track=row["track"],
            track_config=row["track_config"],
            car=row["car"],
        )

    # -- Context manager + helpers ----------------------------------------
    async def __aenter__(self) -> SqliteStore:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SqliteStore is not connected; call connect() first")
        return self._db

    @staticmethod
    def _row_to_lap(row: aiosqlite.Row) -> Lap:
        return Lap(
            lap_number=row["lap_number"],
            lap_time_ms=row["lap_time_ms"],
            sector_times_ms=_decode_sectors(row["sector_times_ms"]),
            valid=bool(row["valid"]),
            started_at=row["started_at"],
            ended_at=row["ended_at"],
        )
