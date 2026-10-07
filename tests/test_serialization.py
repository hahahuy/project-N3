import json
from pathlib import Path

import pytest

from real2scenario import (
    REQUIRED_PROVENANCE_KEYS,
    Actor,
    Scenario,
    State,
    VariantConfig,
    artifact_from_dict,
    artifact_from_json,
    artifact_to_json,
    baseline_artifact_to_dict,
    variant_artifact_to_dict,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic-variant-artifact.json"


def _provenance() -> dict[str, str]:
    return {
        "dataset_name": "synthetic-fixture",
        "dataset_version": "v1",
        "source_scene_token": "synthetic-scene-001",
        "source_window": "0.0s-1.0s",
        "coordinate_transform_version": "synthetic-transform-v1",
        "map_reconstruction_mode": "local-template",
        "map_reconstruction_version": "highway-template-v1",
        "generator_version": "real2scenario-test-v1",
    }


def _scenario() -> Scenario:
    ego = Actor(
        actor_id="ego",
        actor_type="vehicle",
        trajectory=(
            State(time_s=0.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=10.0),
            State(time_s=1.0, x_m=10.0, y_m=0.0, yaw_rad=0.0, speed_mps=10.0),
        ),
        length_m=4.5,
        width_m=1.8,
    )
    return Scenario(
        scenario_id="synthetic-variant-001",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(ego,),
        coordinate_frame="local_road_aligned",
        provenance=_provenance(),
    )


def test_variant_artifact_round_trips_from_synthetic_fixture() -> None:
    scenario, parent_scenario_id, config = artifact_from_json(FIXTURE_PATH.read_text())

    assert scenario.scenario_id == "synthetic-variant-001"
    assert [actor.actor_id for actor in scenario.actors] == ["ego", "lead"]
    assert parent_scenario_id == "synthetic-baseline-001"
    assert config == VariantConfig(
        speed_multiplier=1.1,
        initial_gap_delta_m=-2.0,
        timing_offset_s=0.25,
        seed=7,
    )


def test_artifact_json_is_deterministic_and_round_trips() -> None:
    artifact = variant_artifact_to_dict(
        _scenario(),
        parent_scenario_id="synthetic-baseline-001",
        config=VariantConfig(
            speed_multiplier=1.1,
            initial_gap_delta_m=-2.0,
            timing_offset_s=0.25,
            seed=7,
        ),
    )

    first_json = artifact_to_json(artifact)
    second_json = artifact_to_json(artifact)
    scenario, parent_scenario_id, config = artifact_from_json(first_json)

    assert first_json == second_json
    assert scenario == _scenario()
    assert parent_scenario_id == "synthetic-baseline-001"
    assert config == VariantConfig(1.1, -2.0, 0.25, 7)


def test_artifact_rejects_missing_required_provenance() -> None:
    provenance = _provenance()
    provenance.pop("source_scene_token")
    scenario = Scenario(
        scenario_id="synthetic-baseline-001",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=_scenario().actors,
        coordinate_frame="local_road_aligned",
        provenance=provenance,
    )

    with pytest.raises(ValueError, match="source_scene_token"):
        baseline_artifact_to_dict(scenario)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda artifact: artifact["scenario"].__setitem__("unexpected", "value"),
            "unknown field",
        ),
        (
            lambda artifact: artifact["scenario"]["actors"][0]["trajectory"][1].__setitem__(
                "time_s", 0.0
            ),
            "strictly increase",
        ),
        (
            lambda artifact: artifact.__setitem__("schema_version", "99.0"),
            "Unsupported artifact schema_version",
        ),
    ],
)
def test_artifact_rejects_unknown_or_malformed_fields(mutate, message: str) -> None:
    artifact = variant_artifact_to_dict(
        _scenario(), "synthetic-baseline-001", VariantConfig()
    )
    mutate(artifact)

    with pytest.raises(ValueError, match=message):
        artifact_from_dict(artifact)


def test_required_provenance_keys_are_serialized() -> None:
    artifact = baseline_artifact_to_dict(_scenario())

    assert REQUIRED_PROVENANCE_KEYS <= artifact["scenario"]["provenance"].keys()
    assert json.loads(artifact_to_json(artifact)) == artifact
