from math import pi

import pytest

from real2scenario import Actor, Scenario, State
from real2scenario.carla_adapter import (
    CARLA_FRAME,
    CarlaAnchor,
    CarlaMappingConfig,
    map_scenario_to_carla,
    transform_state_to_carla,
)


def _scenario() -> Scenario:
    return Scenario(
        scenario_id="scene-1",
        duration_s=1.0,
        ego_actor_id="ego",
        coordinate_frame="local_road_aligned",
        actors=(
            Actor(
                actor_id="ego",
                actor_type="vehicle",
                trajectory=(
                    State(0.0, 0.0, 0.0, 0.0, 5.0),
                    State(1.0, 5.0, 0.0, 0.0, 5.0),
                ),
            ),
        ),
        provenance={"source_scene_token": "scene-token"},
    )


def test_transform_state_applies_anchor_rotation_and_translation() -> None:
    state = transform_state_to_carla(
        State(0.0, 2.0, 1.0, pi / 2, 5.0),
        CarlaAnchor(10.0, 20.0, 0.3, pi / 2, 4),
    )

    assert state.x_m == pytest.approx(9.0)
    assert state.y_m == pytest.approx(22.0)
    assert state.yaw_rad == pytest.approx(-pi)


def test_mapping_preserves_source_and_records_carla_provenance() -> None:
    source = _scenario()
    result = map_scenario_to_carla(
        source,
        anchor=CarlaAnchor(100.0, 200.0, 0.5, 0.0, 2),
        world_name="Town04",
    )

    assert source.coordinate_frame == "local_road_aligned"
    assert result.scenario.coordinate_frame == CARLA_FRAME
    assert result.scenario.actors[0].trajectory[1].x_m == pytest.approx(105.0)
    assert result.scenario.provenance["carla_world"] == "Town04"
    assert result.scenario.provenance["carla_anchor_spawn_index"] == "2"


def test_mapping_rejects_global_source_coordinates() -> None:
    source = _scenario()
    global_source = Scenario(
        scenario_id=source.scenario_id,
        duration_s=source.duration_s,
        ego_actor_id=source.ego_actor_id,
        actors=source.actors,
        coordinate_frame="nuscenes_global",
        provenance=source.provenance,
    )

    with pytest.raises(ValueError, match="local_road_aligned"):
        map_scenario_to_carla(
            global_source,
            anchor=CarlaAnchor(0.0, 0.0, 0.0, 0.0, 0),
            world_name="Town04",
            config=CarlaMappingConfig(),
        )
