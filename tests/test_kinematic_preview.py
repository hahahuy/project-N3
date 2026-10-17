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


def test_integrate_rejects_zero_timestep() -> None:
    with pytest.raises(ValueError, match="fixed_timestep_s"):
        integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(2), fixed_timestep_s=0.0)


def test_integrate_rejects_negative_timestep() -> None:
    with pytest.raises(ValueError, match="fixed_timestep_s"):
        integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(2), fixed_timestep_s=-0.05)


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_integrate_rejects_non_finite_timestep(bad: float) -> None:
    with pytest.raises(ValueError, match="fixed_timestep_s"):
        integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(2), fixed_timestep_s=bad)


def test_single_measurement_returns_only_the_initial_state() -> None:
    initial = State(0.0, 1.0, 2.0, 0.3, 4.0)
    preview = integrate_kinematic_open_loop(initial, _steady(1))
    assert preview.states == (initial,)
    assert preview.violations == ()


def test_first_state_is_the_unmodified_initial_state() -> None:
    initial = State(0.0, 5.0, -3.0, 0.2, 7.0, source_timestamp_us=123, source_record_token="tok")
    preview = integrate_kinematic_open_loop(initial, _steady(3))
    assert preview.states[0] is initial


def test_time_advances_by_the_fixed_timestep() -> None:
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(4, step_us=50_000))
    assert [state.time_s for state in preview.states] == pytest.approx([0.0, 0.05, 0.10, 0.15])


def test_constant_speed_moves_straight_along_x() -> None:
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), _steady(3))
    assert [state.x_m for state in preview.states] == pytest.approx([0.0, 0.5, 1.0])
    assert [state.y_m for state in preview.states] == pytest.approx([0.0, 0.0, 0.0])


def test_heading_of_ninety_degrees_moves_along_y() -> None:
    preview = integrate_kinematic_open_loop(State(0, 0, 0, math.pi / 2, 10.0), _steady(3))
    assert preview.states[-1].x_m == pytest.approx(0.0, abs=1e-9)
    assert preview.states[-1].y_m == pytest.approx(1.0)


def test_long_source_gap_is_capped_at_the_fixed_timestep() -> None:
    preview = integrate_kinematic_open_loop(
        State(0, 0, 0, 0, 1), _extension((0, 0.0, 0.0), (1_000_000, 0.0, 0.0)), fixed_timestep_s=0.05
    )
    assert preview.states[1].time_s == pytest.approx(0.05)


def test_short_source_gap_is_used_instead_of_the_fixed_timestep() -> None:
    preview = integrate_kinematic_open_loop(
        State(0, 0, 0, 0, 1), _extension((0, 0.0, 0.0), (10_000, 0.0, 0.0)), fixed_timestep_s=0.05
    )
    assert preview.states[1].time_s == pytest.approx(0.01)
