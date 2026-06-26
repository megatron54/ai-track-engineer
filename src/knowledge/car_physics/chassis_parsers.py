"""Parsers for aero, brakes and suspension car physics files."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.knowledge.car_physics.ini import get_float, parse_ini


class AeroWing(BaseModel):
    """A single aerodynamic surface (body, front wing, rear wing)."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    chord: float = 0.0
    span: float = 0.0
    angle: float = 0.0
    cl_gain: float = 0.0
    cd_gain: float = 0.0


class AeroSpec(BaseModel):
    """Aerodynamic configuration from ``aero.ini``."""

    model_config = ConfigDict(frozen=True)

    wings: tuple[AeroWing, ...] = ()

    @classmethod
    def from_text(cls, text: str) -> AeroSpec:
        data = parse_ini(text)
        wings: list[AeroWing] = []
        for section_name, section in data.items():
            if not section_name.startswith("WING_"):
                continue
            wings.append(
                AeroWing(
                    name=section.get("NAME", ""),
                    chord=get_float(section, "CHORD"),
                    span=get_float(section, "SPAN"),
                    angle=get_float(section, "ANGLE"),
                    cl_gain=get_float(section, "CL_GAIN"),
                    cd_gain=get_float(section, "CD_GAIN"),
                )
            )
        return cls(wings=tuple(wings))


class BrakeSpec(BaseModel):
    """Brake system data from ``brakes.ini``."""

    model_config = ConfigDict(frozen=True)

    max_torque: float = 0.0
    front_share: float = 0.0

    @classmethod
    def from_text(cls, text: str) -> BrakeSpec:
        data = parse_ini(text)
        section = data.get("DATA", {})
        return cls(
            max_torque=get_float(section, "MAX_TORQUE"),
            front_share=get_float(section, "FRONT_SHARE"),
        )


class SuspensionAxle(BaseModel):
    """Suspension parameters for one axle."""

    model_config = ConfigDict(frozen=True)

    spring_rate: float = 0.0
    toe_out: float = 0.0
    static_camber: float = 0.0
    track_width: float = 0.0


class SuspensionSpec(BaseModel):
    """Suspension configuration from ``suspensions.ini``."""

    model_config = ConfigDict(frozen=True)

    wheelbase: float = 0.0
    cg_location: float = 0.0
    arb_front: float = 0.0
    arb_rear: float = 0.0
    front: SuspensionAxle = SuspensionAxle()
    rear: SuspensionAxle = SuspensionAxle()

    @classmethod
    def from_text(cls, text: str) -> SuspensionSpec:
        data = parse_ini(text)
        basic = data.get("BASIC", {})
        arb = data.get("ARB", {})

        def _axle(key: str) -> SuspensionAxle:
            section = data.get(key, {})
            return SuspensionAxle(
                spring_rate=get_float(section, "SPRING_RATE"),
                toe_out=get_float(section, "TOE_OUT"),
                static_camber=get_float(section, "STATIC_CAMBER"),
                track_width=get_float(section, "TRACK"),
            )

        return cls(
            wheelbase=get_float(basic, "WHEELBASE"),
            cg_location=get_float(basic, "CG_LOCATION"),
            arb_front=get_float(arb, "FRONT"),
            arb_rear=get_float(arb, "REAR"),
            front=_axle("FRONT"),
            rear=_axle("REAR"),
        )
