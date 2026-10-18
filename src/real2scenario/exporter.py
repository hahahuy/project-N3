"""Deterministic baseline OpenSCENARIO export for local replay scenarios."""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import Actor, Scenario, State
from .templates import OpenDriveTemplate


OPENSCENARIO_VERSION = "1.0"


def build_openscenario_xml(scenario: Scenario, template: OpenDriveTemplate) -> str:
    """Return deterministic OpenSCENARIO XML for a selected local road template."""
    _validate_export_input(scenario, template)
    root = ET.Element("OpenSCENARIO")
    ET.SubElement(
        root,
        "FileHeader",
        {
            "revMajor": "1",
            "revMinor": "1",
            "date": "1970-01-01T00:00:00",
            "description": "Real2Scenario baseline trajectory replay",
            "author": "real2scenario",
        },
    )
    parameters = ET.SubElement(root, "ParameterDeclarations")
    ET.SubElement(parameters, "ParameterDeclaration", {"name": "$ScenarioDuration", "parameterType": "double", "value": _number(scenario.duration_s)})
    catalog = ET.SubElement(root, "CatalogLocations")
    ET.SubElement(catalog, "VehicleCatalog", {"directory": ""})
    road_network = ET.SubElement(root, "RoadNetwork")
    ET.SubElement(road_network, "LogicFile", {"filepath": Path(template.relative_path).name})
    ET.SubElement(road_network, "SceneGraphFile", {"filepath": ""})

    entities = ET.SubElement(root, "Entities")
    for actor in scenario.actors:
        _append_entity(entities, actor, scenario)

    storyboard = ET.SubElement(root, "Storyboard")
    init = ET.SubElement(storyboard, "Init")
    init_actions = ET.SubElement(init, "Actions")
    for actor in scenario.actors:
        _append_initial_state(init_actions, actor)
    story = ET.SubElement(storyboard, "Story", {"name": "baseline_replay"})
    act = ET.SubElement(story, "Act", {"name": "recorded_trajectories"})
    for actor in scenario.actors:
        _append_maneuver_group(act, actor)
    _append_start_trigger(act)
    _append_stop_trigger(story, scenario.duration_s)
    _append_stop_trigger(storyboard, scenario.duration_s)

    ET.indent(root, space="  ")
    return "<?xml version='1.0' encoding='UTF-8'?>\n" + ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    ) + "\n"


def atomic_write_bytes(output_path: str | Path, data: bytes) -> Path:
    """Write ``data`` to ``output_path`` atomically (tmp file + rename).

    Served artifacts (wasm-pair roads, scenario XML) are read concurrently by
    browser fetches while a regeneration POST rewrites the same path: a
    direct write exposes truncated mid-attribute reads (measured: 561 KB of
    3.9 MB, then 0-byte reads), which the engine reports as opaque ``excPtr``.
    Rename is atomic on POSIX: readers see the old-complete or the
    new-complete file, never a partial one. Bytes identical either way.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)
    return path


def write_openscenario(
    scenario: Scenario, template: OpenDriveTemplate, output_path: str | Path
) -> Path:
    """Write deterministic baseline XML to ``output_path`` and return that path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    template_path = template.path()
    staged_template = path.parent / template_path.name
    atomic_write_bytes(staged_template, template_path.read_bytes())
    atomic_write_bytes(path, build_openscenario_xml(scenario, template).encode("utf-8"))
    return path


def _validate_export_input(scenario: Scenario, template: OpenDriveTemplate) -> None:
    if scenario.coordinate_frame != "local_road_aligned":
        raise ValueError("OpenSCENARIO export requires a 'local_road_aligned' scenario.")
    if scenario.provenance.get("opendrive_template_id") != template.template_id:
        raise ValueError("Scenario provenance does not identify the selected OpenDRIVE template.")
    non_ego_count = _non_ego_traffic_count(scenario)
    if not 1 <= non_ego_count <= 3:
        raise ValueError("OpenSCENARIO baseline export requires one to three non-ego actors.")


def _non_ego_traffic_count(scenario: Scenario) -> int:
    """Non-ego actors that are actual road users.

    The 1..3 export limit sizes the baseline road template to the traffic
    participants. A canvas branch committed with ``include_origin_reference``
    carries an extra actor that replays the edited actor's own recorded start
    trajectory, declared in provenance as ``origin_reference_actor_id``. That
    actor is a diagnostic overlay of the same vehicle, not another road user:
    counting it pushed every reference branch from 3 to 4 and made the WASM
    pair for that branch unexportable. Every scenario without that provenance
    key keeps the previous count exactly.
    """
    reference_id = scenario.provenance.get("origin_reference_actor_id")
    return sum(
        1 for actor in scenario.actors[1:] if actor.actor_id != reference_id
    )


def _append_entity(entities: ET.Element, actor: Actor, scenario: Scenario) -> None:
    """Emit one scenario object with an entity tag matching the source taxonomy.

    ``vehicle.*`` keeps the historical ``Vehicle`` encoding byte-identical so the
    measured replay baseline is unaffected. ``human.*`` emits ``Pedestrian`` and
    anything else emits ``MiscObject`` (category ``other``); the unmodified
    source taxonomy is always preserved in the entity properties. Motion for all
    tags remains defined solely by the recorded trajectory with
    ``followingMode="position"`` and a zero initial-speed hold.
    """
    scenario_object = ET.SubElement(entities, "ScenarioObject", {"name": actor.actor_id})
    if actor.actor_type.startswith("human."):
        _append_pedestrian(scenario_object, actor, scenario)
    elif actor.actor_type.startswith("vehicle."):
        _append_vehicle(scenario_object, actor, scenario)
    else:
        _append_misc_object(scenario_object, actor, scenario)


def _append_vehicle(scenario_object: ET.Element, actor: Actor, scenario: Scenario) -> None:
    vehicle = ET.SubElement(
        scenario_object,
        "Vehicle",
        {
            "name": actor.actor_type,
            "vehicleCategory": _vehicle_category(actor.actor_type),
            "model3d": "",
        },
    )
    bounding_box = ET.SubElement(vehicle, "BoundingBox")
    ET.SubElement(bounding_box, "Center", {"x": _number(_box_center_x(actor)), "y": "0", "z": _number(_box_center_z(actor))})
    ET.SubElement(
        bounding_box,
        "Dimensions",
        {
            "width": _number(actor.width_m or 1.8),
            "length": _number(actor.length_m or 4.5),
            "height": _number(actor.height_m or 1.5),
        },
    )
    ET.SubElement(vehicle, "Performance", {"maxSpeed": "70", "maxAcceleration": "10", "maxDeceleration": "10"})
    axles = ET.SubElement(vehicle, "Axles")
    ET.SubElement(axles, "FrontAxle", {"maxSteering": "0.5", "wheelDiameter": "0.7", "trackWidth": "1.5", "positionX": "2.8", "positionZ": "0.35"})
    ET.SubElement(axles, "RearAxle", {"maxSteering": "0", "wheelDiameter": "0.7", "trackWidth": "1.5", "positionX": "0", "positionZ": "0.35"})
    _append_entity_properties(ET.SubElement(vehicle, "Properties"), actor, scenario)


def _pedestrian_category(actor_type: str) -> str:
    """Map a ``human.*`` taxonomy onto esmini's readable pedestrian categories.

    esmini accepts only `pedestrian`, `wheelchair`, `animal` — anything else
    logs an error and leaves the category unset. The unmodified source taxonomy
    is always preserved in the entity properties.
    """
    if actor_type == "human.pedestrian.wheelchair":
        return "wheelchair"
    return "pedestrian"


def _append_pedestrian(scenario_object: ET.Element, actor: Actor, scenario: Scenario) -> None:
    """Emit a ``human.*`` actor as an OpenSCENARIO pedestrian.

    Mass is inert under position following (no dynamics are simulated) and the
    recorded annotations carry no mass; the fixed default is documented here
    rather than derived. Bounding-box fallbacks mirror the vehicle pattern at a
    pedestrian scale.
    """
    pedestrian = ET.SubElement(
        scenario_object,
        "Pedestrian",
        {
            "name": actor.actor_type,
            "mass": "75",
            "model": "",
            "pedestrianCategory": _pedestrian_category(actor.actor_type),
        },
    )
    bounding_box = ET.SubElement(pedestrian, "BoundingBox")
    ET.SubElement(
        bounding_box,
        "Center",
        {"x": "0", "y": "0", "z": _number((actor.height_m or 1.7) / 2.0)},
    )
    ET.SubElement(
        bounding_box,
        "Dimensions",
        {
            "width": _number(actor.width_m or 0.6),
            "length": _number(actor.length_m or 0.6),
            "height": _number(actor.height_m or 1.7),
        },
    )
    _append_entity_properties(ET.SubElement(pedestrian, "Properties"), actor, scenario)


_MISC_CATEGORY_BY_ACTOR_TYPE = {
    # Exact-only mapping: the source string must equal an esmini-readable
    # value verbatim (see `MiscObject::SetCategory`). Everything else stays
    # `none` — approximate mappings would invent facts.
    "movable_object.barrier": "barrier",
}


def _misc_category(actor_type: str) -> str:
    """Map a non-vehicle non-human taxonomy onto an esmini misc category."""
    return _MISC_CATEGORY_BY_ACTOR_TYPE.get(actor_type, "none")


def _append_misc_object(scenario_object: ET.Element, actor: Actor, scenario: Scenario) -> None:
    """Emit any other taxonomy (e.g. ``movable_object.*``) as a misc object.

    The attribute name must be ``miscObjectCategory`` (lowercase `m`) —
    esmini never reads the capitalized form. The value is `none` except for
    exact string matches; the exact source taxonomy is always preserved in
    the entity properties.
    """
    misc = ET.SubElement(
        scenario_object,
        "MiscObject",
        {"name": actor.actor_type, "miscObjectCategory": _misc_category(actor.actor_type), "mass": "0"},
    )
    bounding_box = ET.SubElement(misc, "BoundingBox")
    ET.SubElement(
        bounding_box,
        "Center",
        {"x": "0", "y": "0", "z": _number((actor.height_m or 1.0) / 2.0)},
    )
    ET.SubElement(
        bounding_box,
        "Dimensions",
        {
            "width": _number(actor.width_m or 0.5),
            "length": _number(actor.length_m or 0.5),
            "height": _number(actor.height_m or 1.0),
        },
    )
    _append_entity_properties(ET.SubElement(misc, "Properties"), actor, scenario)


_VEHICLE_CATEGORY_BY_ACTOR_TYPE = {
    "vehicle.bicycle": "bicycle",
    "vehicle.bus.bendy": "bus",
    "vehicle.bus.rigid": "bus",
    # esmini names it "motorbike": "motorcycle" is unread (LOG_ERROR).
    "vehicle.motorcycle": "motorbike",
    "vehicle.trailer": "trailer",
    "vehicle.truck": "truck",
}


def _vehicle_category(actor_type: str) -> str:
    """Map a source taxonomy name onto an OpenSCENARIO vehicle category.

    Unknown or ``vehicle.*`` subtypes stay ``car`` rather than being invented:
    a wrong category would change replay behaviour, while a conservative default
    preserves the measured baseline. The unmodified source taxonomy is always
    preserved in the entity properties. Every mapped value must be readable by
    esmini (see its `Vehicle::SetCategory`); an unread value logs an error and
    leaves the category unset.
    """
    return _VEHICLE_CATEGORY_BY_ACTOR_TYPE.get(actor_type, "car")


def _box_center_x(actor: Actor) -> float:
    """Bounding-box centre offset along the actor's own length axis."""
    return (actor.length_m or 4.5) / 3.0


def _box_center_z(actor: Actor) -> float:
    """Bounding-box centre height above the road surface."""
    return (actor.height_m or 1.5) / 2.0


def _append_entity_properties(properties: ET.Element, actor: Actor, scenario: Scenario) -> None:
    """Record source provenance and lifecycle as inert entity metadata.

    None of these properties steers the simulator. They exist so a reviewer or
    a diagnostic can recover actor identity, taxonomy, the recorded observation
    window and the trajectory time origin without re-deriving them from the
    canonical artifact. Motion remains defined solely by the recorded
    trajectory, and the initial-speed policy stays at zero.
    """
    entries = (
        ("source_actor_type", actor.actor_type),
        ("source_actor_id", actor.actor_id),
        ("coordinate_frame", scenario.coordinate_frame),
        ("replay_mode", scenario.replay_mode),
        ("observed_start_s", _number(actor.observed_start_s)),
        ("observed_end_s", _number(actor.observed_end_s)),
        ("observation_count", str(actor.observation_count)),
        (
            "lifecycle_status",
            actor.lifecycle_status(0.0, scenario.duration_s),
        ),
        ("trajectory_time_origin_s", _number(actor.trajectory[0].time_s)),
        ("trajectory_last_vertex_s", _number(actor.trajectory[-1].time_s)),
        ("initial_speed_policy", "hold_zero_until_trajectory_start"),
        ("recorded_initial_speed_mps", _number(actor.trajectory[0].speed_mps)),
    )
    transform_version = scenario.provenance.get("coordinate_transform_version")
    if transform_version:
        entries = entries + (("coordinate_transform_version", transform_version),)
    template_id = scenario.provenance.get("opendrive_template_id")
    if template_id:
        entries = entries + (("opendrive_template_id", template_id),)
    for name, value in entries:
        ET.SubElement(properties, "Property", {"name": name, "value": value})


def _append_initial_state(actions: ET.Element, actor: Actor) -> None:
    private = ET.SubElement(actions, "Private", {"entityRef": actor.actor_id})
    private_action = ET.SubElement(private, "PrivateAction")
    teleport = ET.SubElement(private_action, "TeleportAction")
    position = ET.SubElement(teleport, "Position")
    _append_world_position(position, actor.trajectory[0])
    private_action = ET.SubElement(private, "PrivateAction")
    longitudinal = ET.SubElement(private_action, "LongitudinalAction")
    speed_action = ET.SubElement(longitudinal, "SpeedAction")
    ET.SubElement(speed_action, "SpeedActionDynamics", {"dynamicsShape": "step", "value": "0", "dynamicsDimension": "time"})
    target = ET.SubElement(speed_action, "SpeedActionTarget")
    ET.SubElement(target, "AbsoluteTargetSpeed", {"value": "0"})


def _append_maneuver_group(act: ET.Element, actor: Actor) -> None:
    group = ET.SubElement(act, "ManeuverGroup", {"name": f"{actor.actor_id}_trajectory", "maximumExecutionCount": "1"})
    actors = ET.SubElement(group, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": actor.actor_id})
    maneuver = ET.SubElement(group, "Maneuver", {"name": f"{actor.actor_id}_follow"})
    event = ET.SubElement(maneuver, "Event", {"name": f"{actor.actor_id}_start", "priority": "overwrite"})
    action = ET.SubElement(event, "Action", {"name": f"{actor.actor_id}_follow_trajectory"})
    private_action = ET.SubElement(action, "PrivateAction")
    routing = ET.SubElement(private_action, "RoutingAction")
    follow = ET.SubElement(routing, "FollowTrajectoryAction")
    trajectory = ET.SubElement(follow, "Trajectory", {"name": f"{actor.actor_id}_recorded", "closed": "false"})
    shape = ET.SubElement(trajectory, "Shape")
    polyline = ET.SubElement(shape, "Polyline")
    for state in actor.trajectory:
        vertex = ET.SubElement(polyline, "Vertex", {"time": _number(state.time_s)})
        position = ET.SubElement(vertex, "Position")
        _append_world_position(position, state)
    time_reference = ET.SubElement(follow, "TimeReference")
    ET.SubElement(
        time_reference,
        "Timing",
        {"domainAbsoluteRelative": "relative", "scale": "1", "offset": "0"},
    )
    ET.SubElement(follow, "TrajectoryFollowingMode", {"followingMode": "position"})
    start_trigger = ET.SubElement(event, "StartTrigger")
    _append_simulation_time_condition(
        start_trigger, "greaterThan", actor.trajectory[0].time_s, edge="none"
    )


def _append_start_trigger(parent: ET.Element) -> None:
    start_trigger = ET.SubElement(parent, "StartTrigger")
    _append_simulation_time_condition(start_trigger, "greaterThan", 0.0)


def _append_stop_trigger(parent: ET.Element, duration_s: float) -> None:
    stop_trigger = ET.SubElement(parent, "StopTrigger")
    _append_simulation_time_condition(stop_trigger, "greaterThan", duration_s)


def _append_simulation_time_condition(
    trigger: ET.Element, rule: str, value: float, *, edge: str = "rising"
) -> None:
    condition_group = ET.SubElement(trigger, "ConditionGroup")
    condition = ET.SubElement(
        condition_group,
        "Condition",
        {"name": "simulation_time", "delay": "0", "conditionEdge": edge},
    )
    by_value = ET.SubElement(condition, "ByValueCondition")
    ET.SubElement(by_value, "SimulationTimeCondition", {"value": _number(value), "rule": rule})


def _append_world_position(parent: ET.Element, state: State) -> None:
    ET.SubElement(
        parent,
        "WorldPosition",
        {
            "x": _number(state.x_m),
            "y": _number(state.y_m),
            "z": "0",
            "h": _number(state.yaw_rad),
            "p": "0",
            "r": "0",
        },
    )


def _number(value: float) -> str:
    return format(value, ".17g")
