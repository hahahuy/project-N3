"""User-authored trajectory branches for the workspace motion editor."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite, pi
from typing import Sequence

from .models import Actor, Scenario, State


CANVAS_KEYFRAME_VERSION = "canvas-keyframes-v1"
MIN_KEYFRAME_INTERVAL_S = 0.25
MAX_KEYFRAME_SPEED_MPS = 20.0
MAX_KEYFRAME_YAW_RATE_RPS = 2.5
MAX_KEYFRAME_TURN_ANGLE_RAD = 2.0


@dataclass(frozen=True, slots=True)
class CanvasKeyframe:
    """One required-velocity point authored in the local scenario frame."""

    keyframe_id: str
    time_s: float
    x_m: float
    y_m: float
    yaw_rad: float
    speed_mps: float

    def __post_init__(self) -> None:
        if not self.keyframe_id:
            raise ValueError("Canvas keyframe ID must not be empty.")
        values = (self.time_s, self.x_m, self.y_m, self.yaw_rad, self.speed_mps)
        if not all(isfinite(value) for value in values):
            raise ValueError("Canvas keyframe values must be finite.")
        if self.time_s < 0:
            raise ValueError("Canvas keyframe time_s must be non-negative.")
        if self.speed_mps < 0:
            raise ValueError("Canvas keyframe speed_mps must be non-negative.")


@dataclass(frozen=True, slots=True)
class CanvasBranch:
    scenario: Scenario
    keyframe_hash: str
    authored_actor_id: str


def build_canvas_keyframe_branch(
    parent: Scenario,
    actor_id: str,
    keyframes: Sequence[CanvasKeyframe],
    *,
    branch_name: str | None = None,
    seed: int = 0,
    include_origin_reference: bool = False,
) -> CanvasBranch:
    """Create an immutable one-actor child from free, non-snapped keyframes."""
    if parent.coordinate_frame != "local_road_aligned":
        raise ValueError("Canvas authoring requires the local_road_aligned frame.")
    if len(keyframes) < 2:
        raise ValueError("At least two canvas keyframes are required.")
    if len({item.keyframe_id for item in keyframes}) != len(keyframes):
        raise ValueError("Canvas keyframe IDs must be unique.")
    if any(later.time_s <= earlier.time_s for earlier, later in zip(keyframes, keyframes[1:])):
        raise ValueError("Canvas keyframe times must strictly increase.")
    if any(
        later.time_s - earlier.time_s < MIN_KEYFRAME_INTERVAL_S
        for earlier, later in zip(keyframes, keyframes[1:])
    ):
        raise ValueError(f"Canvas keyframe intervals must be at least {MIN_KEYFRAME_INTERVAL_S:.2f}s.")
    if any(item.speed_mps > MAX_KEYFRAME_SPEED_MPS for item in keyframes):
        raise ValueError(f"Canvas keyframe speed must not exceed {MAX_KEYFRAME_SPEED_MPS:.1f} m/s.")
    actor = next((item for item in parent.actors if item.actor_id == actor_id), None)
    if actor is None:
        raise ValueError(f"Unknown actor ID: {actor_id!r}.")
    origin = actor.trajectory[0]
    first = keyframes[0]
    if abs(first.x_m - origin.x_m) > 1e-6 or abs(first.y_m - origin.y_m) > 1e-6:
        raise ValueError("The first canvas keyframe must remain at the actor origin position.")
    if keyframes[-1].time_s > parent.duration_s:
        raise ValueError("Canvas keyframe time must not exceed the origin scenario duration.")
    for previous, current in zip(keyframes, keyframes[1:]):
        if abs(_physical_yaw_delta(current.yaw_rad, previous.yaw_rad)) / (current.time_s - previous.time_s) > MAX_KEYFRAME_YAW_RATE_RPS:
            raise ValueError(f"Canvas keyframe yaw rate must not exceed {MAX_KEYFRAME_YAW_RATE_RPS:.1f} rad/s.")
    for previous, current, following in zip(keyframes, keyframes[1:], keyframes[2:]):
        turn = abs(_physical_yaw_delta(following.yaw_rad, previous.yaw_rad))
        if turn > MAX_KEYFRAME_TURN_ANGLE_RAD:
            raise ValueError(f"Canvas keyframe turn angle must not exceed {MAX_KEYFRAME_TURN_ANGLE_RAD:.2f} rad.")

    normalized = _normalize_keyframes(keyframes)
    payload = {
        "authoring_version": CANVAS_KEYFRAME_VERSION,
        "parent_scenario_id": parent.scenario_id,
        "actor_id": actor_id,
        "seed": seed,
        "keyframes": [
            {
                "keyframe_id": item.keyframe_id,
                "time_s": item.time_s,
                "x_m": item.x_m,
                "y_m": item.y_m,
                "yaw_rad": item.yaw_rad,
                "speed_mps": item.speed_mps,
            }
            for item in normalized
        ],
    }
    keyframe_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    scenario_id = f"{parent.scenario_id}--canvas-{keyframe_hash[:16]}"
    replacement = Actor(
        actor.actor_id,
        actor.actor_type,
        tuple(State(item.time_s, item.x_m, item.y_m, item.yaw_rad, item.speed_mps) for item in normalized),
        actor.length_m,
        actor.width_m,
        actor.height_m,
    )
    actors_list = [replacement if item.actor_id == actor_id else item for item in parent.actors]
    if include_origin_reference:
        reference_id = f"{actor_id}-origin-reference"
        if any(item.actor_id == reference_id for item in actors_list):
            raise ValueError(f"Origin reference actor ID already exists: {reference_id!r}.")
        actors_list.append(Actor(reference_id, actor.actor_type, actor.trajectory, actor.length_m, actor.width_m, actor.height_m))
    actors = tuple(actors_list)
    provenance = dict(parent.provenance)
    provenance.update(
        {
            "parent_scenario_id": parent.scenario_id,
            "authoring_mode": "canvas_keyframes",
            "authoring_version": CANVAS_KEYFRAME_VERSION,
            "keyframe_hash": keyframe_hash,
            "authored_actor_id": actor_id,
            "authored_speed_policy": "required_explicit_velocity",
            "snap_to_lane": "disabled_free_motion",
        }
    )
    if include_origin_reference:
        provenance["origin_reference_actor_id"] = f"{actor_id}-origin-reference"
    if branch_name:
        provenance["branch_name"] = branch_name
    scenario = Scenario(
        scenario_id,
        parent.duration_s,
        parent.ego_actor_id,
        actors,
        parent.coordinate_frame,
        provenance,
        parent.replay_mode,
        parent.interaction_events,
    )
    return CanvasBranch(scenario, keyframe_hash, actor_id)


def _normalize_keyframes(keyframes: Sequence[CanvasKeyframe]) -> tuple[CanvasKeyframe, ...]:
    """Unwrap yaw so a linear path never interpolates through a full turn."""
    result: list[CanvasKeyframe] = [keyframes[0]]
    previous = keyframes[0].yaw_rad
    for item in keyframes[1:]:
        yaw = item.yaw_rad
        while yaw - previous > pi:
            yaw -= 2 * pi
        while yaw - previous < -pi:
            yaw += 2 * pi
        result.append(CanvasKeyframe(item.keyframe_id, item.time_s, item.x_m, item.y_m, yaw, item.speed_mps))
        previous = yaw
    return tuple(result)


def _wrapped_angle_delta(current: float, previous: float) -> float:
    delta = current - previous
    while delta > pi:
        delta -= 2 * pi
    while delta < -pi:
        delta += 2 * pi
    return delta


def _physical_yaw_delta(current: float, previous: float) -> float:
    raw = current - previous
    if abs(abs(raw) - 2 * pi) < 1e-6:
        return raw
    return _wrapped_angle_delta(current, previous)
