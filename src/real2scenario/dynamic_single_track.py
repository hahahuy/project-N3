"""Diagnostic Tier 2 dynamic single-track prototype.

This module is deliberately separate from the Tier 1 kinematic preview and the
Tier 0 replay path. It is a small, deterministic dynamic bicycle model for
vehicle-only experiments; its output is never a fidelity or sensor claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, sin
from typing import Sequence

from .models import State
from .simulation import ReplayState, ReplayTrace


DYNAMIC_SINGLE_TRACK_VERSION = "dynamic-single-track-v1"
DYNAMIC_SINGLE_TRACK_PARAMETERS_VERSION = "dynamic-single-track-parameters-v1"


@dataclass(frozen=True, slots=True)
class DynamicSingleTrackParameters:
    mass_kg: float = 1500.0
    yaw_inertia_kgm2: float = 2500.0
    front_axle_m: float = 1.2
    rear_axle_m: float = 1.6
    cornering_stiffness_front_Nprad: float = 80_000.0
    cornering_stiffness_rear_Nprad: float = 80_000.0
    max_steering_rad: float = 0.6
    max_acceleration_mps2: float = 5.0
    max_deceleration_mps2: float = 8.0
    max_lateral_acceleration_mps2: float = 12.0
    low_speed_guard_mps: float = 1.0
    timestep_s: float = 0.01
    version: str = DYNAMIC_SINGLE_TRACK_PARAMETERS_VERSION

    def __post_init__(self) -> None:
        values = (
            self.mass_kg, self.yaw_inertia_kgm2, self.front_axle_m,
            self.rear_axle_m, self.cornering_stiffness_front_Nprad,
            self.cornering_stiffness_rear_Nprad, self.max_steering_rad,
            self.max_acceleration_mps2, self.max_deceleration_mps2,
            self.max_lateral_acceleration_mps2, self.low_speed_guard_mps,
            self.timestep_s,
        )
        if not self.version or not all(isfinite(value) and value > 0 for value in values):
            raise ValueError("Dynamic single-track parameters must be finite and positive.")


@dataclass(frozen=True, slots=True)
class DynamicSingleTrackState:
    time_s: float
    x_m: float
    y_m: float
    yaw_rad: float
    vx_mps: float
    vy_mps: float
    yaw_rate_radps: float
    steering_rad: float
    acceleration_mps2: float
    beta_rad: float


@dataclass(frozen=True, slots=True)
class DynamicViolation:
    code: str
    state_index: int
    actor_id: str
    observed: float | None
    limit: float | None
    message: str


@dataclass(frozen=True, slots=True)
class DynamicSingleTrackPreview:
    states: tuple[State, ...]
    internal_states: tuple[DynamicSingleTrackState, ...]
    trace: ReplayTrace
    violations: tuple[DynamicViolation, ...]
    provenance: dict[str, str]
    status: str


def integrate_dynamic_single_track(
    initial: State,
    *,
    actor_id: str,
    parameters: DynamicSingleTrackParameters = DynamicSingleTrackParameters(),
    steering_profile: Sequence[tuple[float, float]] = ((0.0, 0.0),),
    acceleration_profile: Sequence[tuple[float, float]] = ((0.0, 0.0),),
    duration_s: float,
) -> DynamicSingleTrackPreview:
    """Integrate one vehicle with midpoint RK2 and explicit diagnostics."""
    if not actor_id or not isfinite(duration_s) or duration_s <= 0:
        raise ValueError("Dynamic integration requires a non-empty actor and positive duration.")
    _validate_profile(steering_profile, "steering")
    _validate_profile(acceleration_profile, "acceleration")
    if initial.speed_mps < parameters.low_speed_guard_mps:
        return _unsupported(initial, actor_id, parameters, "dynamic_single_track_low_speed_model_guard")

    states: list[State] = []
    internal: list[DynamicSingleTrackState] = []
    violations: list[DynamicViolation] = []
    x, y, yaw = initial.x_m, initial.y_m, initial.yaw_rad
    vx, vy, yaw_rate = initial.speed_mps, 0.0, 0.0
    time_s = initial.time_s
    steps = int(round(duration_s / parameters.timestep_s))
    for index in range(steps + 1):
        steering = _profile_value(steering_profile, time_s)
        acceleration = _profile_value(acceleration_profile, time_s)
        beta = atan2(vy, vx)
        current = DynamicSingleTrackState(time_s, x, y, yaw, vx, vy, yaw_rate, steering, acceleration, beta)
        internal.append(current)
        speed = hypot(vx, vy)
        states.append(State(time_s, x, y, yaw, speed))
        if abs(steering) > parameters.max_steering_rad:
            violations.append(DynamicViolation("steering_exceeded", index, actor_id, abs(steering), parameters.max_steering_rad, "Steering exceeds the configured diagnostic limit."))
        if acceleration > parameters.max_acceleration_mps2:
            violations.append(DynamicViolation("acceleration_exceeded", index, actor_id, acceleration, parameters.max_acceleration_mps2, "Acceleration exceeds the configured diagnostic limit."))
        if -acceleration > parameters.max_deceleration_mps2:
            violations.append(DynamicViolation("deceleration_exceeded", index, actor_id, -acceleration, parameters.max_deceleration_mps2, "Deceleration exceeds the configured diagnostic limit."))
        if abs((vx * yaw_rate)) > parameters.max_lateral_acceleration_mps2:
            violations.append(DynamicViolation("lateral_acceleration_exceeded", index, actor_id, abs(vx * yaw_rate), parameters.max_lateral_acceleration_mps2, "Lateral acceleration exceeds the configured diagnostic limit."))
        if index == steps:
            break
        derivative = _derivative(vx, vy, yaw_rate, yaw, steering, acceleration, parameters)
        midpoint = tuple(value + 0.5 * parameters.timestep_s * delta for value, delta in zip((x, y, yaw, vx, vy, yaw_rate), derivative))
        mid_derivative = _derivative(midpoint[3], midpoint[4], midpoint[5], midpoint[2], steering, acceleration, parameters)
        x += parameters.timestep_s * mid_derivative[0]
        y += parameters.timestep_s * mid_derivative[1]
        yaw += parameters.timestep_s * mid_derivative[2]
        vx += parameters.timestep_s * mid_derivative[3]
        vy += parameters.timestep_s * mid_derivative[4]
        yaw_rate += parameters.timestep_s * mid_derivative[5]
        time_s = initial.time_s + (index + 1) * parameters.timestep_s
        if not all(isfinite(value) for value in (x, y, yaw, vx, vy, yaw_rate)):
            violations.append(DynamicViolation("integration_nonfinite", index + 1, actor_id, None, None, "Integration produced a non-finite state."))
            break
    trace = ReplayTrace(tuple(ReplayState(actor_id, state) for state in states))
    provenance = {
        "simulator_version": DYNAMIC_SINGLE_TRACK_VERSION,
        "parameter_version": parameters.version,
        "integration_method": "rk2-midpoint",
        "fixed_timestep_s": format(parameters.timestep_s, ".12g"),
        "tier": "tier2-diagnostic",
        "not_fidelity_or_sensor_evidence": "true",
        "silent_clamps": "forbidden",
    }
    return DynamicSingleTrackPreview(tuple(states), tuple(internal), trace, tuple(violations), provenance, "invalid" if violations else "valid")


def _derivative(vx: float, vy: float, yaw_rate: float, yaw: float, steering: float, acceleration: float, p: DynamicSingleTrackParameters) -> tuple[float, ...]:
    alpha_f = steering - atan2(vy + p.front_axle_m * yaw_rate, max(vx, p.low_speed_guard_mps))
    alpha_r = -atan2(vy - p.rear_axle_m * yaw_rate, max(vx, p.low_speed_guard_mps))
    front_force = p.cornering_stiffness_front_Nprad * alpha_f
    rear_force = p.cornering_stiffness_rear_Nprad * alpha_r
    return (
        vx * cos(yaw) - vy * sin(yaw),
        vx * sin(yaw) + vy * cos(yaw),
        yaw_rate,
        acceleration + yaw_rate * vy,
        (front_force + rear_force) / p.mass_kg - yaw_rate * vx,
        (p.front_axle_m * front_force - p.rear_axle_m * rear_force) / p.yaw_inertia_kgm2,
    )


def _profile_value(profile: Sequence[tuple[float, float]], time_s: float) -> float:
    for left, right in zip(profile, profile[1:]):
        if time_s <= right[0]:
            if right[0] == left[0]:
                return right[1]
            fraction = (time_s - left[0]) / (right[0] - left[0])
            return left[1] + fraction * (right[1] - left[1])
    return profile[-1][1]


def _validate_profile(profile: Sequence[tuple[float, float]], name: str) -> None:
    if not profile or any(not isfinite(t) or not isfinite(value) for t, value in profile):
        raise ValueError(f"{name} profile must contain finite values.")
    if profile[0][0] < 0 or any(right[0] <= left[0] for left, right in zip(profile, profile[1:])):
        raise ValueError(f"{name} profile times must strictly increase from zero.")


def _unsupported(initial: State, actor_id: str, parameters: DynamicSingleTrackParameters, reason: str) -> DynamicSingleTrackPreview:
    violation = DynamicViolation(reason, 0, actor_id, initial.speed_mps, parameters.low_speed_guard_mps, "The dynamic single-track model is guarded below its configured low-speed threshold.")
    trace = ReplayTrace((ReplayState(actor_id, initial),))
    return DynamicSingleTrackPreview((initial,), (), trace, (violation,), {"simulator_version": DYNAMIC_SINGLE_TRACK_VERSION, "tier": "tier2-diagnostic"}, "unsupported")
