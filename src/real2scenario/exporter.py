"""Deterministic baseline OpenSCENARIO export for local replay scenarios."""

from __future__ import annotations

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
        _append_entity(entities, actor)

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


def write_openscenario(
    scenario: Scenario, template: OpenDriveTemplate, output_path: str | Path
) -> Path:
    """Write deterministic baseline XML to ``output_path`` and return that path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    template_path = template.path()
    staged_template = path.parent / template_path.name
    staged_template.write_bytes(template_path.read_bytes())
    path.write_text(build_openscenario_xml(scenario, template), encoding="utf-8")
    return path


def _validate_export_input(scenario: Scenario, template: OpenDriveTemplate) -> None:
    if scenario.coordinate_frame != "local_road_aligned":
        raise ValueError("OpenSCENARIO export requires a 'local_road_aligned' scenario.")
    if scenario.provenance.get("opendrive_template_id") != template.template_id:
        raise ValueError("Scenario provenance does not identify the selected OpenDRIVE template.")
    non_ego_count = len(scenario.actors) - 1
    if not 1 <= non_ego_count <= 3:
        raise ValueError("OpenSCENARIO baseline export requires one to three non-ego actors.")


def _append_entity(entities: ET.Element, actor: Actor) -> None:
    scenario_object = ET.SubElement(entities, "ScenarioObject", {"name": actor.actor_id})
    vehicle = ET.SubElement(
        scenario_object,
        "Vehicle",
        {
            "name": actor.actor_type,
            "vehicleCategory": "car",
            "model3d": "",
        },
    )
    bounding_box = ET.SubElement(vehicle, "BoundingBox")
    ET.SubElement(bounding_box, "Center", {"x": "1.5", "y": "0", "z": "0.9"})
    ET.SubElement(
        bounding_box,
        "Dimensions",
        {"width": _number(actor.width_m or 1.8), "length": _number(actor.length_m or 4.5), "height": "1.5"},
    )
    ET.SubElement(vehicle, "Performance", {"maxSpeed": "70", "maxAcceleration": "10", "maxDeceleration": "10"})
    axles = ET.SubElement(vehicle, "Axles")
    ET.SubElement(axles, "FrontAxle", {"maxSteering": "0.5", "wheelDiameter": "0.7", "trackWidth": "1.5", "positionX": "2.8", "positionZ": "0.35"})
    ET.SubElement(axles, "RearAxle", {"maxSteering": "0", "wheelDiameter": "0.7", "trackWidth": "1.5", "positionX": "0", "positionZ": "0.35"})
    ET.SubElement(vehicle, "Properties")


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
    ET.SubElement(target, "AbsoluteTargetSpeed", {"value": _number(actor.trajectory[0].speed_mps)})


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
    _append_simulation_time_condition(start_trigger, "greaterThan", 0.0, edge="none")


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
