"""Tests for the opponent UDP source: decode, gap math, and the receiver."""

from __future__ import annotations

import struct

import pytest
from src.telemetry.opponents import (
    OpponentCar,
    OpponentReceiver,
    OpponentSnapshot,
    decode_packet,
    gaps_seconds,
)

_HEADER = struct.Struct("<ii")
_CAR = struct.Struct("<ifif")
_LEN = 5000.0  # track spline length (metres)


def _packet(focused: int, cars: list[tuple[int, float, int, float]]) -> bytes:
    out = _HEADER.pack(focused, len(cars))
    for car_id, spline, lap, speed in cars:
        out += _CAR.pack(car_id, spline, lap, speed)
    return out


# --------------------------------------------------------------------------- #
# decode_packet
# --------------------------------------------------------------------------- #
def test_decode_round_trip() -> None:
    snap = decode_packet(_packet(0, [(0, 0.25, 1, 200.0), (3, 0.30, 1, 210.0)]))
    assert snap.focused_id == 0
    assert len(snap.cars) == 2
    first = snap.cars[0]
    assert first.car_id == 0
    assert first.spline == pytest.approx(0.25)
    assert first.lap == 1
    assert first.speed_kmh == pytest.approx(200.0)
    assert snap.cars[1].car_id == 3


def test_decode_empty_grid() -> None:
    snap = decode_packet(_packet(0, []))
    assert snap.focused_id == 0
    assert snap.cars == ()


def test_decode_too_short_for_header() -> None:
    with pytest.raises(ValueError, match="header"):
        decode_packet(b"\x00\x00")


def test_decode_truncated_body() -> None:
    truncated = _packet(0, [(0, 0.1, 0, 100.0)])[:-4]
    with pytest.raises(ValueError, match="too short"):
        decode_packet(truncated)


def test_decode_negative_count() -> None:
    with pytest.raises(ValueError, match="negative car count"):
        decode_packet(_HEADER.pack(0, -1))


def test_focused_lookup() -> None:
    snap = decode_packet(_packet(3, [(0, 0.1, 0, 100.0), (3, 0.2, 0, 110.0)]))
    focused = snap.focused()
    assert focused is not None
    assert focused.car_id == 3


# --------------------------------------------------------------------------- #
# gaps_seconds
# --------------------------------------------------------------------------- #
def test_gap_ahead_and_behind() -> None:
    snap = OpponentSnapshot(
        focused_id=0,
        cars=(
            OpponentCar(0, 0.50, 1, 180.0),  # me
            OpponentCar(1, 0.55, 1, 200.0),  # ahead by 0.05 lap
            OpponentCar(2, 0.45, 1, 170.0),  # behind by 0.05 lap
        ),
    )
    ahead, behind = gaps_seconds(snap, _LEN)
    assert ahead == pytest.approx(0.05 * _LEN / (180.0 / 3.6))  # trailing = me
    assert behind == pytest.approx(0.05 * _LEN / (170.0 / 3.6))  # trailing = behind car


def test_gap_wraparound_across_start_finish() -> None:
    snap = OpponentSnapshot(
        focused_id=0,
        cars=(
            OpponentCar(0, 0.98, 2, 100.0),
            OpponentCar(1, 0.02, 3, 100.0),  # forward 0.04, just ahead over the line
        ),
    )
    ahead, behind = gaps_seconds(snap, _LEN)
    assert ahead == pytest.approx(0.04 * _LEN / (100.0 / 3.6))
    assert behind is None  # the only other car is ahead


def test_gap_single_car_behind() -> None:
    snap = OpponentSnapshot(
        focused_id=0,
        cars=(
            OpponentCar(0, 0.10, 1, 120.0),
            OpponentCar(1, 0.80, 1, 150.0),  # forward 0.70 > 0.5 -> behind by 0.30
        ),
    )
    ahead, behind = gaps_seconds(snap, _LEN)
    assert ahead is None
    assert behind == pytest.approx(0.30 * _LEN / (150.0 / 3.6))


def test_gap_picks_nearest_on_each_side() -> None:
    snap = OpponentSnapshot(
        focused_id=0,
        cars=(
            OpponentCar(0, 0.50, 1, 200.0),
            OpponentCar(1, 0.60, 1, 200.0),  # ahead 0.10
            OpponentCar(2, 0.53, 1, 200.0),  # ahead 0.03 (nearer)
            OpponentCar(3, 0.40, 1, 200.0),  # behind 0.10
            OpponentCar(4, 0.48, 1, 200.0),  # behind 0.02 (nearer)
        ),
    )
    ahead, behind = gaps_seconds(snap, _LEN)
    assert ahead == pytest.approx(0.03 * _LEN / (200.0 / 3.6))
    assert behind == pytest.approx(0.02 * _LEN / (200.0 / 3.6))


def test_gap_slow_car_returns_none() -> None:
    snap = OpponentSnapshot(
        focused_id=0,
        cars=(
            OpponentCar(0, 0.50, 1, 0.0),  # me stopped -> no ahead gap
            OpponentCar(1, 0.55, 1, 5.0),  # behind-side car crawling -> no behind gap
            OpponentCar(2, 0.45, 1, 5.0),
        ),
    )
    assert gaps_seconds(snap, _LEN) == (None, None)


def test_gap_no_opponents() -> None:
    snap = OpponentSnapshot(focused_id=0, cars=(OpponentCar(0, 0.5, 1, 100.0),))
    assert gaps_seconds(snap, _LEN) == (None, None)


def test_gap_focused_missing() -> None:
    snap = OpponentSnapshot(focused_id=9, cars=(OpponentCar(0, 0.5, 1, 100.0),))
    assert gaps_seconds(snap, _LEN) == (None, None)


def test_gap_unknown_track_length() -> None:
    snap = OpponentSnapshot(
        focused_id=0,
        cars=(OpponentCar(0, 0.50, 1, 180.0), OpponentCar(1, 0.55, 1, 180.0)),
    )
    assert gaps_seconds(snap, 0.0) == (None, None)


# --------------------------------------------------------------------------- #
# OpponentReceiver
# --------------------------------------------------------------------------- #
def test_receiver_decodes_and_keeps_latest() -> None:
    recv = OpponentReceiver()
    assert recv.latest() is None
    proto = recv._make_protocol()  # noqa: SLF001 - exercise the receive path

    proto.datagram_received(_packet(0, [(0, 0.10, 0, 100.0)]), ("127.0.0.1", 1))
    first = recv.latest()
    assert first is not None
    assert first.cars[0].spline == pytest.approx(0.10)

    proto.datagram_received(_packet(0, [(0, 0.90, 0, 120.0)]), ("127.0.0.1", 1))
    latest = recv.latest()
    assert latest is not None
    assert latest.cars[0].spline == pytest.approx(0.90)  # latest-wins


def test_receiver_ignores_malformed_packet() -> None:
    recv = OpponentReceiver()
    proto = recv._make_protocol()  # noqa: SLF001
    proto.datagram_received(b"\x00\x00", ("127.0.0.1", 1))
    assert recv.latest() is None
