import pytest

from real2scenario import (
    BATCH_MANIFEST_VERSION,
    GENERATOR_VERSION,
    Actor,
    Scenario,
    State,
    VariantConfig,
    batch_manifest_to_json,
    generate_grid_variants,
    generate_random_variants,
    perturb_scenario,
)


def _scenario() -> Scenario:
    return Scenario(
        scenario_id="generation-fixture",
        duration_s=2.0,
        ego_actor_id="ego",
        actors=(
            Actor(
                "ego",
                "vehicle.ego",
                (State(0.0, 0.0, 0.0, 0.0, 10.0), State(2.0, 20.0, 0.0, 0.0, 10.0)),
            ),
            Actor(
                "lead",
                "vehicle.car",
                (State(0.0, 30.0, 0.0, 0.0, 8.0), State(2.0, 46.0, 0.0, 0.0, 8.0)),
            ),
        ),
        coordinate_frame="local_road_aligned",
        provenance={
            "dataset_name": "synthetic",
            "dataset_version": "v1",
            "source_scene_token": "scene-001",
            "source_window": "0.0s-2.0s",
            "coordinate_transform_version": "transform-v1",
            "map_reconstruction_mode": "template",
            "map_reconstruction_version": "template-v1",
            "generator_version": "baseline-v1",
        },
    )


def test_perturbation_is_deterministic_and_does_not_mutate_parent() -> None:
    parent = _scenario()
    config = VariantConfig(speed_multiplier=1.25, initial_gap_delta_m=-3.0, timing_offset_s=0.5, seed=11)

    first = perturb_scenario(parent, config)
    second = perturb_scenario(parent, config)

    assert first == second
    assert parent.actors[1].trajectory[1] == State(2.0, 46.0, 0.0, 0.0, 8.0)
    assert first.scenario_id.startswith("generation-fixture--variant-")
    assert first.provenance["parent_scenario_id"] == "generation-fixture"
    assert first.provenance["generator_version"] == GENERATOR_VERSION
    assert first.provenance["variant_speed_multiplier"] == "1.25"
    assert first.provenance["variant_initial_gap_delta_m"] == "-3"
    assert first.provenance["variant_timing_offset_s"] == "0.5"
    assert first.provenance["variant_seed"] == "11"


def test_perturbation_changes_speed_longitudinal_gap_and_timing() -> None:
    variant = perturb_scenario(
        _scenario(),
        VariantConfig(speed_multiplier=1.5, initial_gap_delta_m=-2.0, timing_offset_s=0.25),
    )

    ego_start, ego_end = variant.actors[0].trajectory
    lead_start, lead_end = variant.actors[1].trajectory
    assert (ego_start.x_m, ego_start.speed_mps) == (0.0, 15.0)
    assert (ego_end.x_m, ego_end.speed_mps) == (30.0, 15.0)
    assert (lead_start.time_s, lead_start.x_m, lead_start.speed_mps) == (0.25, 28.0, 12.0)
    assert (lead_end.time_s, lead_end.x_m, lead_end.speed_mps) == (2.25, 52.0, 12.0)
    assert variant.duration_s == 2.25


def test_perturbation_uses_ego_heading_for_longitudinal_gap() -> None:
    parent = _scenario()
    ego = parent.actors[0]
    changed_ego = Actor(
        ego.actor_id,
        ego.actor_type,
        tuple(State(s.time_s, s.x_m, s.y_m, 1.5707963267948966, s.speed_mps) for s in ego.trajectory),
    )
    parent = Scenario(
        parent.scenario_id,
        parent.duration_s,
        parent.ego_actor_id,
        (changed_ego, parent.actors[1]),
        parent.coordinate_frame,
        parent.provenance,
    )

    lead_start = perturb_scenario(parent, VariantConfig(initial_gap_delta_m=2.0)).actors[1].trajectory[0]
    assert lead_start.x_m == pytest.approx(30.0)
    assert lead_start.y_m == pytest.approx(2.0)


def test_perturbation_rejects_negative_timestamps_instead_of_clamping() -> None:
    with pytest.raises(ValueError, match="negative timestamp"):
        perturb_scenario(_scenario(), VariantConfig(timing_offset_s=-0.1))


def test_variant_config_rejects_non_integer_seed() -> None:
    with pytest.raises(ValueError, match="seed must be an integer"):
        VariantConfig(seed=1.5)  # type: ignore[arg-type]


def test_perturbation_rejects_empty_generator_version() -> None:
    with pytest.raises(ValueError, match="generator_version"):
        perturb_scenario(_scenario(), VariantConfig(), generator_version="")


def test_grid_generation_has_stable_order_ids_and_manifest() -> None:
    first_variants, first_manifest = generate_grid_variants(
        _scenario(),
        speed_multipliers=(1.0, 1.2),
        initial_gap_deltas_m=(0.0, -2.0),
        timing_offsets_s=(0.0, 0.25),
        seed=19,
    )
    second_variants, second_manifest = generate_grid_variants(
        _scenario(),
        speed_multipliers=(1.0, 1.2),
        initial_gap_deltas_m=(0.0, -2.0),
        timing_offsets_s=(0.0, 0.25),
        seed=19,
    )

    assert first_variants == second_variants
    assert first_manifest == second_manifest
    assert len(first_variants) == 8
    assert first_manifest.mode == "grid"
    assert first_manifest.variant_ids == tuple(item.scenario_id for item in first_variants)
    assert first_manifest.configurations[0] == VariantConfig(1.0, 0.0, 0.0, 19)
    assert first_manifest.configurations[1] == VariantConfig(1.0, 0.0, 0.25, 19)
    assert '"manifest_version":"1.0"' in batch_manifest_to_json(first_manifest)
    assert BATCH_MANIFEST_VERSION == "1.0"


def test_random_generation_repeats_with_seed_and_uses_requested_count() -> None:
    first, first_manifest = generate_random_variants(
        _scenario(),
        count=5,
        speed_multiplier_range=(0.8, 1.4),
        initial_gap_delta_range_m=(-4.0, 2.0),
        timing_offset_range_s=(0.0, 0.5),
        seed=23,
    )
    second, second_manifest = generate_random_variants(
        _scenario(),
        count=5,
        speed_multiplier_range=(0.8, 1.4),
        initial_gap_delta_range_m=(-4.0, 2.0),
        timing_offset_range_s=(0.0, 0.5),
        seed=23,
    )

    assert first == second
    assert first_manifest == second_manifest
    assert len(first) == 5
    assert all(0.8 <= config.speed_multiplier <= 1.4 for config in first_manifest.configurations)
    assert all(-4.0 <= config.initial_gap_delta_m <= 2.0 for config in first_manifest.configurations)
    assert all(0.0 <= config.timing_offset_s <= 0.5 for config in first_manifest.configurations)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda: generate_grid_variants(
                _scenario(),
                speed_multipliers=(),
                initial_gap_deltas_m=(0.0,),
                timing_offsets_s=(0.0,),
            ),
            "must not be empty",
        ),
        (
            lambda: generate_random_variants(
                _scenario(),
                count=0,
                speed_multiplier_range=(1.0, 1.0),
                initial_gap_delta_range_m=(0.0, 0.0),
                timing_offset_range_s=(0.0, 0.0),
            ),
            "positive integer",
        ),
        (
            lambda: generate_random_variants(
                _scenario(),
                count=1,
                speed_multiplier_range=(0.0, 1.0),
                initial_gap_delta_range_m=(0.0, 0.0),
                timing_offset_range_s=(0.0, 0.0),
            ),
            "positive values",
        ),
        (
            lambda: generate_random_variants(
                _scenario(),
                count=1,
                speed_multiplier_range=(1.0, 0.5),
                initial_gap_delta_range_m=(0.0, 0.0),
                timing_offset_range_s=(0.0, 0.0),
            ),
            "ordered",
        ),
    ],
)
def test_batch_generation_rejects_invalid_configuration(call, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()
