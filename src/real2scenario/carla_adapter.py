"""Map canonical road-aligned scenarios into a CARLA world frame.

The adapter deliberately keeps the canonical scenario untouched.  CARLA is a
declared execution target, so the world transform and waypoint validation are
stored alongside the mapped execution scenario rather than replacing source
coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, pi, sin
from typing import Any, Iterable

from .models import Actor, Scenario, State


CARLA_FRAME = "carla_world"
CARLA_MAPPING_VERSION = "carla-world-anchor-v1"


@dataclass(frozen=True, slots=True)
class CarlaAnchor:
    """World pose used as the origin of a local road-aligned scenario."""

    x_m: float
    y_m: float
    z_m: float
    yaw_rad: float
    spawn_index: int

    def __post_init__(self) -> None:
        values = (self.x_m, self.y_m, self.z_m, self.yaw_rad)
        if not all(isfinite(value) for value in values):
            raise ValueError("CarlaAnchor values must be finite.")
        if self.spawn_index < 0:
            raise ValueError("CarlaAnchor spawn_index must be non-negative.")


@dataclass(frozen=True, slots=True)
class CarlaMappingConfig:
    """Versioned policy for source-to-CARLA mapping and waypoint checks."""

    max_waypoint_distance_m: float = 4.0
    max_heading_error_rad: float = pi / 2
    mapping_version: str = CARLA_MAPPING_VERSION

    def __post_init__(self) -> None:
        if not isfinite(self.max_waypoint_distance_m) or self.max_waypoint_distance_m < 0:
            raise ValueError("max_waypoint_distance_m must be finite and non-negative.")
        if not isfinite(self.max_heading_error_rad) or self.max_heading_error_rad < 0:
            raise ValueError("max_heading_error_rad must be finite and non-negative.")
        if not self.mapping_version:
            raise ValueError("mapping_version must not be empty.")


@dataclass(frozen=True, slots=True)
class CarlaWaypointMatch:
    """Waypoint validation result for one mapped state."""

    actor_id: str
    state_index: int
    distance_m: float | None
    heading_error_rad: float | None
    matched: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CarlaMappingResult:
    """Mapped execution scenario and auditable waypoint validation."""

    scenario: Scenario
    anchor: CarlaAnchor
    world_name: str
    config: CarlaMappingConfig
    matches: tuple[CarlaWaypointMatch, ...]

    @property
    def valid(self) -> bool:
        return bool(self.matches) and all(match.matched for match in self.matches)

    @property
    def max_waypoint_distance_m(self) -> float | None:
        distances = [match.distance_m for match in self.matches if match.distance_m is not None]
        return max(distances) if distances else None

    @property
    def mean_waypoint_distance_m(self) -> float | None:
        distances = [match.distance_m for match in self.matches if match.distance_m is not None]
        return sum(distances) / len(distances) if distances else None

    def provenance(self) -> dict[str, str]:
        """Return metadata required to reproduce this execution mapping."""
        return {
            **self.scenario.provenance,
            "simulator": "CARLA",
            "carla_world": self.world_name,
            "carla_mapping_version": self.config.mapping_version,
            "carla_anchor_spawn_index": str(self.anchor.spawn_index),
            "carla_anchor_x_m": _number(self.anchor.x_m),
            "carla_anchor_y_m": _number(self.anchor.y_m),
            "carla_anchor_z_m": _number(self.anchor.z_m),
            "carla_anchor_yaw_rad": _number(self.anchor.yaw_rad),
            "carla_waypoint_max_distance_m": _optional_number(self.max_waypoint_distance_m),
            "carla_waypoint_mean_distance_m": _optional_number(self.mean_waypoint_distance_m),
            "carla_waypoint_validation": "pass" if self.valid else "fail",
        }


def transform_state_to_carla(state: State, anchor: CarlaAnchor) -> State:
    """Apply a local road-aligned SE(2) transform to a CARLA world state."""
    heading_cos = cos(anchor.yaw_rad)
    heading_sin = sin(anchor.yaw_rad)
    return State(
        time_s=state.time_s,
        x_m=anchor.x_m + heading_cos * state.x_m - heading_sin * state.y_m,
        y_m=anchor.y_m + heading_sin * state.x_m + heading_cos * state.y_m,
        yaw_rad=_wrap_angle(state.yaw_rad + anchor.yaw_rad),
        speed_mps=state.speed_mps,
    )


def map_scenario_to_carla(
    scenario: Scenario,
    *,
    anchor: CarlaAnchor,
    world_name: str,
    waypoint_map: Any | None = None,
    config: CarlaMappingConfig = CarlaMappingConfig(),
) -> CarlaMappingResult:
    """Create a CARLA-world execution scenario without mutating ``scenario``.

    ``waypoint_map`` is optional so the geometric mapping remains unit-testable
    without importing CARLA.  When supplied, it must provide
    ``get_waypoint(location, project_to_road=True, lane_type=...)``.
    """
    if scenario.coordinate_frame != "local_road_aligned":
        raise ValueError(
            "CARLA mapping requires a local_road_aligned source scenario; "
            "map global nuScenes coordinates to that frame first."
        )
    if not world_name:
        raise ValueError("world_name must not be empty.")

    actors = tuple(
        Actor(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            trajectory=tuple(transform_state_to_carla(state, anchor) for state in actor.trajectory),
            length_m=actor.length_m,
            width_m=actor.width_m,
            height_m=actor.height_m,
        )
        for actor in scenario.actors
    )
    mapped = Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=scenario.ego_actor_id,
        actors=actors,
        coordinate_frame=CARLA_FRAME,
        provenance={**scenario.provenance, **_base_provenance(world_name, anchor, config)},
    )
    matches = _validate_waypoints(mapped, waypoint_map, config)
    return CarlaMappingResult(mapped, anchor, world_name, config, matches)


def choose_best_anchor(
    scenario: Scenario,
    world: Any,
    *,
    world_name: str,
    config: CarlaMappingConfig = CarlaMappingConfig(),
) -> CarlaMappingResult:
    """Choose the spawn-point anchor with the best ego waypoint fit."""
    if scenario.coordinate_frame != "local_road_aligned":
        raise ValueError("CARLA anchor search requires a local_road_aligned scenario.")
    spawn_points = tuple(world.get_map().get_spawn_points())
    if not spawn_points:
        raise ValueError(f"CARLA world {world_name!r} has no spawn points.")

    candidates = (
        map_scenario_to_carla(
            scenario,
            anchor=CarlaAnchor(
                x_m=float(point.location.x),
                y_m=float(point.location.y),
                z_m=float(point.location.z),
                yaw_rad=point.rotation.yaw * pi / 180.0,
                spawn_index=index,
            ),
            world_name=world_name,
            waypoint_map=world.get_map(),
            config=config,
        )
        for index, point in enumerate(spawn_points)
    )
    ego_id = scenario.ego_actor_id
    return min(candidates, key=lambda result: _anchor_score(result, ego_id))


def _validate_waypoints(
    scenario: Scenario, waypoint_map: Any | None, config: CarlaMappingConfig
) -> tuple[CarlaWaypointMatch, ...]:
    if waypoint_map is None:
        return ()
    try:
        import carla
    except ImportError as error:
        raise RuntimeError("CARLA Python client is required for waypoint validation.") from error

    matches: list[CarlaWaypointMatch] = []
    for actor in scenario.actors:
        for state_index, state in enumerate(actor.trajectory):
            location = carla.Location(x=state.x_m, y=state.y_m, z=0.0)
            waypoint = waypoint_map.get_waypoint(
                location,
                project_to_road=True,
                lane_type=carla.LaneType.Driving,
            )
            if waypoint is None:
                matches.append(
                    CarlaWaypointMatch(actor.actor_id, state_index, None, None, False, "no_waypoint")
                )
                continue
            distance_m = hypot(
                state.x_m - waypoint.transform.location.x,
                state.y_m - waypoint.transform.location.y,
            )
            waypoint_yaw = waypoint.transform.rotation.yaw * pi / 180.0
            heading_error = abs(_wrap_angle(state.yaw_rad - waypoint_yaw))
            matched = (
                distance_m <= config.max_waypoint_distance_m
                and heading_error <= config.max_heading_error_rad
            )
            reason = None if matched else "waypoint_distance_or_heading"
            matches.append(
                CarlaWaypointMatch(
                    actor.actor_id,
                    state_index,
                    distance_m,
                    heading_error,
                    matched,
                    reason,
                )
            )
    return tuple(matches)


def _anchor_score(result: CarlaMappingResult, ego_id: str) -> tuple[float, float, int]:
    ego_matches = [match for match in result.matches if match.actor_id == ego_id]
    distances = [match.distance_m for match in ego_matches if match.distance_m is not None]
    failures = sum(not match.matched for match in ego_matches)
    mean_distance = sum(distances) / len(distances) if distances else float("inf")
    return failures, mean_distance, result.anchor.spawn_index


def _base_provenance(
    world_name: str, anchor: CarlaAnchor, config: CarlaMappingConfig
) -> dict[str, str]:
    return {
        "simulator": "CARLA",
        "carla_world": world_name,
        "carla_mapping_version": config.mapping_version,
        "carla_anchor_spawn_index": str(anchor.spawn_index),
        "carla_anchor_x_m": _number(anchor.x_m),
        "carla_anchor_y_m": _number(anchor.y_m),
        "carla_anchor_z_m": _number(anchor.z_m),
        "carla_anchor_yaw_rad": _number(anchor.yaw_rad),
    }


def _wrap_angle(angle_rad: float) -> float:
    return (angle_rad + pi) % (2 * pi) - pi


def _number(value: float) -> str:
    return format(value, ".17g")


def _optional_number(value: float | None) -> str:
    return "unknown" if value is None else _number(value)
