"""Parsers for individual car physics files (car.ini, drivetrain.ini)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.knowledge.car_physics.ini import get_float, get_int, parse_ini


class CarSpec(BaseModel):
    """General car data from ``car.ini``."""

    model_config = ConfigDict(frozen=True)

    screen_name: str = ""
    total_mass_kg: float = 0.0
    fuel_light_min_l: float = 0.0

    @classmethod
    def from_text(cls, text: str) -> CarSpec:
        data = parse_ini(text)
        info = data.get("INFO", {})
        basic = data.get("BASIC", {})
        graphics = data.get("GRAPHICS", {})
        return cls(
            screen_name=info.get("SCREEN_NAME", ""),
            total_mass_kg=get_float(basic, "TOTALMASS"),
            fuel_light_min_l=get_float(graphics, "FUEL_LIGHT_MIN_LITERS"),
        )


class Drivetrain(BaseModel):
    """Transmission data from ``drivetrain.ini``."""

    model_config = ConfigDict(frozen=True)

    traction_type: str = ""
    gear_count: int = 0
    gear_ratios: tuple[float, ...] = ()
    reverse_ratio: float = 0.0
    final_drive: float = 0.0

    @classmethod
    def from_text(cls, text: str) -> Drivetrain:
        data = parse_ini(text)
        traction = data.get("TRACTION", {})
        gears = data.get("GEARS", {})
        count = get_int(gears, "COUNT")
        ratios = tuple(
            get_float(gears, f"GEAR_{i}") for i in range(1, count + 1) if f"GEAR_{i}" in gears
        )
        return cls(
            traction_type=traction.get("TYPE", ""),
            gear_count=count,
            gear_ratios=ratios,
            reverse_ratio=get_float(gears, "GEAR_R"),
            final_drive=get_float(gears, "FINAL"),
        )

    def ratio_for(self, gear: int) -> float | None:
        """Total drive ratio (gear x final) for 1-based forward *gear*."""
        if not 1 <= gear <= len(self.gear_ratios) or self.final_drive == 0:
            return None
        return self.gear_ratios[gear - 1] * self.final_drive
