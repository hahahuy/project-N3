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


def test_exporter_keeps_vertex_attributes_compatible_with_esmini() -> None:
    scenario, template = _selected_scenario()
    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    assert all("speed" not in vertex.attrib for vertex in root.findall(".//Vertex"))
    assert root.find(".//Private[@entityRef='ego']//AbsoluteTargetSpeed").attrib["value"] == "0"


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


def _late_start_scenario() -> tuple[Scenario, object]:
    """A scenario whose non-ego track begins after the scenario start."""
    scenario = Scenario(
        scenario_id="export-late-start",
        duration_s=8.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle.ego", (State(0.0, 0.0, 0.0, 0.0, 4.0), State(8.0, 32.0, 0.0, 0.0, 4.0))),
            Actor(
                "lead",
                "vehicle.car",
                (
                    State(4.0, 12.0, 0.0, 0.0, 3.0),
                    State(6.0, 18.0, 0.0, 0.0, 3.0),
                    State(8.0, 24.0, 0.0, 0.0, 3.0),
                ),
            ),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    return select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)


def test_exporter_delays_trajectory_start_to_the_recorded_track_start() -> None:
    """A late-appearing actor must not be replayed from simulation time zero.

    Contract: each maneuver's StartTrigger fires at the actor's own first
    recorded timestamp. Starting it at zero makes esmini consume the entire
    recorded trajectory before the track has even begun, which leaves the actor
    ``start_time * speed`` metres ahead of recorded truth at every compared
    timestamp. Measured on the full 850-scene set this single condition accounted
    for ADE mean 16.040 m -> 1.138 m.
    """
    scenario, template = _late_start_scenario()

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    triggers = {
        group.find("Maneuver/Event").attrib["name"]: group.find(
            "Maneuver/Event/StartTrigger/ConditionGroup/Condition"
            "/ByValueCondition/SimulationTimeCondition"
        ).attrib["value"]
        for group in root.iter("ManeuverGroup")
    }

    assert triggers["ego_start"] == "0"
    assert triggers["lead_start"] == "4"

    # The polyline timeline itself must stay unshifted: a `relative` domain
    # offset would move vertex times rather than delay the follow.
    assert root.find(".//Trajectory[@name='lead_recorded']/../TimeReference/Timing").attrib[
        "offset"
    ] == "0"


def test_exporter_holds_actor_stationary_until_its_track_begins() -> None:
    """An actor must not move before its first recorded keyframe.

    Contract: the initial ``AbsoluteTargetSpeed`` is 0, not the actor's first
    recorded speed. Setting a non-zero speed makes esmini drive the entity away
    from its teleport pose for the whole window between simulation time zero and
    ``trajectory[0].time_s``, before the follow-trajectory trigger fires. For a
    late-appearing actor that is metres of invented travel.

    Measured on the full 850-scene nuScenes set, holding plus the matching
    StartTrigger took actor-track ADE median from 17.95 m to 0.022 m and the
    overall maximum from 157.80 m to 0.78 m. Tracks whose first keyframe is at
    t = 0 are numerically unchanged by both conditions.
    """
    scenario, template = _late_start_scenario()

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    speeds = {
        private.get("entityRef"): private.find(".//AbsoluteTargetSpeed").attrib["value"]
        for private in root.iter("Private")
    }

    assert speeds == {"ego": "0", "lead": "0"}


def test_exporter_keeps_position_following_mode() -> None:
    """Trajectory following must stay on ``position``, never ``timing``.

    Contract: the subset supports ``position`` following only. ``timing`` forces
    the entity to be at each 2 Hz polyline vertex at that vertex's own
    timestamp; consecutive vertices are ~0.5 s apart and differ in heading, so
    the follower has to accelerate and brake between every pair and overshoots
    at each vertex.

    Measured on the full 850-scene nuScenes v1.0-trainval set (3215 actor
    tracks, role A identity grid), with the trigger and hold conditions
    otherwise identical:

        followingMode   ADE median   ADE max     FDE max
        position        0.0586 m     0.8859 m    1.0298 m
        timing          0.1322 m     1.9154 m    1.8352 m

    ``timing`` is worse on every statistic, and by 9.4x on ADE max at the
    0.01 s timestep. This test exists because that regression reached main.
    """
    scenario, template = _late_start_scenario()

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    modes = {
        mode.attrib["followingMode"] for mode in root.iter("TrajectoryFollowingMode")
    }

    assert modes == {"position"}
