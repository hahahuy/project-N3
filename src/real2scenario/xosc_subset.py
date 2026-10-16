"""Fail-closed parser contract for the project's OpenSCENARIO subset."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


XOSC_SUBSET_VERSION = "r2s-xosc-subset-v1"


@dataclass(frozen=True, slots=True)
class XoscExecutionIdentity:
    xosc_sha256: str
    xodr_sha256: str | None
    subset_version: str = XOSC_SUBSET_VERSION


@dataclass(frozen=True, slots=True)
class ValidatedXoscScenario:
    source_path: str
    map_reference: str | None
    entity_names: tuple[str, ...]
    initial_positions: dict[str, tuple[float, float, float, float]]
    trajectories: dict[str, tuple[tuple[float, float, float, float, float], ...]]
    subset_version: str = XOSC_SUBSET_VERSION


def build_execution_identity(xosc_path: str | Path, xodr_path: str | Path | None) -> XoscExecutionIdentity:
    return XoscExecutionIdentity(
        xosc_sha256=_sha256(Path(xosc_path)),
        xodr_sha256=None if xodr_path is None else _sha256(Path(xodr_path)),
    )


def parse_xosc_subset(
    xosc_path: str | Path, xodr_path: str | Path | None
) -> ValidatedXoscScenario:
    path = Path(xosc_path)
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as error:
        raise ValueError(f"invalid_xosc: {error}") from error
    if root.tag != "OpenSCENARIO":
        raise ValueError("unsupported_xosc_feature: root must be OpenSCENARIO")
    unsupported = root.find("Environment")
    if unsupported is not None:
        raise ValueError("unsupported_xosc_feature: /OpenSCENARIO/Environment")
    logic = root.find("./RoadNetwork/LogicFile")
    map_reference = None if logic is None else logic.get("filepath")
    if xodr_path is not None and not Path(xodr_path).is_file():
        raise ValueError("map_asset_missing")
    entities = tuple(item.get("name", "") for item in root.findall("./Entities/ScenarioObject"))
    if not entities or any(not name for name in entities):
        raise ValueError("invalid_xosc: entities must have names")
    if len(entities) != len(set(entities)):
        raise ValueError("invalid_xosc: duplicate entity name")
    for element in root.iter():
        if element.tag in {"Environment", "Route", "AcquirePosition", "LanePosition", "RoadPosition"}:
            raise ValueError(f"unsupported_xosc_feature: {element.tag}")
    initial_positions: dict[str, tuple[float, float, float, float]] = {}
    for private in root.findall("./Storyboard/Init/Actions/Private"):
        entity = private.get("entityRef", "")
        position = private.find("./PrivateAction/TeleportAction/Position/WorldPosition")
        if not entity or position is None:
            raise ValueError("invalid_xosc: missing initial teleport position")
        initial_positions[entity] = tuple(
            float(position.get(name, "0")) for name in ("x", "y", "z", "h")
        )
    trajectories: dict[str, tuple[tuple[float, float, float, float, float], ...]] = {}
    for group in root.findall("./Storyboard/Story/Act/ManeuverGroup"):
        entity_ref = group.find("./Actors/EntityRef")
        entity = None if entity_ref is None else entity_ref.get("entityRef")
        vertices = group.findall("./Maneuver/Event/Action/PrivateAction/RoutingAction/FollowTrajectoryAction/Trajectory/Shape/Polyline/Vertex")
        if entity and vertices:
            trajectories[entity] = tuple(
                _vertex_to_tuple(vertex)
                for vertex in vertices
            )
    return ValidatedXoscScenario(path.as_posix(), map_reference, entities, initial_positions, trajectories)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vertex_to_tuple(vertex: ET.Element) -> tuple[float, float, float, float, float]:
    position = vertex.find("./Position/WorldPosition")
    if position is None:
        raise ValueError("invalid_xosc: trajectory vertex lacks WorldPosition")
    return (
        float(vertex.get("time", "0")),
        float(position.get("x", "0")),
        float(position.get("y", "0")),
        float(position.get("h", "0")),
        float(position.get("z", "0")),
    )


XOSC_INTERPRETER_VERSION = "r2s-xosc-interpreter-v1"

UNSUPPORTED_XOSC_ELEMENTS = frozenset(
    {
        "Environment",
        "Route",
        "AcquirePosition",
        "LanePosition",
        "RoadPosition",
        "RelativeDistanceToMasterEntityPosition",
        "DistanceCondition",
        "ReachPositionCondition",
        "TraveledDistanceCondition",
        "EndOfRoadCondition",
        "CollisionCondition",
        "TimeToCollisionCondition",
        "StandStillCondition",
        "ParameterSet",
        "VariableAction",
        "ActivateControllerAction",
        "ControllerAction",
        "VisibilityAction",
        "SynchronizeAction",
        "OverrideControllerValueAction",
        "EntityController",
        "CatalogReference",
    }
)


@dataclass(frozen=True, slots=True)
class XoscConditionInterpretation:
    """One interpreted trigger condition."""

    name: str
    delay_s: float
    condition_edge: str
    rule: str
    value: float


@dataclass(frozen=True, slots=True)
class XoscEntityInterpretation:
    """Everything the interpreter resolved for one scenario object."""

    name: str
    initial_position: tuple[float, float, float, float]
    trajectory: tuple[tuple[float, float, float, float, float], ...]
    maneuver_group_name: str
    event_name: str
    time_reference_domain: str
    time_reference_scale: float
    time_reference_offset_s: float
    start_conditions: tuple[XoscConditionInterpretation, ...]
    stop_conditions: tuple[XoscConditionInterpretation, ...]
    act_start_conditions: tuple[XoscConditionInterpretation, ...] = ()

    @property
    def state_count(self) -> int:
        return len(self.trajectory)

    @property
    def duration_s(self) -> float:
        return self.trajectory[-1][0] if self.trajectory else 0.0

    @property
    def starts_at_zero(self) -> bool:
        """Timing edits may legitimately start a trajectory after time zero."""
        return bool(self.trajectory) and abs(self.trajectory[0][0]) <= 1e-9


@dataclass(frozen=True, slots=True)
class XoscInterpretation:
    """Deterministic, fail-closed interpretation of one project XOSC file."""

    source_path: str
    map_reference: str | None
    act_name: str
    entities: tuple[XoscEntityInterpretation, ...]
    identity: XoscExecutionIdentity
    story_name: str = ""
    story_stop_conditions: tuple[XoscConditionInterpretation, ...] = ()
    subset_version: str = XOSC_SUBSET_VERSION
    interpreter_version: str = XOSC_INTERPRETER_VERSION

    def by_name(self, name: str) -> XoscEntityInterpretation:
        for entity in self.entities:
            if entity.name == name:
                return entity
        raise KeyError(f"Scenario object {name!r} was not interpreted.")

    @property
    def interpretation_to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe interpretation data."""
        return {
            "interpreter_version": self.interpreter_version,
            "subset_version": self.subset_version,
            "map_reference": self.map_reference,
            "act_name": self.act_name,
            "story_name": self.story_name,
            "story_stop_conditions": [
                {
                    "name": condition.name,
                    "delay_s": condition.delay_s,
                    "condition_edge": condition.condition_edge,
                    "rule": condition.rule,
                    "value": condition.value,
                }
                for condition in self.story_stop_conditions
            ],
            "execution_identity": {
                "xosc_sha256": self.identity.xosc_sha256,
                "xodr_sha256": self.identity.xodr_sha256,
            },
            "entities": [
                {
                    "name": entity.name,
                    "state_count": entity.state_count,
                    "duration_s": entity.duration_s,
                    "starts_at_zero": entity.starts_at_zero,
                    "start_time_s": entity.trajectory[0][0] if entity.trajectory else None,
                    "initial_position": list(entity.initial_position),
                    "time_reference": {
                        "domain": entity.time_reference_domain,
                        "scale": entity.time_reference_scale,
                        "offset_s": entity.time_reference_offset_s,
                    },
                    "start_conditions": [
                        {
                            "name": condition.name,
                            "delay_s": condition.delay_s,
                            "condition_edge": condition.condition_edge,
                            "rule": condition.rule,
                            "value": condition.value,
                        }
                        for condition in entity.start_conditions
                    ],
                    "stop_conditions": [
                        {
                            "name": condition.name,
                            "delay_s": condition.delay_s,
                            "condition_edge": condition.condition_edge,
                            "rule": condition.rule,
                            "value": condition.value,
                        }
                        for condition in entity.stop_conditions
                    ],
                }
                for entity in self.entities
            ],
        }


def interpret_xosc_subset(
    xosc_path: str | Path, xodr_path: str | Path | None
) -> XoscInterpretation:
    """Interpret a project XOSC file into an auditable execution plan.

    The interpreter is deliberately strict. It resolves the Init teleports, the
    Act/ManeuverGroup/Event structure, the FollowTrajectoryAction time
    reference and the start/stop trigger conditions for every scenario object,
    and it rejects anything outside the declared subset instead of guessing.
    """
    path = Path(xosc_path)
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as error:
        raise ValueError(f"invalid_xosc: {error}") from error
    if root.tag != "OpenSCENARIO":
        raise ValueError("unsupported_xosc_feature: root must be OpenSCENARIO")
    unsupported = sorted({element.tag for element in root.iter() if element.tag in UNSUPPORTED_XOSC_ELEMENTS})
    if unsupported:
        raise ValueError(f"unsupported_xosc_feature: {', '.join(unsupported)}")
    logic = root.find("./RoadNetwork/LogicFile")
    map_reference = None if logic is None else logic.get("filepath")
    if xodr_path is not None and not Path(xodr_path).is_file():
        raise ValueError("map_asset_missing")

    initial_positions: dict[str, tuple[float, float, float, float]] = {}
    for private in root.findall("./Storyboard/Init/Actions/Private"):
        entity = private.get("entityRef", "")
        position = private.find("./PrivateAction/TeleportAction/Position/WorldPosition")
        if not entity or position is None:
            raise ValueError("invalid_xosc: missing initial teleport position")
        if entity in initial_positions:
            raise ValueError(f"invalid_xosc: duplicate initial position for {entity!r}")
        initial_positions[entity] = tuple(
            float(position.get(name, "0")) for name in ("x", "y", "z", "h")
        )
    _validate_speed_actions(root)
    _validate_parameter_declarations(root)
    _validate_following_modes(root)

    story = root.find("./Storyboard/Story")
    acts = () if story is None else tuple(story.findall("Act"))
    if not acts:
        raise ValueError("invalid_xosc: storyboard declares no Act")
    if len(acts) > 1:
        raise ValueError("unsupported_xosc_feature: multiple Acts")
    act = acts[0]
    story_name = story.attrib.get("name", "") if story is not None else ""
    story_stop_conditions = _conditions(story.find("./StopTrigger") if story is not None else None, "story")
    if not story_stop_conditions:
        raise ValueError("invalid_xosc: story has no StopTrigger condition")
    if not _conditions(act.find("StartTrigger"), "act"):
        raise ValueError("invalid_xosc: act has no StartTrigger condition")

    act_start_conditions = _conditions(act.find("StartTrigger"), "act")
    entities = tuple(
        _interpret_group(group, initial_positions, act_start_conditions)
        for group in act.findall("ManeuverGroup")
    )
    if not entities:
        raise ValueError("invalid_xosc: act declares no ManeuverGroup")
    names = [entity.name for entity in entities]
    if len(names) != len(set(names)):
        raise ValueError("invalid_xosc: duplicate ManeuverGroup for one scenario object")
    declared = tuple(item.get("name", "") for item in root.findall("./Entities/ScenarioObject"))
    if set(names) != set(declared):
        raise ValueError("invalid_xosc: scenario objects and maneuver groups must match")
    return XoscInterpretation(
        source_path=path.as_posix(),
        map_reference=map_reference,
        act_name=act.attrib.get("name", ""),
        entities=entities,
        identity=build_execution_identity(path, xodr_path),
        story_name=story_name,
        story_stop_conditions=story_stop_conditions,
    )


def _validate_speed_actions(root: ET.Element) -> None:
    for action in root.findall(".//LongitudinalAction/SpeedAction"):
        dynamics = action.find("SpeedActionDynamics")
        if dynamics is None or dynamics.attrib.get("dynamicsShape") != "step":
            raise ValueError("unsupported_xosc_feature: only step speed dynamics are supported")
        if dynamics.attrib.get("dynamicsDimension") != "time":
            raise ValueError("unsupported_xosc_feature: only time-based speed dynamics are supported")


def _validate_parameter_declarations(root: ET.Element) -> None:
    """Only the exporter's own double scalar declarations are inside the subset."""
    for declaration in root.iter("ParameterDeclaration"):
        name = declaration.attrib.get("name", "")
        if name not in {"$ScenarioDuration", "speed"}:
            raise ValueError(f"unsupported_xosc_feature: ParameterDeclaration {name!r}")
        if declaration.attrib.get("parameterType") != "double":
            raise ValueError(f"invalid_xosc: ParameterDeclaration {name!r} must be a double")


def _validate_following_modes(root: ET.Element) -> None:
    for mode in root.iter("TrajectoryFollowingMode"):
        if mode.attrib.get("followingMode") not in {"position", "timing"}:
            raise ValueError("unsupported_xosc_feature: only position trajectory following is supported")


def _interpret_group(
    group: ET.Element,
    initial_positions: dict[str, tuple[float, float, float, float]],
    act_start_conditions: tuple[XoscConditionInterpretation, ...] = (),
) -> XoscEntityInterpretation:
    entity_ref = group.find("./Actors/EntityRef")
    name = "" if entity_ref is None else entity_ref.attrib.get("entityRef", "")
    if not name:
        raise ValueError("invalid_xosc: maneuver group has no EntityRef")
    if name not in initial_positions:
        raise ValueError(f"invalid_xosc: {name!r} has no Init teleport position")
    events = group.findall("./Maneuver/Event")
    if len(events) != 1:
        raise ValueError("unsupported_xosc_feature: exactly one Event per Maneuver is supported")
    event = events[0]
    shape = event.find("./Action/PrivateAction/RoutingAction/FollowTrajectoryAction/Trajectory/Shape")
    if shape is None or shape.find("Polyline") is None:
        raise ValueError("unsupported_xosc_feature: only Polyline trajectories are supported")
    vertices = shape.findall("./Polyline/Vertex")
    if not vertices:
        raise ValueError("invalid_xosc: trajectory has no vertices")
    trajectory = tuple(_vertex_to_tuple(vertex) for vertex in vertices)
    times = [vertex[0] for vertex in trajectory]
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError("invalid_xosc: trajectory vertex times must strictly increase")
    if times[0] < -1e-9:
        raise ValueError("invalid_xosc: trajectory must not start before time zero")
    reference = event.find("./Action/PrivateAction/RoutingAction/FollowTrajectoryAction/TimeReference/Timing")
    if reference is None:
        raise ValueError("invalid_xosc: FollowTrajectoryAction requires a TimeReference")
    if reference.attrib.get("domainAbsoluteRelative") not in {"absolute", "relative"}:
        raise ValueError("invalid_xosc: unsupported TimeReference domain")
    return XoscEntityInterpretation(
        name=name,
        initial_position=initial_positions[name],
        trajectory=trajectory,
        maneuver_group_name=group.attrib.get("name", ""),
        event_name=event.attrib.get("name", ""),
        time_reference_domain=reference.attrib["domainAbsoluteRelative"],
        time_reference_scale=float(reference.attrib.get("scale", "1")),
        time_reference_offset_s=float(reference.attrib.get("offset", "0")),
        start_conditions=_conditions(event.find("StartTrigger"), f"event {event.attrib.get('name', '')}")
        or act_start_conditions,
        stop_conditions=_conditions(event.find("StopTrigger"), f"event {event.attrib.get('name', '')}"),
    )


def _conditions(trigger: ET.Element | None, label: str) -> tuple[XoscConditionInterpretation, ...]:
    if trigger is None:
        return ()
    conditions = []
    for condition in trigger.findall("./ConditionGroup/Condition"):
        by_value = condition.find("ByValueCondition/SimulationTimeCondition")
        if by_value is None:
            raise ValueError(
                f"unsupported_xosc_feature: only SimulationTimeCondition triggers are supported ({label})"
            )
        conditions.append(
            XoscConditionInterpretation(
                name=condition.attrib.get("name", ""),
                delay_s=float(condition.attrib.get("delay", "0")),
                condition_edge=condition.attrib.get("conditionEdge", "none"),
                rule=by_value.attrib.get("rule", ""),
                value=float(by_value.attrib.get("value", "0")),
            )
        )
    return tuple(conditions)
