"""Spike B0 receiver: decode OpponentsBridge UDP packets and show gaps.

Run this WHILE driving a multi-car AC session (Practice/Race vs AI, >= 2 cars)
with the OpponentsBridge in-sim app enabled. It prints the player's position and
the gap (in lap-fraction) to the car ahead and behind - proving the opponent
data flows end to end before we build the production Phase B source.

    uv run python scripts/spikes/opponent_udp_probe.py
"""

from __future__ import annotations

import socket
import struct
import sys

_ADDR = ("127.0.0.1", 9997)
_HEADER = struct.Struct("<ii")
_CAR = struct.Struct("<ifif")


def _decode(data: bytes) -> tuple[int, list[dict[str, float]]]:
    focused, count = _HEADER.unpack_from(data, 0)
    offset = _HEADER.size
    cars: list[dict[str, float]] = []
    for _ in range(count):
        car_id, spline, lap, speed = _CAR.unpack_from(data, offset)
        offset += _CAR.size
        cars.append({"id": car_id, "spline": spline, "lap": lap, "speed": speed})
    return focused, cars


def _format(focused: int, cars: list[dict[str, float]]) -> str | None:
    me = next((c for c in cars if c["id"] == focused), None)
    if me is None or len(cars) < 2:
        return None
    for car in cars:
        car["progress"] = car["lap"] + car["spline"]  # total track progress
    ordered = sorted(cars, key=lambda c: c["progress"], reverse=True)
    idx = next(i for i, c in enumerate(ordered) if c["id"] == focused)
    parts = [f"P{idx + 1}/{len(ordered)}"]
    if idx > 0:
        ahead = ordered[idx - 1]
        gap = ahead["progress"] - me["progress"]
        parts.append(f"ahead +{gap:.3f} lap-frac (id {int(ahead['id'])})")
    if idx < len(ordered) - 1:
        behind = ordered[idx + 1]
        gap = me["progress"] - behind["progress"]
        parts.append(f"behind -{gap:.3f} lap-frac (id {int(behind['id'])})")
    return " | ".join(parts)


def main() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(_ADDR)
    host, port = _ADDR
    print(f"Listening on {host}:{port} - drive a multi-car session (Ctrl+C to stop).")
    try:
        while True:
            data, _ = sock.recvfrom(65535)
            line = _format(*_decode(data))
            if line is not None:
                print(line)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
