"""Versioned transforms between recorded and local road-aligned frames."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, pi, sin

from .models import Actor, Scenario, State


LOCAL_ROAD_ALIGNED_FRAME = "local_road_aligned"
COORDINATE_TRANSFORM_VERSION = "local-road-aligned-v1"


@dataclass(frozen=True, slots=True)
class RoadAlignedTransform:
    """A rigid 2D transform with local x forward and local y left in metres."""

    origin_x_m: float
    origin_y_m: float
    heading_rad: float
    source_frame: str = "nuscenes_global"
    version: str = COORDINATE_TRANSFORM_VERSION
    round_trip_tolerance_m: float = 1e-9

    def __post_init__(self) -> None:
        if not all(
            isfinite(value)
            for value in (
                self.origin_x_m,
                self.origin_y_m,
                self.heading_rad,
                self.round_trip_tolerance_m,
            )
        ):
            raise ValueError("RoadAlignedTransform values must be finite.")
        if self.round_trip_tolerance_m <= 0:
            raise ValueError("RoadAlignedTransform round_trip_tolerance_m must be positive.")
        if not self.source_frame:
            raise ValueError("RoadAlignedTransform source_frame must not be empty.")
        if not self.version:
            raise ValueError("RoadAlignedTransform version must not be empty.")

    def to_local_state(self, state: State) -> State:
        """Rotate and translate a source-frame state into the local frame."""
        delta_x_m = state.x_m - self.origin_x_m
        delta_y_m = state.y_m - self.origin_y_m
        heading_cos = cos(self.heading_rad)
        heading_sin = sin(self.heading_rad)
        return State(
            time_s=state.time_s,
            x_m=heading_cos * delta_x_m + heading_sin * delta_y_m,
            y_m=-heading_sin * delta_x_m + heading_cos * delta_y_m,
            yaw_rad=_wrap_angle(state.yaw_rad - self.heading_rad),
            speed_mps=state.speed_mps,
        )

    def to_source_state(self, state: State) -> State:
        """Invert ``to_local_state`` for a state in the local frame."""
        heading_cos = cos(self.heading_rad)
        heading_sin = sin(self.heading_rad)
        return State(
            time_s=state.time_s,
            x_m=self.origin_x_m + heading_cos * state.x_m - heading_sin * state.y_m,
            y_m=self.origin_y_m + heading_sin * state.x_m + heading_cos * state.y_m,
            yaw_rad=_wrap_angle(state.yaw_rad + self.heading_rad),
            speed_mps=state.speed_mps,
        )

    def provenance(self) -> dict[str, str]:
        """Return durable metadata describing this transform's frame contract."""
        return {
            "coordinate_transform_version": self.version,
            "coordinate_transform_source_frame": self.source_frame,
            "coordinate_transform_target_frame": LOCAL_ROAD_ALIGNED_FRAME,
            "coordinate_transform_origin_x_m": _format_number(self.origin_x_m),
            "coordinate_transform_origin_y_m": _format_number(self.origin_y_m),
            "coordinate_transform_heading_rad": _format_number(self.heading_rad),
            "coordinate_transform_axes": "x_forward_m,y_left_m,z_up_m",
            "coordinate_transform_round_trip_tolerance_m": _format_number(
                self.round_trip_tolerance_m
            ),
        }


def transform_to_local_road_aligned(
    scenario: Scenario, transform: RoadAlignedTransform
) -> Scenario:
    """Create a local-frame scenario without mutating the recorded input scenario."""
    if scenario.coordinate_frame != transform.source_frame:
        raise ValueError(
            "Scenario coordinate_frame must match RoadAlignedTransform source_frame; "
            f"got {scenario.coordinate_frame!r}, expected {transform.source_frame!r}."
        )

    actors = tuple(
        Actor(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            trajectory=tuple(transform.to_local_state(state) for state in actor.trajectory),
            length_m=actor.length_m,
            width_m=actor.width_m,
        )
        for actor in scenario.actors
    )
    provenance = {**scenario.provenance, **transform.provenance()}
    return Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=scenario.ego_actor_id,
        actors=actors,
        coordinate_frame=LOCAL_ROAD_ALIGNED_FRAME,
        provenance=provenance,
    )


def _wrap_angle(angle_rad: float) -> float:
    """Normalize an angle into the half-open interval [-pi, pi)."""
    return (angle_rad + pi) % (2 * pi) - pi


def _format_number(value: float) -> str:
    return format(value, ".17g")
