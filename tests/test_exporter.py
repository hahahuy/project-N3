from xml.etree import ElementTree as ET

import threading

import pytest

from real2scenario import (
    Actor,
    Scenario,
    STRAIGHT_ROAD_TOPOLOGY,
    State,
    atomic_write_bytes,
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


def test_exporter_records_lifecycle_and_provenance_as_inert_properties() -> None:
    """Lifecycle/timing metadata must be visible without steering the simulator.

    Contract: the recorded observation window, trajectory time origin, source
    taxonomy and the initial-speed policy are emitted as ``Property`` entries on
    the entity. None of them may change the simulation: the polyline vertices,
    the ``position`` following mode, the per-actor ``StartTrigger`` and the
    zero initial ``AbsoluteTargetSpeed`` all stay exactly as the measured
    baseline requires.
    """
    scenario, template = _late_start_scenario()

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    properties = {
        item.get("name"): item.get("value")
        for item in root.findall(".//Entities/ScenarioObject/Vehicle/Properties/Property")
    }
    assert properties["source_actor_type"] == "vehicle.car"
    assert properties["source_actor_id"] == "lead"
    assert properties["observed_start_s"] == "4"
    assert properties["observed_end_s"] == "8"
    assert properties["observation_count"] == "3"
    assert properties["lifecycle_status"] == "late_entry"
    assert properties["trajectory_time_origin_s"] == "4"
    assert properties["initial_speed_policy"] == "hold_zero_until_trajectory_start"
    assert properties["replay_mode"] == "open_loop_trajectory"

    # The measured replay baseline must be untouched by the metadata.
    speeds = {
        private.get("entityRef"): private.find(".//AbsoluteTargetSpeed").attrib["value"]
        for private in root.iter("Private")
    }
    assert speeds == {"ego": "0", "lead": "0"}
    assert {
        mode.attrib["followingMode"] for mode in root.iter("TrajectoryFollowingMode")
    } == {"position"}


def test_exporter_uses_recorded_actor_dimensions_instead_of_constants() -> None:
    """Bounding-box height and centre must come from the recorded annotation.

    The exporter previously hardcoded ``height=1.5`` and a fixed centre, so a
    recorded truck or trailer rendered with the wrong cuboid in every replay
    surface. Dimensions must pass through unchanged.
    """
    scenario = Scenario(
        scenario_id="export-dimensions",
        duration_s=2.0,
        ego_actor_id="truck",
        actors=(
            Actor(
                "truck",
                "vehicle.truck",
                (State(0.0, 0.0, 0.0, 0.0, 5.0), State(2.0, 10.0, 0.0, 0.0, 5.0)),
                length_m=12.5,
                width_m=2.9,
                height_m=3.6,
            ),
            Actor(
                "car",
                "vehicle.car",
                (State(0.0, 20.0, 0.0, 0.0, 5.0), State(2.0, 30.0, 0.0, 0.0, 5.0)),
                length_m=4.5,
                width_m=1.8,
                height_m=1.5,
            ),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    scenario, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    dimensions = root.find(
        "./Entities/ScenarioObject[@name='truck']/Vehicle/BoundingBox/Dimensions"
    )
    assert dimensions is not None
    assert float(dimensions.attrib["height"]) == 3.6
    assert float(dimensions.attrib["length"]) == 12.5
    assert float(dimensions.attrib["width"]) == 2.9
    assert (
        root.find("./Entities/ScenarioObject[@name='truck']/Vehicle").attrib["vehicleCategory"]
        == "truck"
    )


def test_exporter_emits_renault_zoe_ego_dimensions() -> None:
    """The nuScenes recording vehicle uses the documented Zoe body dimensions."""
    scenario = Scenario(
        scenario_id="export-zoe-ego",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(
            Actor(
                "ego",
                "vehicle.ego",
                (State(0.0, 0.0, 0.0, 0.0, 0.0),),
                length_m=4.084,
                width_m=1.730,
                height_m=1.562,
            ),
            Actor("lead", "vehicle.car", (State(0.0, 10.0, 0.0, 0.0, 0.0),)),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "nuScenes"},
    )
    scenario, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]
    dimensions = root.find("./Entities/ScenarioObject[@name='ego']/Vehicle/BoundingBox/Dimensions")
    center = root.find("./Entities/ScenarioObject[@name='ego']/Vehicle/BoundingBox/Center")

    assert dimensions is not None
    assert center is not None
    assert float(dimensions.attrib["width"]) == pytest.approx(1.730)
    assert float(dimensions.attrib["length"]) == pytest.approx(4.084)
    assert float(dimensions.attrib["height"]) == pytest.approx(1.562)
    assert float(center.attrib["x"]) == pytest.approx(4.084 / 3.0)
    assert center.attrib["y"] == "0"
    assert float(center.attrib["z"]) == pytest.approx(1.562 / 2.0)


def test_exporter_maps_known_vehicle_categories_and_defaults_conservatively() -> None:
    """An unmapped subtype stays ``car`` rather than being guessed.

    A wrong ``vehicleCategory`` changes replay behaviour. Unknown or plain
    ``vehicle.*`` subtypes therefore keep the measured ``car`` default while the
    unmodified source taxonomy is still preserved in the entity properties.
    """
    scenario = Scenario(
        scenario_id="export-categories",
        duration_s=1.0,
        ego_actor_id="bicycle",
        actors=(
            Actor("bicycle", "vehicle.bicycle", (State(0.0, 0.0, 0.0, 0.0, 2.0),)),
            Actor("ego", "vehicle.unknown_future_type", (State(0.0, 10.0, 0.0, 0.0, 2.0),)),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    scenario, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    categories = {
        obj.attrib["name"]: obj.find("Vehicle").attrib["vehicleCategory"]
        for obj in root.findall("./Entities/ScenarioObject")
    }
    assert categories == {"bicycle": "bicycle", "ego": "car"}


def test_exporter_uses_esmini_readable_category_values() -> None:
    """Every emitted category must be readable by esmini, not just schema-shaped.

    esmini logs `LOG_ERROR` and leaves the category unset for anything outside
    its own value lists (`Vehicle::SetCategory` has `motorbike`, not
    `motorcycle`; `Pedestrian` accepts `pedestrian`/`wheelchair`/`animal`;
    `MiscObject` has no `other`). An unread value is a dead mapping.
    """
    scenario = Scenario(
        scenario_id="export-readable-categories",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle.ego", (State(0.0, 0.0, 0.0, 0.0, 2.0),)),
            Actor("moto", "vehicle.motorcycle", (State(0.0, 5.0, 0.0, 0.0, 2.0),)),
            Actor("chair", "human.pedestrian.wheelchair", (State(0.0, 3.0, 1.0, 0.0, 1.0),)),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    scenario, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    assert root.find("./Entities/ScenarioObject[@name='moto']/Vehicle").attrib["vehicleCategory"] == "motorbike"
    assert root.find("./Entities/ScenarioObject[@name='chair']/Pedestrian").attrib["pedestrianCategory"] == "wheelchair"


def test_exporter_maps_only_exact_misc_categories() -> None:
    """`movable_object.barrier` is an exact esmini value; all else stays `none`.

    Approximate mappings (e.g. traffic cones as `obstacle`) would invent facts:
    nothing in the source record says the object is an obstacle in esmini's
    sense. The unmodified source taxonomy is preserved in Properties either way.
    """
    scenario = Scenario(
        scenario_id="export-misc-exact",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle.ego", (State(0.0, 0.0, 0.0, 0.0, 2.0),)),
            Actor("barr", "movable_object.barrier", (State(0.0, 5.0, 0.0, 0.0, 0.0),)),
            Actor("cone", "movable_object.trafficcone", (State(0.0, 3.0, 1.0, 0.0, 0.0),)),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    scenario, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    assert root.find("./Entities/ScenarioObject[@name='barr']/MiscObject").attrib["miscObjectCategory"] == "barrier"
    assert root.find("./Entities/ScenarioObject[@name='cone']/MiscObject").attrib["miscObjectCategory"] == "none"


def test_exporter_emits_pedestrian_and_misc_object_entities() -> None:
    """Owner-approved population widening (2026-10-16): matching entity tags.

    ``vehicle.*`` keeps the historical ``Vehicle`` encoding byte-identical (see
    the determinism test above); only the entity tag routes by source taxonomy.
    ``human.*`` emits ``Pedestrian`` and anything else emits ``MiscObject`` with
    the conservative ``other`` category. Provenance properties are preserved on
    every tag and motion stays position-followed with a zero-speed hold.
    """
    scenario = Scenario(
        scenario_id="export-pedestrian",
        duration_s=2.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle.ego", (State(0.0, 0.0, 0.0, 0.0, 4.0), State(2.0, 8.0, 0.0, 0.0, 4.0))),
            Actor("walk1", "human.pedestrian.adult", (State(0.0, 3.0, 1.0, 0.0, 1.2), State(2.0, 5.0, 1.0, 0.0, 1.2)), 0.6, 0.6, 1.7),
            Actor("cone1", "movable_object.cone", (State(0.0, 6.0, 0.0, 0.0, 0.0), State(2.0, 6.0, 0.0, 0.0, 0.0)), 0.4, 0.4, 0.8),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    scenario, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)

    root = ET.fromstring(build_openscenario_xml(scenario, template))  # type: ignore[arg-type]

    tags = {
        obj.attrib["name"]: list(obj)[0].tag
        for obj in root.findall("./Entities/ScenarioObject")
    }
    assert tags == {"ego": "Vehicle", "walk1": "Pedestrian", "cone1": "MiscObject"}
    assert root.find("./Entities/ScenarioObject[@name='walk1']/Vehicle") is None
    assert root.find("./Entities/ScenarioObject[@name='walk1']/Pedestrian/Performance") is None
    assert root.find("./Entities/ScenarioObject[@name='walk1']/Pedestrian/Axles") is None
    assert (
        root.find("./Entities/ScenarioObject[@name='cone1']/MiscObject").attrib["miscObjectCategory"]
        == "none"
    )
    assert (
        root.find("./Entities/ScenarioObject[@name='walk1']/Pedestrian").attrib["pedestrianCategory"]
        == "pedestrian"
    )
    for name, taxonomy in (
        ("ego", "vehicle.ego"),
        ("walk1", "human.pedestrian.adult"),
        ("cone1", "movable_object.cone"),
    ):
        properties = {
            item.attrib["name"]: item.attrib["value"]
            for item in root.findall(f"./Entities/ScenarioObject[@name='{name}']/*/Properties/Property")
        }
        assert properties["source_actor_type"] == taxonomy
        assert properties["initial_speed_policy"] == "hold_zero_until_trajectory_start"
    dimensions = root.find("./Entities/ScenarioObject[@name='walk1']/Pedestrian/BoundingBox/Dimensions").attrib
    assert (float(dimensions["width"]), float(dimensions["length"]), float(dimensions["height"])) == (0.6, 0.6, 1.7)
    assert {mode.attrib["followingMode"] for mode in root.iter("TrajectoryFollowingMode")} == {"position"}
    assert root.find(".//AbsoluteTargetSpeed").attrib == {"value": "0"}


def test_pedestrian_export_passes_fail_closed_validators(tmp_path) -> None:
    """The new entity tags need no validator change: both validators are tag-agnostic."""
    from real2scenario.xosc_subset import interpret_xosc_subset, parse_xosc_subset

    scenario = Scenario(
        scenario_id="export-pedestrian-validated",
        duration_s=2.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle.ego", (State(0.0, 0.0, 0.0, 0.0, 4.0), State(2.0, 8.0, 0.0, 0.0, 4.0))),
            Actor("walk1", "human.pedestrian.adult", (State(0.0, 3.0, 1.0, 0.0, 1.2), State(2.0, 5.0, 1.0, 0.0, 1.2))),
        ),
        coordinate_frame="local_road_aligned",
        provenance={"dataset": "synthetic"},
    )
    scenario, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)
    xosc = tmp_path / "scenario.xosc"
    xosc.write_text(build_openscenario_xml(scenario, template), encoding="utf-8")  # type: ignore[arg-type]

    assert parse_xosc_subset(xosc, template.path()).entity_names == ("ego", "walk1")  # type: ignore[union-attr]
    assert [entity.name for entity in interpret_xosc_subset(xosc, template.path()).entities] == ["ego", "walk1"]


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


def test_atomic_write_bytes_never_exposes_partial_reads(tmp_path) -> None:
    """Concurrent regeneration must never serve a half-written artifact.

    Measured failure: two overlapping wasm-pair POSTs (dev StrictMode
    double-mount) served 561 KB of a 3.9 MB road, then 0-byte reads, and the
    engine died with opaque ``excPtr``. Rename is atomic: every read below
    must observe exactly one complete generation.
    """
    target = tmp_path / "road.xodr"
    first = b"<a>" + b"x" * 500000 + b"</a>"
    second = b"<b>" + b"y" * 500000 + b"</b>"
    errors: list[str] = []

    def rewrite() -> None:
        try:
            for _ in range(30):
                atomic_write_bytes(target, first)
                atomic_write_bytes(target, second)
        except OSError as error:
            errors.append(str(error))

    def observe() -> None:
        try:
            for _ in range(300):
                try:
                    content = target.read_bytes()
                except FileNotFoundError:
                    continue
                assert content in (first, second), f"partial read of {len(content)} bytes"
        except AssertionError as error:
            errors.append(str(error))

    writer = threading.Thread(target=rewrite)
    readers = [threading.Thread(target=observe) for _ in range(3)]
    writer.start()
    for reader in readers:
        reader.start()
    writer.join()
    for reader in readers:
        reader.join()
    assert not errors
