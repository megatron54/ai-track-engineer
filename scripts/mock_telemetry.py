"""Print mock telemetry to the console for offline development.

Usage:
    uv run python scripts/mock_telemetry.py --seconds 5 --speed 2

``--speed`` accelerates simulated time (2 = twice real time). This script needs
no running game and is handy for exercising the dashboard or analysis layers.
"""

from __future__ import annotations

import argparse
import asyncio

from src.observability import configure_logging, get_logger
from src.telemetry import MockTelemetrySource


async def _run(seconds: float, hz: int, speed: float) -> None:
    log = get_logger("mock")
    source = MockTelemetrySource()
    static_info = source.connect()
    log.info("connected", track=static_info.track, car=static_info.car_model)
    try:
        max_frames = int(hz * seconds)
        emitted = 0
        async for frame in source.stream(int(hz * speed), max_frames=max_frames):
            emitted += 1
            if emitted % max(1, int(hz * speed) // 10) == 0:
                physics = frame.physics
                log.info(
                    "frame",
                    t=round(frame.timestamp, 2),
                    lap_pos=round(frame.graphics.normalized_car_position, 3),
                    speed_kmh=round(physics.speed_kmh, 1),
                    rpm=physics.rpm,
                    gear=physics.gear_label,
                    fuel=round(physics.fuel, 2),
                )
    finally:
        source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Print mock Assetto Corsa telemetry.")
    parser.add_argument("--seconds", type=float, default=5.0, help="Simulated seconds.")
    parser.add_argument("--hz", type=int, default=60, help="Base sample rate.")
    parser.add_argument("--speed", type=float, default=1.0, help="Time multiplier.")
    args = parser.parse_args()

    configure_logging("INFO")
    asyncio.run(_run(args.seconds, args.hz, args.speed))


if __name__ == "__main__":
    main()
