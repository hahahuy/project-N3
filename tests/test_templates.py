from pathlib import Path

import pytest

from real2scenario import (
    Actor,
    Scenario,
    STRAIGHT_ROAD_TOPOLOGY,
    State,
    TEMPLATE_REGISTRY_VERSION,
    select_full_scene_map,
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


def test_full_scene_map_names_the_declared_road_and_passes_export() -> None:
    """Per-scene maps ride the same exporter contract as templates.

    The caller owns the transformed bytes (staged_path); selection only names
    the declared LogicFile and records provenance, so the exporter accepts the
    pair with zero special cases.
    """
    from real2scenario import build_openscenario_xml
    from real2scenario.xosc_subset import interpret_xosc_subset, parse_xosc_subset

    xodr_text = (
        "<?xml version='1.0' encoding='UTF-8'?>\n<OpenDRIVE>"
        "<header revMajor='1' revMinor='6' name='m'/>"
        "<road name='r1' id='1' length='10' junction='-1'><planView>"
        "<geometry s='0' x='0' y='0' hdg='0' length='10'><line/></geometry>"
        "</planView><lanes><laneOffset s='0' a='0' b='0' c='0' d='0'/>"
        "<laneSection s='0'><center><lane id='0' type='none' level='false'/></center>"
        "</laneSection></lanes></road></OpenDRIVE>\n"
    )
    two_actor = Scenario(
        scenario_id="template-fixture",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle.ego", (State(0.0, 0.0, 0.0, 0.0, 1.0),)),
            Actor("lead", "vehicle.car", (State(0.0, 5.0, 0.0, 0.0, 1.0),)),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    selected, template = select_full_scene_map(
        two_actor,
        map_name="unit-map",
        road_filename="unit-map.xodr",
        map_builder_version="map-builder-v1",
    )

    assert template.template_id == "nuscenes-fullmap-unit-map"
    assert template.relative_path == "unit-map.xodr"
    assert selected.provenance["map_reconstruction_mode"] == "local_nuscenes_fullmap"
    assert selected.provenance["map_name"] == "unit-map"

    xml = build_openscenario_xml(selected, template)
    assert 'filepath="unit-map.xodr"' in xml
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        xosc = Path(directory) / "scenario.xosc"
        xosc.write_text(xml, encoding="utf-8")
        staged = Path(directory) / "unit-map.xodr"
        staged.write_text(xodr_text, encoding="utf-8")
        assert parse_xosc_subset(xosc, staged).map_reference == "unit-map.xodr"
        assert [entity.name for entity in interpret_xosc_subset(xosc, staged).entities] == ["ego", "lead"]


def test_full_scene_map_rejects_bare_names_and_global_scenarios(tmp_path) -> None:
    scenario = _local_scenario()
    with pytest.raises(ValueError, match="bare file name"):
        select_full_scene_map(scenario, map_name="m", road_filename="sub/dir.xodr", map_builder_version="v")
    with pytest.raises(ValueError, match="map name"):
        select_full_scene_map(scenario, map_name="", road_filename="m.xodr", map_builder_version="v")
    global_scenario = Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=scenario.ego_actor_id,
        actors=scenario.actors,
        coordinate_frame="nuscenes_global",
        provenance=scenario.provenance,
    )
    with pytest.raises(ValueError, match="local_road_aligned"):
        select_full_scene_map(global_scenario, map_name="m", road_filename="m.xodr", map_builder_version="v")


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
