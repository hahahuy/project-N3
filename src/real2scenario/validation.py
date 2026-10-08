"""Configurable feasibility validation for generated scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi

from .models import Actor, Scenario


VALIDATION_VERSION = "feasibility-v1"


@dataclass(frozen=True, slots=True)
class RoadBoundary:
    """Optional axis-aligned drivable rectangle in the scenario frame."""

    min_x_m: float
    max_x_m: float
    min_y_m: float
    max_y_m: float

    def __post_init__(self) -> None:
        values = (self.min_x_m, self.max_x_m, self.min_y_m, self.max_y_m)
        if not all(isfinite(value) for value in values):
            raise ValueError("Road boundary values must be finite.")
        if self.min_x_m > self.max_x_m or self.min_y_m > self.max_y_m:
            raise ValueError("Road boundary minimums must not exceed maximums.")


@dataclass(frozen=True, slots=True)
class FeasibilityLimits:
    """Versioned thresholds for kinematic and optional road checks."""

    max_acceleration_mps2: float = 5.0
    max_deceleration_mps2: float = 8.0
    max_jerk_mps3: float = 20.0
    max_yaw_rate_rps: float = 1.5
    road_boundary: RoadBoundary | None = None
    version: str = VALIDATION_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("max_acceleration_mps2", self.max_acceleration_mps2),
            ("max_deceleration_mps2", self.max_deceleration_mps2),
            ("max_jerk_mps3", self.max_jerk_mps3),
            ("max_yaw_rate_rps", self.max_yaw_rate_rps),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative.")
        if not self.version:
            raise ValueError("FeasibilityLimits version must not be empty.")


@dataclass(frozen=True, slots=True)
class RejectionReason:
    """One reviewable reason a scenario failed feasibility validation."""

    code: str
    category: str
    actor_id: str | None
    state_index: int | None
    observed: float | None
    limit: float | None
    message: str


@dataclass(frozen=True, slots=True)
class FeasibilityReport:
    """Complete validation result, including every rejection reason."""

    scenario_id: str
    validation_version: str
    valid: bool
    reasons: tuple[RejectionReason, ...]


def validate_feasibility(
    scenario: Scenario,
    limits: FeasibilityLimits = FeasibilityLimits(),
) -> FeasibilityReport:
    """Validate all actors without clamping or stopping at the first failure."""
    reasons: list[RejectionReason] = []
    for actor in scenario.actors:
        reasons.extend(_validate_actor(actor, limits))
    if limits.road_boundary is not None:
        reasons.extend(_validate_boundary(scenario, limits.road_boundary))
    return FeasibilityReport(
        scenario_id=scenario.scenario_id,
        validation_version=limits.version,
        valid=not reasons,
        reasons=tuple(reasons),
    )


def _validate_actor(actor: Actor, limits: FeasibilityLimits) -> list[RejectionReason]:
    reasons: list[RejectionReason] = []
    accelerations: list[float] = []
    yaw_rates: list[float] = []
    for index, (previous, current) in enumerate(zip(actor.trajectory, actor.trajectory[1:]), 1):
        delta_t = current.time_s - previous.time_s
        acceleration = (current.speed_mps - previous.speed_mps) / delta_t
        yaw_rate = _wrapped_angle_delta(current.yaw_rad, previous.yaw_rad) / delta_t
        accelerations.append(acceleration)
        yaw_rates.append(yaw_rate)
        if acceleration > limits.max_acceleration_mps2:
            reasons.append(
                _reason(
                    "acceleration_exceeded",
                    "kinematic",
                    actor,
                    index,
                    acceleration,
                    limits.max_acceleration_mps2,
                    "Acceleration exceeds configured maximum.",
                )
            )
        if -acceleration > limits.max_deceleration_mps2:
            reasons.append(
                _reason(
                    "deceleration_exceeded",
                    "kinematic",
                    actor,
                    index,
                    -acceleration,
                    limits.max_deceleration_mps2,
                    "Deceleration exceeds configured maximum.",
                )
            )
        if abs(yaw_rate) > limits.max_yaw_rate_rps:
            reasons.append(
                _reason(
                    "yaw_rate_exceeded",
                    "kinematic",
                    actor,
                    index,
                    abs(yaw_rate),
                    limits.max_yaw_rate_rps,
                    "Yaw rate exceeds configured maximum.",
                )
            )
    for index, (previous, current) in enumerate(zip(accelerations, accelerations[1:]), 2):
        delta_t = actor.trajectory[index].time_s - actor.trajectory[index - 1].time_s
        jerk = (current - previous) / delta_t
        if abs(jerk) > limits.max_jerk_mps3:
            reasons.append(
                _reason(
                    "jerk_exceeded",
                    "kinematic",
                    actor,
                    index,
                    abs(jerk),
                    limits.max_jerk_mps3,
                    "Jerk exceeds configured maximum.",
                )
            )
    return reasons


def _validate_boundary(scenario: Scenario, boundary: RoadBoundary) -> list[RejectionReason]:
    reasons: list[RejectionReason] = []
    for actor in scenario.actors:
        for index, state in enumerate(actor.trajectory):
            if state.x_m < boundary.min_x_m or state.x_m > boundary.max_x_m:
                reasons.append(
                    _reason(
                        "road_boundary_x",
                        "road",
                        actor,
                        index,
                        state.x_m,
                        boundary.min_x_m if state.x_m < boundary.min_x_m else boundary.max_x_m,
                        "State lies outside the configured road x boundary.",
                    )
                )
            if state.y_m < boundary.min_y_m or state.y_m > boundary.max_y_m:
                reasons.append(
                    _reason(
                        "road_boundary_y",
                        "road",
                        actor,
                        index,
                        state.y_m,
                        boundary.min_y_m if state.y_m < boundary.min_y_m else boundary.max_y_m,
                        "State lies outside the configured road y boundary.",
                    )
                )
    return reasons


def _reason(
    code: str,
    category: str,
    actor: Actor,
    state_index: int,
    observed: float,
    limit: float,
    message: str,
) -> RejectionReason:
    return RejectionReason(
        code=code,
        category=category,
        actor_id=actor.actor_id,
        state_index=state_index,
        observed=observed,
        limit=limit,
        message=message,
    )


def _wrapped_angle_delta(current: float, previous: float) -> float:
    return (current - previous + pi) % (2 * pi) - pi
