"""Validate the live shared-memory layout against a running Assetto Corsa.

Run this with Assetto Corsa in a session (drive or watch a replay), then:

    uv run python scripts/validate_shm.py

It connects to the three shared-memory pages, reads one frame, and prints key
fields plus a few sanity checks (RPM within limits, normalised position in
[0, 1], non-empty track name). This is the on-hardware counterpart to the
unit tests that validate the struct layout in memory.
"""

from __future__ import annotations

import sys

from src.telemetry import SharedMemoryTelemetrySource
from src.telemetry.shm_structs import GRAPHICS_SIZE, PHYSICS_SIZE, STATIC_SIZE


def main() -> int:
    print(f"Page sizes -> physics={PHYSICS_SIZE} graphics={GRAPHICS_SIZE} static={STATIC_SIZE}")
    source = SharedMemoryTelemetrySource()
    try:
        static_info = source.connect()
    except Exception as exc:  # noqa: BLE001 - report any connection failure clearly
        print(f"Failed to connect to shared memory: {exc}")
        return 1

    frame = source.read_frame()
    source.close()

    physics, graphics = frame.physics, frame.graphics
    print("\n=== Static ===")
    print(f"  track={static_info.track!r} car={static_info.car_model!r}")
    print(f"  max_rpm={static_info.max_rpm} max_fuel={static_info.max_fuel}")
    print(
        f"  track_length={static_info.track_spline_length:.1f} "
        f"sectors={static_info.sector_count}"
    )
    print("\n=== Graphics ===")
    print(f"  status={graphics.status.name} session={graphics.session_type.name}")
    print(f"  norm_pos={graphics.normalized_car_position:.4f} lap={graphics.completed_laps}")
    print(f"  current_time={graphics.current_time!r}")
    print("\n=== Physics ===")
    print(f"  speed={physics.speed_kmh:.1f} km/h rpm={physics.rpm} gear={physics.gear_label}")
    print(f"  tyre_core_temp={physics.tyre_core_temp.as_tuple()}")

    checks = {
        "track name present": bool(static_info.track),
        "rpm within limits": 0 <= physics.rpm <= max(1, static_info.max_rpm) + 500,
        "normalised position in [0, 1]": 0.0 <= graphics.normalized_car_position <= 1.0,
    }
    print("\n=== Sanity checks ===")
    all_ok = True
    for label, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")
        all_ok = all_ok and ok

    if graphics.status.name != "LIVE":
        print("\nNote: simulator is not LIVE. Start a session for meaningful values.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
