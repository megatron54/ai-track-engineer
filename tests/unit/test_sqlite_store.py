"""Tests for the SQLite metadata store."""

from __future__ import annotations

import pytest
from src.processing.models import Lap
from src.storage.sqlite_client import SqliteStore


@pytest.fixture
async def store() -> SqliteStore:
    store = SqliteStore(":memory:")
    await store.connect()
    return store


async def test_create_and_get_session(store: SqliteStore) -> None:
    session = await store.create_session(
        track="ks_laguna_seca", car="ks_ferrari_488_gt3", started_at=100.0
    )
    fetched = await store.get_session(session.id)
    assert fetched == session
    assert fetched is not None
    assert fetched.track == "ks_laguna_seca"


async def test_get_missing_session_returns_none(store: SqliteStore) -> None:
    assert await store.get_session("does-not-exist") is None


async def test_record_and_list_laps(store: SqliteStore) -> None:
    session = await store.create_session(track="t", car="c", started_at=0.0)
    await store.record_lap(
        session.id,
        Lap(lap_number=1, lap_time_ms=90_000, sector_times_ms=(30_000, 30_000, 30_000)),
    )
    await store.record_lap(session.id, Lap(lap_number=2, lap_time_ms=88_500, valid=True))

    laps = await store.laps_for_session(session.id)
    assert [lap.lap_number for lap in laps] == [1, 2]
    assert laps[0].sector_times_ms == (30_000, 30_000, 30_000)
    assert laps[1].lap_time_ms == 88_500


async def test_best_lap_ignores_invalid_laps(store: SqliteStore) -> None:
    session = await store.create_session(track="t", car="c", started_at=0.0)
    await store.record_lap(session.id, Lap(lap_number=1, lap_time_ms=85_000, valid=False))
    await store.record_lap(session.id, Lap(lap_number=2, lap_time_ms=90_000, valid=True))
    await store.record_lap(session.id, Lap(lap_number=3, lap_time_ms=89_000, valid=True))

    best = await store.best_lap(session.id)
    assert best is not None
    assert best.lap_number == 3
    assert best.lap_time_ms == 89_000


async def test_best_lap_none_when_no_valid_laps(store: SqliteStore) -> None:
    session = await store.create_session(track="t", car="c", started_at=0.0)
    await store.record_lap(session.id, Lap(lap_number=1, lap_time_ms=85_000, valid=False))
    assert await store.best_lap(session.id) is None


async def test_record_lap_is_idempotent_per_lap_number(store: SqliteStore) -> None:
    session = await store.create_session(track="t", car="c", started_at=0.0)
    await store.record_lap(session.id, Lap(lap_number=1, lap_time_ms=90_000))
    # Re-recording the same lap number replaces, not duplicates.
    await store.record_lap(session.id, Lap(lap_number=1, lap_time_ms=88_000))
    laps = await store.laps_for_session(session.id)
    assert len(laps) == 1
    assert laps[0].lap_time_ms == 88_000


async def test_operations_require_connection() -> None:
    store = SqliteStore(":memory:")
    with pytest.raises(RuntimeError, match="not connected"):
        await store.create_session(track="t", car="c", started_at=0.0)


async def test_context_manager_connects_and_closes() -> None:
    async with SqliteStore(":memory:") as store:
        session = await store.create_session(track="t", car="c", started_at=0.0)
        assert await store.get_session(session.id) is not None


async def test_latest_session_returns_most_recent(store: SqliteStore) -> None:
    await store.create_session(track="t1", car="c", started_at=100.0)
    newest = await store.create_session(track="t2", car="c", started_at=200.0)
    latest = await store.latest_session()
    assert latest is not None
    assert latest.id == newest.id
    assert latest.track == "t2"


async def test_latest_session_none_when_empty(store: SqliteStore) -> None:
    assert await store.latest_session() is None
