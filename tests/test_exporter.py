from xml.etree import ElementTree as ET

import pytest

from real2scenario import (
    Actor,
    Scenario,
    STRAIGHT_ROAD_TOPOLOGY,
    State,
    build_openscenario_xml,
    select_opendrive_template,
    write_openscenario,
)


def _selected_scenario() -> tuple[Scenario, object]:
    scenario = Scenario(
        scenario_id="export-fixture",
        duration_s=2.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle.ego", (State(0.0, 0.0, 0.0, 0.0, 4.0), State(2.0, 8.0, 0.0, 0.0, 4.0))),
            Actor("lead", "vehicle.car", (State(0.0, 12.0, 0.0, 0.0, 3.0), State(2.0, 18.0, 0.0, 0.0, 3.0))),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    return select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)


def test_exporter_generates_parseable_deterministic_xml() -> None:
    scenario, template = _selected_scenario()

    first = build_openscenario_xml(scenario, template)  # type: ignore[arg-type]
    second = build_openscenario_xml(scenario, template)  # type: ignore[arg-type]
    root = ET.fromstring(first)

    assert first == second
    assert root.tag == "OpenSCENARIO"
    assert root.find("RoadNetwork/LogicFile").attrib["filepath"] == "straight-two-lane-v1.xodr"
    assert [item.attrib["name"] for item in root.findall("Entities/ScenarioObject")] == ["ego", "lead"]
    assert [item.attrib["time"] for item in root.findall(".//Trajectory[@name='ego_recorded']/Shape/Polyline/Vertex")] == ["0", "2"]
    assert root.find(".//Trajectory[@name='ego_recorded']/../TimeReference/Timing").attrib == {
        "domainAbsoluteRelative": "relative",
        "scale": "1",
        "offset": "0",
    }
    assert root.find(".//Event[@name='ego_start']/StartTrigger/ConditionGroup/Condition").attrib[
        "conditionEdge"
    ] == "none"
    assert "/home/" not in first


def test_exporter_writes_the_xml_without_changing_content(tmp_path) -> None:
    scenario, template = _selected_scenario()
    output = tmp_path / "baseline.xosc"

    returned = write_openscenario(scenario, template, output)  # type: ignore[arg-type]

    assert returned == output
    assert output.read_text(encoding="utf-8") == build_openscenario_xml(scenario, template)  # type: ignore[arg-type]
    assert (tmp_path / "straight-two-lane-v1.xodr").read_text(encoding="utf-8").startswith("<?xml")


def test_exporter_rejects_more_than_three_non_ego_actors() -> None:
    scenario, template = _selected_scenario()
    actors = scenario.actors + tuple(
        Actor(f"actor-{number}", "vehicle.car", (State(0.0, float(number), 0.0, 0.0, 0.0),))
        for number in range(3)
    )
    oversized = Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=scenario.ego_actor_id,
        actors=actors,
        coordinate_frame=scenario.coordinate_frame,
        provenance=scenario.provenance,
    )

    with pytest.raises(ValueError, match="one to three"):
        build_openscenario_xml(oversized, template)  # type: ignore[arg-type]
