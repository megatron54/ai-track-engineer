"""Validated, immutable domain models for Assetto Corsa telemetry.

These Pydantic models are the application's telemetry contract. Everything above
the capture layer consumes these — never the raw ctypes structures. Models are
frozen to enforce the project's immutability principle: a frame, once captured,
never mutates.

Note on engine temperatures: the Assetto Corsa shared-memory API does **not**
expose water/oil temperature or oil pressure. The engine monitor therefore works
from the signals that *are* available (RPM vs. max RPM, turbo boost, tyre/brake
temperatures). See :mod:`src.telemetry.shm_structs` for the raw layout.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from src.telemetry.shm_structs import ACFlagType, ACSessionType, ACStatus

_GEAR_LABELS = {0: "R", 1: "N"}


class Wheels(BaseModel):
    """A value measured at each of the four wheels.

    Order matches Assetto Corsa: front-left, front-right, rear-left, rear-right.
    """

    model_config = ConfigDict(frozen=True)

    front_left: float
    front_right: float
    rear_left: float
    rear_right: float

    @classmethod
    def of(cls, values: Sequence[float]) -> Wheels:
        """Build from a 4-element sequence in ``[FL, FR, RL, RR]`` order."""
        if len(values) != 4:
            raise ValueError(f"expected 4 wheel values, got {len(values)}")
        fl, fr, rl, rr = values
        return cls(front_left=fl, front_right=fr, rear_left=rl, rear_right=rr)

    def as_tuple(self) -> tuple[float, float, float, float]:
        """Return the values as a ``(FL, FR, RL, RR)`` tuple."""
        return (self.front_left, self.front_right, self.rear_left, self.rear_right)

    @property
    def front_axle_avg(self) -> float:
        """Average of the two front wheels."""
        return (self.front_left + self.front_right) / 2.0

    @property
    def rear_axle_avg(self) -> float:
        """Average of the two rear wheels."""
        return (self.rear_left + self.rear_right) / 2.0


class ACPhysics(BaseModel):
    """Physics telemetry for the player's car (60 Hz)."""

    model_config = ConfigDict(frozen=True)

    packet_id: int

    # Driver inputs.
    gas: float
    brake: float
    clutch: float
    steer_angle: float
    gear: int
    rpm: int
    speed_kmh: float
    fuel: float

    # Motion: g-force and velocity vectors, ordered (x=lateral, y=vertical,
    # z=longitudinal) following the Assetto Corsa convention.
    g_force: tuple[float, float, float]
    velocity: tuple[float, float, float]

    # Tyres.
    tyre_core_temp: Wheels
    tyre_temp_inner: Wheels
    tyre_temp_middle: Wheels
    tyre_temp_outer: Wheels
    tyre_pressure: Wheels
    tyre_wear: Wheels
    wheel_slip: Wheels
    brake_temp: Wheels
    suspension_travel: Wheels

    # Electronics / aids / environment.
    tc: float
    abs: float
    turbo_boost: float
    brake_bias: float
    air_temp: float
    road_temp: float

    @property
    def g_force_lateral(self) -> float:
        """Lateral g-force (positive to the right)."""
        return self.g_force[0]

    @property
    def g_force_vertical(self) -> float:
        """Vertical g-force."""
        return self.g_force[1]

    @property
    def g_force_longitudinal(self) -> float:
        """Longitudinal g-force (positive under acceleration)."""
        return self.g_force[2]

    @property
    def gear_label(self) -> str:
        """Human-readable gear: ``R``, ``N``, ``1``, ``2`` ..."""
        return _GEAR_LABELS.get(self.gear, str(self.gear - 1))


class ACGraphics(BaseModel):
    """Session/graphics telemetry (variable update rate)."""

    model_config = ConfigDict(frozen=True)

    packet_id: int
    status: ACStatus
    session_type: ACSessionType

    current_time: str
    last_time: str
    best_time: str
    split: str

    completed_laps: int
    position: int

    current_time_ms: int
    last_time_ms: int
    best_time_ms: int
    session_time_left: float
    distance_traveled: float

    current_sector_index: int
    last_sector_time_ms: int
    number_of_laps: int

    is_in_pit: bool
    is_in_pit_lane: bool

    tyre_compound: str
    normalized_car_position: float
    car_coordinates: tuple[float, float, float]
    flag: ACFlagType
    surface_grip: float


class ACStaticInfo(BaseModel):
    """Static session information, read once when the session loads."""

    model_config = ConfigDict(frozen=True)

    sm_version: str
    ac_version: str
    num_cars: int
    car_model: str
    track: str
    track_configuration: str
    car_skin: str
    sector_count: int
    max_torque: float
    max_power: float
    max_rpm: int
    max_fuel: float
    track_spline_length: float
    penalties_enabled: bool
    pit_window_start: int
    pit_window_end: int


class TelemetryFrame(BaseModel):
    """A single, self-contained telemetry sample.

    Bundles the physics and graphics pages with the (slowly changing) static
    information and a monotonic capture timestamp, so downstream consumers
    (storage, dashboard, analysis) receive everything they need per frame.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: float
    physics: ACPhysics
    graphics: ACGraphics
    static_info: ACStaticInfo

    @property
    def is_live(self) -> bool:
        """Whether the simulator is in a live (non-replay, non-paused) state."""
        return self.graphics.status is ACStatus.LIVE
