"""Tests for telemetry domain models."""

from __future__ import annotations

import pytest
from src.telemetry.models import ACPhysics, Wheels
from src.telemetry.shm_structs import ACStatus

from tests.factories import make_frame, make_physics


def test_wheels_of_roundtrip() -> None:
    wheels = Wheels.of([1.0, 2.0, 3.0, 4.0])
    assert wheels.as_tuple() == (1.0, 2.0, 3.0, 4.0)
    assert wheels.front_axle_avg == 1.5
    assert wheels.rear_axle_avg == 3.5


def test_wheels_of_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="expected 4 wheel values"):
        Wheels.of([1.0, 2.0, 3.0])


def test_wheels_is_immutable() -> None:
    wheels = Wheels.of([1.0, 2.0, 3.0, 4.0])
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError on frozen
        wheels.front_left = 9.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("gear", "label"),
    [(0, "R"), (1, "N"), (2, "1"), (3, "2"), (8, "7")],
)
def test_gear_label(gear: int, label: str) -> None:
    physics = make_physics(gear=gear)
    assert physics.gear_label == label


def test_g_force_named_axes() -> None:
    physics = make_physics(g_force=(0.5, -1.0, 1.5))
    assert physics.g_force_lateral == 0.5
    assert physics.g_force_vertical == -1.0
    assert physics.g_force_longitudinal == 1.5


def test_physics_is_frozen() -> None:
    physics = make_physics()
    with pytest.raises(Exception):  # noqa: B017
        physics.rpm = 1234  # type: ignore[misc]


def test_frame_is_live_reflects_status() -> None:
    live = make_frame(status=ACStatus.LIVE)
    replay = make_frame(status=ACStatus.REPLAY)
    assert live.is_live is True
    assert replay.is_live is False


def test_physics_requires_all_wheel_data() -> None:
    # Building ACPhysics without a required field must fail validation.
    with pytest.raises(Exception):  # noqa: B017
        ACPhysics(packet_id=1)  # type: ignore[call-arg]
