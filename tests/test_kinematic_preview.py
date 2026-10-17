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


def test_repeated_source_timestamp_is_rejected_by_the_trace() -> None:
    source = _extension((0, 0.0, 0.0), (100_000, 0.0, 0.0), (100_000, 0.0, 0.0))
    with pytest.raises(ValueError, match="strictly increase"):
        integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), source)


def test_acceleration_updates_speed_by_dt() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 2.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 3.0), source)
    assert preview.states[1].speed_mps == pytest.approx(3.1)


def test_yaw_rate_updates_yaw_by_dt() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 0.0, 0.5))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0.1, 3.0), source)
    assert preview.states[1].yaw_rad == pytest.approx(0.125)


def test_acceleration_over_limit_is_reported() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 6.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), source)
    (violation,) = preview.violations
    assert (violation.code, violation.state_index) == ("acceleration_exceeded", 1)
    assert (violation.observed, violation.limit) == (6.0, 5.0)


def test_acceleration_at_the_limit_is_not_reported() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 5.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), source)
    assert preview.violations == ()


def test_deceleration_over_limit_reports_positive_magnitude() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, -9.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), source)
    (violation,) = preview.violations
    assert violation.code == "deceleration_exceeded"
    assert (violation.observed, violation.limit) == (9.0, 8.0)


def test_negative_yaw_rate_over_limit_is_reported_by_magnitude() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 0.0, -2.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), source)
    (violation,) = preview.violations
    assert violation.code == "yaw_rate_exceeded"
    assert violation.observed == 2.0


def test_negative_speed_is_reported_without_clamping() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, -8.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 0.1), source)
    assert preview.states[1].speed_mps == pytest.approx(-0.3)
    negative = [v for v in preview.violations if v.code == "negative_speed"]
    assert len(negative) == 1 and negative[0].limit == 0.0


def test_jerk_over_limit_is_reported_from_the_second_step() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 0.0, 0.0), (100_000, 2.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), source)
    (violation,) = preview.violations
    assert (violation.code, violation.state_index) == ("jerk_exceeded", 2)
    assert violation.observed == pytest.approx(40.0)


def test_first_step_has_no_jerk_reference() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 4.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), source)
    assert "jerk_exceeded" not in _codes(preview)


def test_violation_message_names_the_actor() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 6.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 10.0), source, actor_id="veh-7")
    assert preview.violations[0].message.startswith("veh-7:")


def test_trace_uses_the_requested_actor_id() -> None:
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(3), actor_id="veh-7")
    assert preview.trace is not None
    assert len(preview.trace.states_for("veh-7")) == 3
    with pytest.raises(ValueError, match="no states"):
        preview.trace.states_for("ego")


def test_provenance_declares_simulator_and_no_silent_clamps() -> None:
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(2))
    assert preview.provenance["simulator_version"] == KINEMATIC_VERSION
    assert preview.provenance["silent_clamps"] == "forbidden"


@pytest.mark.parametrize(("step", "text"), [(0.05, "0.05"), (0.1, "0.1"), (1.0, "1")])
def test_provenance_formats_the_fixed_timestep(step: float, text: str) -> None:
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(2), fixed_timestep_s=step)
    assert preview.provenance["fixed_timestep_s"] == text


def test_provenance_records_the_limits_version() -> None:
    limits = KinematicLimits(version="custom-limits-v9")
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), _steady(2), limits=limits)
    assert preview.provenance["kinematic_limits_version"] == "custom-limits-v9"


def test_provenance_includes_source_provenance() -> None:
    source = _extension((0, 0.0, 0.0), (50_000, 0.0, 0.0), provenance={"source_state_status": "can_pose"})
    preview = integrate_kinematic_open_loop(State(0, 0, 0, 0, 1), source)
    assert preview.provenance["source_state_status"] == "can_pose"
    assert preview.source_state_version == SOURCE_STATE_VERSION


def test_footprints_empty_actor_list_is_clear() -> None:
    result = check_footprint_collisions(())
    assert result.status == "clear"
    assert result.collisions == ()


def test_footprints_missing_dimension_is_unsupported_with_reason() -> None:
    sized = _box("a", (State(0, 0, 0, 0, 0),))
    unsized = Actor("b", "vehicle", (State(0, 50, 0, 0, 0),), length_m=4.0)
    result = check_footprint_collisions((sized, unsized))
    assert result.status == "unsupported"
    assert result.reason == "actor_dimensions_missing"


def test_footprints_far_apart_actors_are_clear() -> None:
    first = _box("a", (State(0, 0, 0, 0, 0),))
    second = _box("b", (State(0, 100, 0, 0, 0),))
    result = check_footprint_collisions((first, second))
    assert (result.status, result.reason) == ("clear", None)


def test_footprints_touching_at_the_boundary_collide() -> None:
    first = _box("a", (State(0, 0, 0, 0, 0),))
    touching = _box("b", (State(0, 10, 0, 0, 0),))
    apart = _box("c", (State(0, 10.01, 0, 0, 0),))
    assert check_footprint_collisions((first, touching)).status == "collision"
    assert check_footprint_collisions((first, apart)).status == "clear"


def test_footprints_without_matching_times_are_clear() -> None:
    first = _box("a", (State(0.0, 0, 0, 0, 0),))
    later = _box("b", (State(0.1, 0, 0, 0, 0),))
    assert check_footprint_collisions((first, later)).status == "clear"


def test_footprint_collision_records_state_indices() -> None:
    first = _box("a", (State(0, 0, 0, 0, 0), State(1, 0, 0, 0, 0)))
    late = _box("b", (State(1, 9, 0, 0, 0), State(2, 50, 0, 0, 0)))
    (collision,) = check_footprint_collisions((first, late)).collisions
    assert collision == {
        "left_actor_id": "a", "right_actor_id": "b",
        "left_state_index": 1, "right_state_index": 0,
    }


def test_footprint_times_match_after_rounding() -> None:
    first = _box("a", (State(0.1 + 0.2, 0, 0, 0, 0),))
    second = _box("b", (State(0.3, 1, 0, 0, 0),))
    assert 0.1 + 0.2 != 0.3
    assert check_footprint_collisions((first, second)).status == "collision"


def test_source_state_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="equal, non-empty"):
        build_source_state_extension((0, 1_000_000), ((0.0, 0.0),), (0.0, 0.0))


def test_source_state_rejects_non_increasing_timestamps() -> None:
    with pytest.raises(ValueError, match="strictly increase"):
        build_source_state_extension((0, 0), ((0.0, 0.0), (1.0, 0.0)), (0.0, 0.0))


def test_constant_velocity_has_zero_finite_difference_acceleration() -> None:
    extension = build_source_state_extension(
        (0, 1_000_000, 2_000_000, 3_000_000),
        ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)),
        (0.0, 0.0, 0.0, 0.0),
    )
    assert [state.acceleration_mps2 for state in extension.states] == pytest.approx([0.0] * 4)


def test_yaw_rate_wraps_across_pi() -> None:
    extension = build_source_state_extension(
        (0, 1_000_000), ((0.0, 0.0), (0.0, 0.0)), (3.1, -3.1)
    )
    expected = 2 * math.pi - 6.2
    assert extension.states[0].yaw_rate_radps == pytest.approx(expected)
    assert extension.states[1].yaw_rate_radps == pytest.approx(expected)
