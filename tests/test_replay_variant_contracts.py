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
    # The limit is stated explicitly rather than inherited from the default.
    # The default yaw-rate limit was relaxed from 1.5 to 2.5 rad/s, so a 2.0
    # rad/s trajectory no longer trips it; this test is about the rejection
    # mechanism, not about the default value.
    report = validate_feasibility(
        _scenario(actor, duration_s=2.0), FeasibilityLimits(max_yaw_rate_rps=1.5)
    )
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


def test_grid_variants_follow_cartesian_product_order():
    variants, manifest = generate_grid_variants(
        _scenario(_ego(), _lead()), speed_multipliers=(0.9, 1.1), initial_gap_deltas_m=(0.0, 2.0), timing_offsets_s=(0.0, 0.5, 1.0)
    )
    assert len(variants) == 12
    first, second = manifest.configurations[:2]
    assert (first.speed_multiplier, first.initial_gap_delta_m, first.timing_offset_s) == (0.9, 0.0, 0.0)
    assert (second.speed_multiplier, second.initial_gap_delta_m, second.timing_offset_s) == (0.9, 0.0, 0.5)


def test_grid_generation_rejects_an_empty_parameter_list():
    with pytest.raises(ValueError):
        generate_grid_variants(_scenario(_ego(), _lead()), speed_multipliers=(), initial_gap_deltas_m=(0.0,), timing_offsets_s=(0.0,))


def test_batch_manifest_lists_every_variant_id_once():
    variants, manifest = generate_grid_variants(
        _scenario(_ego(), _lead()), speed_multipliers=(0.9, 1.0, 1.1), initial_gap_deltas_m=(0.0,), timing_offsets_s=(0.0,)
    )
    assert manifest.variant_ids == tuple(v.scenario_id for v in variants)
    assert len(set(manifest.variant_ids)) == 3
    assert manifest.parent_scenario_id == "s"


def test_random_variants_are_reproducible_from_the_seed():
    kwargs = dict(count=5, speed_multiplier_range=(0.8, 1.2), initial_gap_delta_range_m=(-2.0, 2.0), timing_offset_range_s=(0.0, 1.0), seed=7)
    _, first = generate_random_variants(_scenario(_ego(), _lead()), **kwargs)
    _, second = generate_random_variants(_scenario(_ego(), _lead()), **kwargs)
    assert first.configurations == second.configurations
    assert first.variant_ids == second.variant_ids


def test_random_variant_parameters_stay_inside_their_ranges():
    _, manifest = generate_random_variants(
        _scenario(_ego(), _lead()), count=50, speed_multiplier_range=(0.8, 1.2),
        initial_gap_delta_range_m=(-2.0, 2.0), timing_offset_range_s=(0.0, 1.0), seed=3,
    )
    for config in manifest.configurations:
        assert 0.8 <= config.speed_multiplier <= 1.2
        assert -2.0 <= config.initial_gap_delta_m <= 2.0
        assert 0.0 <= config.timing_offset_s <= 1.0


def test_batch_manifest_json_is_stable_and_parseable():
    _, manifest = generate_grid_variants(
        _scenario(_ego(), _lead()), speed_multipliers=(0.9, 1.1), initial_gap_deltas_m=(0.0, 2.0), timing_offsets_s=(0.0,)
    )
    text = batch_manifest_to_json(manifest)
    assert text == batch_manifest_to_json(manifest)
    payload = json.loads(text)
    assert payload["mode"] == "grid"
    assert len(payload["variants"]) == 4


@pytest.mark.xfail(raises=ValueError, reason="L7: one invalid configuration aborts the whole batch", strict=False)
def test_one_invalid_configuration_does_not_abort_the_batch():
    variants, _ = generate_grid_variants(
        _scenario(_ego(), _lead()), speed_multipliers=(1.0,), initial_gap_deltas_m=(0.0,), timing_offsets_s=(0.0, -0.5)
    )
    assert len(variants) == 1


def test_preview_rejects_empty_unknown_and_duplicate_edits():
    parent = _scenario(_ego(), _lead())
    with pytest.raises(ValueError):
        preview_variant(parent, [])
    with pytest.raises(ValueError):
        preview_variant(parent, [ActorMotionEdit("ghost")])
    with pytest.raises(ValueError):
        preview_variant(parent, [ActorMotionEdit("lead"), ActorMotionEdit("lead", speed_multiplier=2.0)])


def test_preview_speed_edit_changes_only_the_edited_actor():
    parent = _scenario(_ego(), _lead())
    preview = preview_variant(parent, [ActorMotionEdit("lead", speed_multiplier=2.0)])
    lead = _actor(preview, "lead").trajectory
    assert lead[-1].x_m - lead[0].x_m == pytest.approx(120.0)
    assert _actor(preview, "ego").trajectory == _actor(parent, "ego").trajectory


def test_preview_id_depends_on_edits_and_seed():
    parent = _scenario(_ego(), _lead())
    edit = [ActorMotionEdit("lead", speed_multiplier=1.5)]
    assert preview_variant(parent, edit).scenario_id == preview_variant(parent, edit).scenario_id
    assert preview_variant(parent, edit, seed=1).scenario_id != preview_variant(parent, edit).scenario_id


def test_motion_edit_rejects_invalid_values():
    with pytest.raises(ValueError):
        ActorMotionEdit("lead", braking_mps2=-1.0)
    with pytest.raises(ValueError):
        ActorMotionEdit("lead", start_time_s=3.0, end_time_s=1.0)
    with pytest.raises(ValueError):
        ActorMotionEdit("lead", speed_multiplier=0.0)


@pytest.mark.xfail(reason="L4: preview braking changes the speed column but not the positions", strict=False)
def test_preview_braking_shortens_the_distance_travelled():
    preview = preview_variant(_scenario(_ego(), _lead()), [ActorMotionEdit("lead", braking_mps2=3.0, start_time_s=1.0)])
    lead = _actor(preview, "lead").trajectory
    assert lead[-1].x_m == pytest.approx(40.0 + 10.0**2 / (2 * 3.0), abs=0.5)
    assert min(s.speed_mps for s in lead) >= 0.0


@pytest.mark.xfail(reason="L5: the preview ID hash ignores braking, acceleration and steering", strict=False)
def test_preview_id_differs_for_different_braking_strengths():
    parent = _scenario(_ego(), _lead())
    soft = preview_variant(parent, [ActorMotionEdit("lead", braking_mps2=3.0, start_time_s=1.0)])
    hard = preview_variant(parent, [ActorMotionEdit("lead", braking_mps2=7.0, start_time_s=1.0)])
    assert soft.scenario_id != hard.scenario_id


def test_export_declares_one_scenario_object_per_actor():
    root = _xml(_scenario(_ego(), _lead(), _cross()))
    assert [o.get("name") for o in root.iter("ScenarioObject")] == ["ego", "lead", "cross"]


def test_exported_polyline_vertices_keep_recorded_timestamps():
    scenario = _scenario(_ego(), _lead())
    root = _xml(scenario)
    for actor, trajectory in zip(scenario.actors, root.iter("Trajectory")):
        times = [float(v.get("time")) for v in trajectory.iter("Vertex")]
        assert times == pytest.approx([s.time_s for s in actor.trajectory])


def test_late_actor_event_starts_at_its_first_recorded_time():
    late = Actor("late", "vehicle.car", _line(50.0, 3.5, 8.0, 0.0, t0=2.0, steps=9), 4.5, 1.9)
    root = _xml(_scenario(_ego(), late))
    events = {e.get("name"): e for e in root.iter("Event")}
    condition = events["late_start"].find("StartTrigger").find(".//SimulationTimeCondition")
    assert float(condition.get("value")) == pytest.approx(2.0)


def test_export_references_road_template_and_duration():
    root = _xml(_scenario(_ego(), _lead()))
    assert root.find("RoadNetwork/LogicFile").get("filepath") == "straight-two-lane-v1.xodr"
    parameter = root.find("ParameterDeclarations/ParameterDeclaration")
    assert parameter.get("name") == "$ScenarioDuration"
    assert float(parameter.get("value")) == pytest.approx(6.0)


def test_export_maps_taxonomy_to_entity_types():
    walker = Actor("walker", "human.pedestrian.adult", _line(20.0, 5.0, 1.0, 0.0), 0.6, 0.6)
    truck = Actor("truck", "vehicle.truck", _line(60.0, 3.5, 8.0, 0.0), 8.0, 2.5)
    cone = Actor("cone", "movable_object.trafficcone", _line(25.0, -3.0, 0.0, 0.0, yaw=0.0), 0.4, 0.4)
    objects = {o.get("name"): o for o in _xml(_scenario(_ego(), walker, truck, cone)).iter("ScenarioObject")}
    assert objects["walker"].find("Pedestrian") is not None
    assert objects["truck"].find("Vehicle").get("vehicleCategory") == "truck"
    assert objects["cone"].find("MiscObject") is not None


def test_export_holds_zero_initial_speed():
    root = _xml(_scenario(_ego(), _lead()))
    assert {t.get("value") for t in root.iter("AbsoluteTargetSpeed")} == {"0"}
    policies = {p.get("value") for p in root.iter("Property") if p.get("name") == "initial_speed_policy"}
    assert policies == {"hold_zero_until_trajectory_start"}


def test_export_is_deterministic():
    scenario, template = select_opendrive_template(_scenario(_ego(), _lead()), topology="straight_road")
    assert build_openscenario_xml(scenario, template) == build_openscenario_xml(scenario, template)


@pytest.mark.xfail(reason="L10: StopTrigger sits inside Story and VehicleCatalog lacks a Directory child", strict=False)
def test_export_follows_openscenario_element_structure():
    root = _xml(_scenario(_ego(), _lead()))
    assert root.find("Storyboard/Story/StopTrigger") is None
    assert root.find("Storyboard/StopTrigger") is not None
    catalog = root.find("CatalogLocations/VehicleCatalog")
    assert catalog is None or catalog.find("Directory") is not None


@pytest.mark.xfail(reason="L3: BoundingBox Center x is offset by a third of the length", strict=False)
def test_bounding_box_is_centred_on_the_recorded_position():
    root = _xml(_scenario(_ego(), _lead()))
    assert {float(c.get("x")) for c in root.iter("Center")} == {0.0}


def test_scenario_survives_a_dictionary_round_trip():
    scenario = _scenario(_ego(), _lead(), _cross())
    restored = scenario_from_dict(scenario_to_dict(scenario))
    assert scenario_to_dict(restored) == scenario_to_dict(scenario)
