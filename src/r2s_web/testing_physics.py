"""Deterministic internal path physics for the testing surface, no CARLA."""
from __future__ import annotations

import math
from typing import Sequence

from real2scenario import State, compare_trajectory


def recalculate_path(keyframes: Sequence[object], *, obstacles: Sequence[dict[str, float]] = (), timestep_s: float = 0.05) -> dict[str, object]:
    reference = tuple(State(item.time_s, item.x_m, item.y_m, item.yaw_rad, item.speed_mps) for item in keyframes)
    if len(reference) < 2:
        raise ValueError("path_recalculate_requires_two_keyframes")
    trace = _follow_path(reference, timestep_s)
    collisions = _detect_collisions(trace, obstacles)
    metric = compare_trajectory(reference, trace)
    metrics = metric.__dict__ if hasattr(metric, "__dict__") else {field: getattr(metric, field) for field in metric.__dataclass_fields__}
    return {"status": "completed", "mode": "testing-internal-single-track-v1", "world": "local_road_aligned", "server_version": "testing-internal-single-track-v1", "collision_count": len(collisions), "collisions": collisions, "metrics": metrics, "trace": [_state_dict(item) for item in trace], "physics_enabled": True, "same_xosc": False, "sensor_output": False}


# Yaw-rate ceiling for the internal follower, in rad/s. This is the constant
# that decides how fast the nose may swing from the old heading to the new one.
#
# It is deliberately a flat ceiling, not a vehicle model: the follower has no
# wheelbase and no mass, so every actor turns identically no matter how big it
# is. A size-aware limit would be min(steering-limited, grip-limited):
#   steering-limited  yaw_rate = v * tan(max_steering_rad) / (front_axle + rear_axle)
#   grip-limited      yaw_rate = max_lateral_acceleration_mps2 / v
# using DynamicSingleTrackParameters in real2scenario.dynamic_single_track.
# The same gap exists downstream: real2scenario.exporter writes a hardcoded
# maxSteering=0.5 / wheelDiameter=0.7 / trackWidth=1.5 / positionX=2.8 axle block
# for every actor, even though width/length/height do come from the actor, so an
# exported truck and an exported car are steered by identical geometry.
MAX_YAW_RATE_RADPS = 2.5


def _follow_path(reference: Sequence[State], timestep_s: float) -> tuple[State, ...]:
    position = reference[0]
    result: list[State] = []
    for index in range(max(1, int(math.ceil(reference[-1].time_s / timestep_s))) + 1):
        time_s = min(reference[-1].time_s, index * timestep_s)
        target = _interpolate(reference, time_s)
        # The aim point is the interpolated target at the current time, i.e. one
        # solver step ahead. A longer lookahead was measured and rejected: on a
        # constant-radius arc the heading then settles on the chord to the distant
        # point, which is offset from the tangent by half the spanned arc angle
        # (7.6 deg for a 4 m lookahead on a 15 m radius), so the nose oversteers
        # the curve instead of following it.
        dx = target.x_m - position.x_m
        dy = target.y_m - position.y_m
        distance = math.hypot(dx, dy)
        desired_heading = math.atan2(dy, dx) if distance > 1e-6 else position.yaw_rad
        heading_error = _wrap(desired_heading - position.yaw_rad)
        max_heading_step = MAX_YAW_RATE_RADPS * timestep_s
        if abs(heading_error) > math.pi / 2:
            speed = 0.0
            yaw = position.yaw_rad
        else:
            yaw = position.yaw_rad + max(-max_heading_step, min(max_heading_step, heading_error))
            speed = min(target.speed_mps, distance / max(timestep_s, 1e-6))
        x = position.x_m + math.cos(yaw) * speed * timestep_s
        y = position.y_m + math.sin(yaw) * speed * timestep_s
        position = State(time_s, x, y, yaw, speed)
        result.append(position)
    return tuple(result)


def _detect_collisions(trace: Sequence[State], obstacles: Sequence[dict[str, float]]) -> list[dict[str, object]]:
    collisions: list[dict[str, object]] = []
    for obstacle_index, obstacle in enumerate(obstacles):
        ox, oy = float(obstacle.get("x_m", 0)), float(obstacle.get("y_m", 0))
        radius = max(0.5, float(obstacle.get("length_m", 2)) / 2, float(obstacle.get("width_m", 2)) / 2)
        for state in trace:
            distance = math.hypot(state.x_m - ox, state.y_m - oy)
            if distance <= radius + 2.25:
                collisions.append({"time_s": state.time_s, "obstacle_index": obstacle_index, "distance_m": distance})
    return collisions


def _interpolate(reference: Sequence[State], time_s: float) -> State:
    if time_s <= reference[0].time_s:
        return reference[0]
    for left, right in zip(reference, reference[1:]):
        if time_s <= right.time_s:
            fraction = (time_s - left.time_s) / max(1e-6, right.time_s - left.time_s)
            return State(time_s, left.x_m + (right.x_m - left.x_m) * fraction, left.y_m + (right.y_m - left.y_m) * fraction, left.yaw_rad + (right.yaw_rad - left.yaw_rad) * fraction, left.speed_mps + (right.speed_mps - left.speed_mps) * fraction)
    return reference[-1]


def _state_dict(state: State) -> dict[str, float]:
    return {"time_s": state.time_s, "x_m": state.x_m, "y_m": state.y_m, "yaw_rad": state.yaw_rad, "speed_mps": state.speed_mps}


def _wrap(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle
