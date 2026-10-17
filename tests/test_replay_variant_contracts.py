"""Contracts for replay metrics, feasibility checks, variant generation and XOSC export.

Every expected value is computed by hand from a small synthetic scenario, so a
failure points at the code under test rather than at recorded data. Tests
marked ``xfail`` pin known defects; they flip to XPASS once the defect is fixed.
"""

import json
import math
import xml.etree.ElementTree as ET

import pytest

from real2scenario.exporter import build_openscenario_xml
from real2scenario.generation import (
    ActorMotionEdit,
    batch_manifest_to_json,
    generate_grid_variants,
    generate_random_variants,
    perturb_scenario,
    preview_variant,
)
from real2scenario.metrics import aggregate_replay_metrics, compute_replay_metrics
from real2scenario.models import Actor, Scenario, State, VariantConfig
from real2scenario.serialization import scenario_from_dict, scenario_to_dict
from real2scenario.templates import select_opendrive_template
from real2scenario.validation import FeasibilityLimits, validate_feasibility


def _line(x0, y0, vx, vy, *, t0=0.0, steps=13, dt=0.5, yaw=None):
    """States of a constant-velocity actor sampled every ``dt`` seconds."""
    heading = math.atan2(vy, vx) if yaw is None else yaw
    speed = math.hypot(vx, vy)
    return tuple(
        State(t0 + i * dt, x0 + vx * i * dt, y0 + vy * i * dt, heading, speed) for i in range(steps)
    )


def _scenario(*actors, scenario_id="s", duration_s=6.0):
    return Scenario(scenario_id, duration_s, actors[0].actor_id, tuple(actors), "local_road_aligned")


def _ego():
    return Actor("ego", "vehicle.ego", _line(0.0, 0.0, 10.0, 0.0), 4.5, 1.9)


def _lead():
    return Actor("lead", "vehicle.car", _line(30.0, 0.0, 10.0, 0.0), 4.5, 1.9)


def _cross():
    return Actor("cross", "vehicle.car", _line(40.0, -20.0, 0.0, 5.0), 4.5, 1.9)


def _actor(scenario, actor_id):
    return next(actor for actor in scenario.actors if actor.actor_id == actor_id)


def _xml(scenario):
    selected, template = select_opendrive_template(scenario, topology="straight_road")
    return ET.fromstring(build_openscenario_xml(selected, template).split("\n", 1)[1])


def test_identical_replay_has_zero_error_and_complete_coverage():
    states = _line(0.0, 0.0, 10.0, 0.0)
    metrics = compute_replay_metrics(states, states)
    assert metrics.position_rmse_m == 0.0
    assert metrics.ade_m == 0.0
    assert metrics.fde_m == 0.0
    assert metrics.heading_mae_rad == 0.0
    assert metrics.speed_mae_mps == 0.0
    assert metrics.coverage_status == "complete"
    assert metrics.sample_count == len(states)


def test_constant_lateral_offset_sets_rmse_ade_and_fde_to_the_offset():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    replayed = _line(0.0, 0.5, 10.0, 0.0)
    metrics = compute_replay_metrics(recorded, replayed)
    assert metrics.position_rmse_m == pytest.approx(0.5)
    assert metrics.ade_m == pytest.approx(0.5)
    assert metrics.fde_m == pytest.approx(0.5)
    assert metrics.final_displacement_m == pytest.approx(0.5)


def test_denser_replay_is_interpolated_at_recorded_times():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    replayed = _line(0.0, 0.0, 10.0, 0.0, steps=25, dt=0.25)
    metrics = compute_replay_metrics(recorded, replayed)
    assert metrics.ade_m == pytest.approx(0.0, abs=1e-9)
    assert metrics.sample_count == len(recorded)


def test_heading_error_wraps_across_the_pi_boundary():
    recorded = _line(0.0, 0.0, 10.0, 0.0, yaw=math.pi - 0.01)
    replayed = _line(0.0, 0.0, 10.0, 0.0, yaw=-math.pi + 0.01)
    metrics = compute_replay_metrics(recorded, replayed)
    assert metrics.heading_mae_rad == pytest.approx(0.02, abs=1e-9)


def test_speed_error_is_the_mean_absolute_difference():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    replayed = tuple(State(s.time_s, s.x_m, s.y_m, s.yaw_rad, 12.0) for s in recorded)
    assert compute_replay_metrics(recorded, replayed).speed_mae_mps == pytest.approx(2.0)


def test_short_replay_reports_insufficient_coverage_without_fde():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    replayed = _line(0.0, 0.0, 10.0, 0.0, steps=7)
    metrics = compute_replay_metrics(recorded, replayed)
    assert metrics.coverage_status == "insufficient_coverage"
    assert metrics.fde_m is None
    assert metrics.sample_count == 7


def test_replay_without_overlapping_time_is_rejected():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    replayed = _line(0.0, 0.0, 10.0, 0.0, t0=10.0)
    with pytest.raises(ValueError):
        compute_replay_metrics(recorded, replayed)


def test_aggregate_reports_mean_median_and_max_ade():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    metrics = [compute_replay_metrics(recorded, _line(0.0, offset, 10.0, 0.0)) for offset in (1.0, 2.0, 3.0, 10.0)]
    aggregate = aggregate_replay_metrics(metrics)
    assert aggregate.actor_count == 4
    assert aggregate.ade_m.mean == pytest.approx(4.0)
    assert aggregate.ade_m.median == pytest.approx(2.5)
    assert aggregate.ade_m.max == pytest.approx(10.0)


def test_aggregate_fde_ignores_actors_without_full_coverage():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    complete = compute_replay_metrics(recorded, _line(0.0, 1.0, 10.0, 0.0))
    partial = compute_replay_metrics(recorded, _line(0.0, 9.0, 10.0, 0.0, steps=5))
    aggregate = aggregate_replay_metrics([complete, partial])
    assert aggregate.actor_count == 2
    assert aggregate.fde_m.max == pytest.approx(1.0)
    assert aggregate.ade_m.max == pytest.approx(9.0)


def test_constant_speed_scenario_is_feasible():
    report = validate_feasibility(_scenario(_ego(), _lead()))
    assert report.valid
    assert report.reasons == ()
    assert report.validation_version == FeasibilityLimits().version


def test_acceleration_above_limit_is_reported_with_observed_value():
    speeds = (10.0, 10.0, 14.0, 14.0, 14.0)
    actor = Actor("ego", "vehicle.ego", tuple(State(i * 0.5, i * 5.0, 0.0, 0.0, v) for i, v in enumerate(speeds)), 4.5, 1.9)
    report = validate_feasibility(_scenario(actor, duration_s=2.0))
    reason = next(r for r in report.reasons if r.code == "acceleration_exceeded")
    assert not report.valid
    assert reason.actor_id == "ego"
    assert reason.observed == pytest.approx(8.0)
    assert reason.limit == pytest.approx(5.0)


def test_deceleration_above_limit_is_rejected():
    speeds = (10.0, 10.0, 4.0, 4.0, 4.0)
    actor = Actor("ego", "vehicle.ego", tuple(State(i * 0.5, i * 4.0, 0.0, 0.0, v) for i, v in enumerate(speeds)), 4.5, 1.9)
    report = validate_feasibility(_scenario(actor, duration_s=2.0))
    reason = next(r for r in report.reasons if r.code == "deceleration_exceeded")
    assert reason.observed == pytest.approx(12.0)


def test_yaw_rate_above_limit_is_rejected():
    yaws = (0.0, 0.0, 1.0, 1.0)
    actor = Actor("ego", "vehicle.ego", tuple(State(i * 0.5, i * 5.0, 0.0, yaw, 10.0) for i, yaw in enumerate(yaws)), 4.5, 1.9)
    report = validate_feasibility(_scenario(actor, duration_s=2.0))
    reason = next(r for r in report.reasons if r.code == "yaw_rate_exceeded")
    assert reason.observed == pytest.approx(2.0)


def test_heading_crossing_pi_is_not_a_yaw_rate_violation():
    yaws = (math.pi - 0.05, -math.pi + 0.05, -math.pi + 0.15)
    actor = Actor("ego", "vehicle.ego", tuple(State(i * 0.5, -i * 5.0, 0.0, yaw, 10.0) for i, yaw in enumerate(yaws)), 4.5, 1.9)
    report = validate_feasibility(_scenario(actor, duration_s=1.0))
    assert "yaw_rate_exceeded" not in {r.code for r in report.reasons}


def test_speed_limit_is_checked_only_when_configured():
    scenario = _scenario(_ego(), _lead())
    assert validate_feasibility(scenario).valid
    report = validate_feasibility(scenario, FeasibilityLimits(max_speed_mps=8.0))
    assert "speed_exceeded" in {r.code for r in report.reasons}


def test_validation_reports_every_failing_actor():
    def jumpy(actor_id, actor_type):
        speeds = (10.0, 20.0, 20.0)
        return Actor(actor_id, actor_type, tuple(State(i * 0.5, i * 5.0, 0.0, 0.0, v) for i, v in enumerate(speeds)), 4.5, 1.9)

    report = validate_feasibility(_scenario(jumpy("ego", "vehicle.ego"), jumpy("lead", "vehicle.car"), duration_s=1.0))
    assert {r.actor_id for r in report.reasons} == {"ego", "lead"}


def test_identity_variant_reproduces_parent_motion():
    parent = _scenario(_ego(), _lead())
    variant = perturb_scenario(parent, VariantConfig())
    for before, after in zip(parent.actors, variant.actors):
        assert [(s.time_s, s.x_m, s.y_m, s.speed_mps) for s in before.trajectory] == pytest.approx(
            [(s.time_s, s.x_m, s.y_m, s.speed_mps) for s in after.trajectory]
        )


def test_variant_id_is_deterministic():
    parent = _scenario(_ego(), _lead())
    config = VariantConfig(speed_multiplier=1.2, initial_gap_delta_m=3.0, timing_offset_s=0.5)
    assert perturb_scenario(parent, config).scenario_id == perturb_scenario(parent, config).scenario_id


def test_variant_id_changes_with_speed_multiplier():
    parent = _scenario(_ego(), _lead())
    first = perturb_scenario(parent, VariantConfig(speed_multiplier=1.1))
    second = perturb_scenario(parent, VariantConfig(speed_multiplier=1.2))
    assert first.scenario_id != second.scenario_id
    assert first.scenario_id.startswith("s--variant-")


def test_perturbation_does_not_mutate_the_parent():
    parent = _scenario(_ego(), _lead())
    before = json.dumps(scenario_to_dict(parent), sort_keys=True)
    perturb_scenario(parent, VariantConfig(speed_multiplier=1.4, initial_gap_delta_m=-3.0, timing_offset_s=0.5))
    assert json.dumps(scenario_to_dict(parent), sort_keys=True) == before


def test_initial_gap_moves_only_non_ego_actors():
    parent = _scenario(_ego(), _lead())
    variant = perturb_scenario(parent, VariantConfig(initial_gap_delta_m=5.0))
    assert _actor(variant, "lead").trajectory[0].x_m == pytest.approx(35.0)
    assert _actor(variant, "ego").trajectory[0].x_m == pytest.approx(0.0)


def test_initial_gap_is_applied_along_the_ego_heading():
    ego = Actor("ego", "vehicle.ego", _line(0.0, 0.0, 0.0, 10.0), 4.5, 1.9)
    lead = Actor("lead", "vehicle.car", _line(0.0, 30.0, 0.0, 10.0), 4.5, 1.9)
    variant = perturb_scenario(_scenario(ego, lead), VariantConfig(initial_gap_delta_m=5.0))
    start = _actor(variant, "lead").trajectory[0]
    assert (start.x_m, start.y_m) == pytest.approx((0.0, 35.0))


def test_timing_offset_shifts_only_non_ego_timestamps():
    variant = perturb_scenario(_scenario(_ego(), _lead()), VariantConfig(timing_offset_s=0.5))
    assert _actor(variant, "lead").trajectory[0].time_s == pytest.approx(0.5)
    assert _actor(variant, "ego").trajectory[0].time_s == pytest.approx(0.0)
    assert variant.duration_s == pytest.approx(6.5)


def test_negative_timing_offset_below_zero_is_rejected():
    with pytest.raises(ValueError):
        perturb_scenario(_scenario(_ego(), _lead()), VariantConfig(timing_offset_s=-0.5))


def test_speed_multiplier_scales_recorded_speeds():
    variant = perturb_scenario(_scenario(_ego(), _lead()), VariantConfig(speed_multiplier=1.5))
    assert [s.speed_mps for s in _actor(variant, "lead").trajectory] == pytest.approx([15.0] * 13)


def test_speed_multiplier_scales_distance_for_parallel_actors():
    variant = perturb_scenario(_scenario(_ego(), _lead()), VariantConfig(speed_multiplier=1.5))
    lead = _actor(variant, "lead").trajectory
    assert lead[-1].x_m - lead[0].x_m == pytest.approx(90.0)


@pytest.mark.xfail(reason="L6: perturb_scenario scales displacement only along the ego axis", strict=False)
def test_speed_multiplier_scales_distance_for_crossing_actors():
    variant = perturb_scenario(_scenario(_ego(), _cross()), VariantConfig(speed_multiplier=1.5))
    cross = _actor(variant, "cross").trajectory
    assert cross[-1].y_m - cross[0].y_m == pytest.approx(45.0)
