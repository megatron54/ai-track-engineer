"""OpponentsBridge - Assetto Corsa in-sim app (PROTOTYPE / SPIKE B0).

Reads every car's normalised spline position, lap and speed from AC's Python
API and broadcasts them over UDP to localhost, so AI-TrackEngineer can compute
gaps to the cars ahead and behind. Works in single-player (vs AI) and online
(client side).

Install:
    Copy this folder to  <AssettoCorsa>/apps/python/OpponentsBridge/
    so the file is        OpponentsBridge/OpponentsBridge.py
    then enable "OpponentsBridge" in AC's in-game app list.

NOTE: Assetto Corsa embeds Python 3.3 - keep this file 3.3 compatible
(no f-strings, no modern typing).
"""

import socket
import struct

import ac
import acsys

_UDP_ADDR = ("127.0.0.1", 9997)
_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_label = 0


def acMain(ac_version):  # noqa: N802 (AC entry point name is fixed)
    global _label
    app = ac.newApp("OpponentsBridge")
    ac.setSize(app, 230, 60)
    _label = ac.addLabel(app, "OpponentsBridge: starting...")
    ac.setPosition(_label, 8, 30)
    return "OpponentsBridge"


def acUpdate(delta_t):  # noqa: N802 (AC entry point name is fixed)
    try:
        count = ac.getCarsCount()
        focused = ac.getFocusedCar()
        cars = []
        for car_id in range(count):
            if ac.isConnected(car_id) == 0:
                continue
            spline = ac.getCarState(car_id, acsys.CS.NormalizedSplinePosition)
            laps = ac.getCarState(car_id, acsys.CS.LapCount)
            speed = ac.getCarState(car_id, acsys.CS.SpeedKMH)
            cars.append((car_id, float(spline), int(laps), float(speed)))

        # Wire format (little-endian):
        #   int focused_car_id
        #   int car_count
        #   car_count * { int id; float spline; int lap; float speed_kmh }
        payload = struct.pack("<ii", int(focused), len(cars))
        for car_id, spline, laps, speed in cars:
            payload += struct.pack("<ifif", car_id, spline, laps, speed)
        _sock.sendto(payload, _UDP_ADDR)
        ac.setText(_label, "OpponentsBridge: %d cars" % len(cars))
    except Exception as exc:  # keep the app alive; surface errors on the label
        ac.setText(_label, "OpponentsBridge err: %s" % exc)
