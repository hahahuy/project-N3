from pathlib import Path

import pytest

from real2scenario import (
    Actor,
    Scenario,
    STRAIGHT_ROAD_TOPOLOGY,
    State,
    TEMPLATE_REGISTRY_VERSION,
    select_opendrive_template,
)


def _local_scenario() -> Scenario:
    return Scenario(
        scenario_id="template-fixture",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(
            Actor(
                actor_id="ego",
                actor_type="vehicle.ego",
                trajectory=(State(0.0, 0.0, 0.0, 0.0, 1.0),),
            ),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )


def test_registry_selects_the_versioned_straight_road_template() -> None:
    selected, template = select_opendrive_template(_local_scenario(), topology=STRAIGHT_ROAD_TOPOLOGY)

    assert template.template_id == "straight-two-lane"
    assert template.version == "1.0"
    assert template.path().is_file()
    assert Path(template.path()).read_text(encoding="utf-8").startswith("<?xml")
    assert selected.provenance["map_reconstruction_mode"] == "local-template-approximation"
    assert selected.provenance["map_reconstruction_version"] == TEMPLATE_REGISTRY_VERSION
    assert selected.provenance["opendrive_template_selection_reason"].startswith(
        "explicit_supported_topology"
    )
    assert selected.provenance["dataset"] == "synthetic"


def test_registry_rejects_unsupported_topology_without_fallback() -> None:
    with pytest.raises(ValueError, match="Unsupported road topology"):
        select_opendrive_template(_local_scenario(), topology="intersection")


def test_registry_requires_a_local_road_aligned_scenario() -> None:
    scenario = _local_scenario()
    global_scenario = Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=scenario.ego_actor_id,
        actors=scenario.actors,
        coordinate_frame="nuscenes_global",
        provenance=scenario.provenance,
    )

    with pytest.raises(ValueError, match="local_road_aligned"):
        select_opendrive_template(global_scenario, topology=STRAIGHT_ROAD_TOPOLOGY)
