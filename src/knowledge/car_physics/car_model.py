"""Unified car physics model combining the individual data files.

Loads ``power.lut``, ``car.ini`` and ``drivetrain.ini`` from a car's unpacked
``data`` directory into one object the Setup Lab can reason about (mass, power,
gearing, power-to-weight, a rough top-speed estimate).
"""

from __future__ import annotations

import math
from pathlib import Path

from src.knowledge.car_physics.car_parser import CarSpec, Drivetrain
from src.knowledge.car_physics.chassis_parsers import AeroSpec, BrakeSpec, SuspensionSpec
from src.knowledge.car_physics.power_parser import PowerCurve

_RPM_TO_RAD_S = 2.0 * math.pi / 60.0


class CarPhysicsModel:
    """Combined view of a car's physics data."""

    def __init__(
        self,
        car: CarSpec,
        drivetrain: Drivetrain,
        power: PowerCurve | None,
        aero: AeroSpec | None = None,
        brakes: BrakeSpec | None = None,
        suspension: SuspensionSpec | None = None,
    ) -> None:
        self.car = car
        self.drivetrain = drivetrain
        self.power = power
        self.aero = aero
        self.brakes = brakes
        self.suspension = suspension

    @classmethod
    def from_dir(cls, data_dir: str | Path) -> CarPhysicsModel:
        """Load the model from a car's unpacked ``data`` directory."""
        path = Path(data_dir)
        car = CarSpec.from_text(_read(path / "car.ini"))
        drivetrain = Drivetrain.from_text(_read(path / "drivetrain.ini"))
        power_text = _read(path / "power.lut")
        power = PowerCurve.from_text(power_text) if power_text else None
        aero_text = _read(path / "aero.ini")
        aero = AeroSpec.from_text(aero_text) if aero_text else None
        brakes_text = _read(path / "brakes.ini")
        brakes = BrakeSpec.from_text(brakes_text) if brakes_text else None
        susp_text = _read(path / "suspensions.ini")
        suspension = SuspensionSpec.from_text(susp_text) if susp_text else None
        return cls(car, drivetrain, power, aero, brakes, suspension)

    @property
    def peak_power_hp(self) -> float | None:
        """Peak power in metric horsepower, or ``None`` if no power curve."""
        return None if self.power is None else self.power.peak_power.power_hp

    @property
    def power_to_weight(self) -> float | None:
        """Power-to-weight ratio in hp per tonne, or ``None`` if unknown."""
        if self.peak_power_hp is None or self.car.total_mass_kg <= 0:
            return None
        return self.peak_power_hp / (self.car.total_mass_kg / 1000.0)

    def top_speed_kmh(self, tyre_radius_m: float) -> float | None:
        """Estimate top speed (km/h) at peak power in the highest gear.

        A first-order estimate ignoring aero drag: it reflects gearing and
        engine speed, which is what the Setup Lab needs for gearing advice.
        """
        if self.power is None or tyre_radius_m <= 0 or self.drivetrain.gear_count == 0:
            return None
        ratio = self.drivetrain.ratio_for(self.drivetrain.gear_count)
        if ratio is None or ratio == 0:
            return None
        wheel_rad_s = (self.power.peak_power.rpm * _RPM_TO_RAD_S) / ratio
        return wheel_rad_s * tyre_radius_m * 3.6


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")
