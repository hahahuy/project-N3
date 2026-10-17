"""Tier 1 kinematic preview: limits, integration, footprints and source state."""

from __future__ import annotations

import math

import pytest

from real2scenario.kinematic import (
    KINEMATIC_LIMITS_VERSION,
    KINEMATIC_VERSION,
    KinematicLimits,
    check_footprint_collisions,
    integrate_kinematic_open_loop,
)
from real2scenario.models import Actor, State
from real2scenario.nuscenes_backend import CanPoseSample
from real2scenario.source_state import (
    SOURCE_STATE_VERSION,
    SourceState,
    SourceStateExtension,
    build_source_state_extension,
)


def _extension(*rows: tuple[int, float, float], provenance: dict[str, str] | None = None):
    """Build a source extension from (timestamp_us, acceleration, yaw_rate) rows."""
    states = tuple(
        SourceState(timestamp, accel, yaw_rate, "can_pose", "can_pose")
        for timestamp, accel, yaw_rate in rows
    )
    return SourceStateExtension(SOURCE_STATE_VERSION, states, dict(provenance or {}))


def _steady(count: int, step_us: int = 50_000, accel: float = 0.0, yaw_rate: float = 0.0):
    return _extension(*((index * step_us, accel, yaw_rate) for index in range(count)))


def _codes(preview) -> list[str]:
    return [violation.code for violation in preview.violations]


def _box(actor_id: str, states: tuple[State, ...], length: float = 6.0, width: float = 8.0) -> Actor:
    """Actor whose footprint radius is exactly 5 m (hypot(6, 8) / 2)."""
    return Actor(actor_id, "vehicle", states, length, width)


def test_limits_defaults_match_documented_values() -> None:
    limits = KinematicLimits()
    assert limits.max_acceleration_mps2 == 5.0
    assert limits.max_deceleration_mps2 == 8.0
    assert limits.max_jerk_mps3 == 20.0
    assert limits.max_yaw_rate_radps == 1.5


def test_limits_default_version_is_the_module_constant() -> None:
    assert KinematicLimits().version == KINEMATIC_LIMITS_VERSION == "kinematic-limits-v1"


@pytest.mark.parametrize(
    "field",
    ["max_acceleration_mps2", "max_deceleration_mps2", "max_jerk_mps3", "max_yaw_rate_radps"],
)
def test_limits_reject_negative_values(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        KinematicLimits(**{field: -0.1})


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_limits_reject_non_finite_values(bad: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        KinematicLimits(max_jerk_mps3=bad)


def test_limits_reject_empty_version() -> None:
    with pytest.raises(ValueError, match="versioned"):
        KinematicLimits(version="")


def test_limits_accept_zero_boundaries() -> None:
    limits = KinematicLimits(0.0, 0.0, 0.0, 0.0)
    assert limits.max_acceleration_mps2 == 0.0
    assert limits.max_yaw_rate_radps == 0.0
