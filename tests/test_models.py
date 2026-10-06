import pytest

from real2scenario import Actor, Scenario, State, VariantConfig


def test_scenario_accepts_a_valid_ego_trajectory() -> None:
    ego = Actor(
        actor_id="ego",
        actor_type="vehicle",
        trajectory=(
            State(time_s=0.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=1.0),
            State(time_s=1.0, x_m=1.0, y_m=0.0, yaw_rad=0.0, speed_mps=1.0),
        ),
    )

    scenario = Scenario(
        scenario_id="scene-001",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(ego,),
        coordinate_frame="local_enu",
        provenance={"dataset": "fixture"},
    )

    assert scenario.ego_actor_id == "ego"
    assert scenario.actors[0].trajectory[-1].x_m == 1.0


def test_actor_rejects_non_monotonic_timestamps() -> None:
    states = (
        State(time_s=1.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0),
        State(time_s=1.0, x_m=1.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0),
    )

    with pytest.raises(ValueError, match="strictly increase"):
        Actor(actor_id="ego", actor_type="vehicle", trajectory=states)


def test_scenario_rejects_missing_ego() -> None:
    actor = Actor(
        actor_id="lead",
        actor_type="vehicle",
        trajectory=(State(time_s=0.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0),),
    )

    with pytest.raises(ValueError, match="ego_actor_id"):
        Scenario(
            scenario_id="scene-001",
            duration_s=1.0,
            ego_actor_id="ego",
            actors=(actor,),
            coordinate_frame="local_enu",
        )


def test_variant_config_requires_a_positive_speed_multiplier() -> None:
    with pytest.raises(ValueError, match="positive"):
        VariantConfig(speed_multiplier=0.0)
