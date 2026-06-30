"""Opponent telemetry over a local UDP bridge.

Assetto Corsa's base shared memory is player-only, so opponent positions come
from a tiny in-sim Python app (``tools/ac_app_opponents``) that broadcasts every
car's normalised spline position, lap and speed over UDP. This module decodes
that stream and turns it into the time gap to the cars immediately ahead and
behind, which feeds :class:`~src.strategy.gap_manager.GapManager`.

Wire format (little-endian), matching ``OpponentsBridge.py``::

    int32   focused_car_id
    int32   car_count
    car_count * { int32 id; float32 spline; int32 lap; float32 speed_kmh }
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable
from dataclasses import dataclass

from src.observability import get_logger

_log = get_logger("telemetry.opponents")

_HEADER = struct.Struct("<ii")
_CAR = struct.Struct("<ifif")

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 9997
# Below this speed a time gap is meaningless (car stopped or in the pits).
_MIN_SPEED_KMH = 10.0
# A car within half a lap ahead is "ahead"; beyond that it is "behind" (almost a
# full lap in front, i.e. right behind us on track).
_AHEAD_HORIZON = 0.5


@dataclass(frozen=True)
class OpponentCar:
    """One car's position in the opponent stream."""

    car_id: int
    spline: float  # normalised track position [0, 1)
    lap: int
    speed_kmh: float


@dataclass(frozen=True)
class OpponentSnapshot:
    """All cars in a single broadcast frame, plus the focused (player) car id."""

    focused_id: int
    cars: tuple[OpponentCar, ...]

    def focused(self) -> OpponentCar | None:
        """Return the focused (player) car, or ``None`` if it is not present."""
        return next((c for c in self.cars if c.car_id == self.focused_id), None)


def decode_packet(data: bytes) -> OpponentSnapshot:
    """Decode a UDP packet into an :class:`OpponentSnapshot`.

    Raises:
        ValueError: if the packet is truncated or declares a negative car count.
    """
    if len(data) < _HEADER.size:
        raise ValueError("packet too short for header")
    focused, count = _HEADER.unpack_from(data, 0)
    if count < 0:
        raise ValueError(f"negative car count: {count}")
    expected = _HEADER.size + count * _CAR.size
    if len(data) < expected:
        raise ValueError(f"packet too short: need {expected} bytes, got {len(data)}")
    cars = []
    offset = _HEADER.size
    for _ in range(count):
        car_id, spline, lap, speed = _CAR.unpack_from(data, offset)
        offset += _CAR.size
        cars.append(OpponentCar(car_id=car_id, spline=spline, lap=lap, speed_kmh=speed))
    return OpponentSnapshot(focused_id=focused, cars=tuple(cars))


def _gap_seconds(
    track_fraction: float, track_spline_length: float, trailing_speed_kmh: float
) -> float | None:
    """Convert a track-position gap (lap fraction) to a time gap in seconds."""
    if trailing_speed_kmh < _MIN_SPEED_KMH or track_fraction <= 0.0:
        return None
    distance_m = track_fraction * track_spline_length
    speed_ms = trailing_speed_kmh / 3.6
    return distance_m / speed_ms


def gaps_seconds(
    snapshot: OpponentSnapshot, track_spline_length: float
) -> tuple[float | None, float | None]:
    """Return the time gap (seconds) to the nearest car ahead and behind.

    Gaps come from on-track proximity (normalised spline, wrapping at the
    start/finish line), independent of race order. The gap to the car ahead uses
    the player's speed (we are chasing it); the gap to the car behind uses that
    car's speed (it is chasing us). A side is ``None`` when there is no car there,
    when the track length is unknown, or when the trailing car is too slow for a
    time gap to be meaningful.
    """
    me = snapshot.focused()
    if me is None or track_spline_length <= 0.0:
        return (None, None)

    ahead_car: OpponentCar | None = None
    ahead_frac = 0.0
    behind_car: OpponentCar | None = None
    behind_frac = 0.0
    for car in snapshot.cars:
        if car.car_id == me.car_id:
            continue
        forward = (car.spline - me.spline) % 1.0
        if forward <= 0.0:
            continue
        if forward <= _AHEAD_HORIZON:
            if ahead_car is None or forward < ahead_frac:
                ahead_car, ahead_frac = car, forward
        else:
            behind = 1.0 - forward
            if behind_car is None or behind < behind_frac:
                behind_car, behind_frac = car, behind

    gap_ahead = (
        _gap_seconds(ahead_frac, track_spline_length, me.speed_kmh)
        if ahead_car is not None
        else None
    )
    gap_behind = (
        _gap_seconds(behind_frac, track_spline_length, behind_car.speed_kmh)
        if behind_car is not None
        else None
    )
    return (gap_ahead, gap_behind)


class _OpponentProtocol(asyncio.DatagramProtocol):
    """Decodes incoming datagrams and hands snapshots to a store callback."""

    def __init__(self, store: Callable[[OpponentSnapshot], None]) -> None:
        self._store = store

    def datagram_received(self, data: bytes, addr: object) -> None:
        try:
            snapshot = decode_packet(data)
        except ValueError as exc:
            _log.warning("opponent-packet-malformed", error=str(exc))
            return
        self._store(snapshot)


class OpponentReceiver:
    """Async UDP listener holding the latest opponent snapshot (latest-wins).

    No queue is kept: only the most recent frame matters for live gaps, so a slow
    consumer never falls behind. Bind the socket with :meth:`start` and release it
    with :meth:`close`; read the freshest data with :meth:`latest`.
    """

    def __init__(self, host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._latest: OpponentSnapshot | None = None
        self._transport: asyncio.BaseTransport | None = None

    def latest(self) -> OpponentSnapshot | None:
        """Return the most recently received snapshot, or ``None``."""
        return self._latest

    def _store(self, snapshot: OpponentSnapshot) -> None:
        self._latest = snapshot

    def _make_protocol(self) -> _OpponentProtocol:
        return _OpponentProtocol(self._store)

    async def start(self) -> None:
        """Bind the UDP socket and begin receiving (raises ``OSError`` on bind failure)."""
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            self._make_protocol, local_addr=(self.host, self.port)
        )
        self._transport = transport

    def close(self) -> None:
        """Release the UDP socket. Idempotent."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None
