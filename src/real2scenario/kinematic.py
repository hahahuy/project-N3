"""Deterministic Tier 1 kinematic-open-loop preview."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, isfinite, sin
from typing import Sequence

from .models import Actor, State
from .simulation import ReplayState, ReplayTrace
from .source_state import SourceStateExtension


KINEMATIC_VERSION = "kinematic-open-loop-v1"
KINEMATIC_LIMITS_VERSION = "kinematic-limits-v1"


@dataclass(frozen=True, slots=True)
class KinematicLimits:
    """Diagnostic limits; none are used to clamp or correct propagation."""

    max_acceleration_mps2: float = 5.0
    max_deceleration_mps2: float = 8.0
    max_jerk_mps3: float = 20.0
    max_yaw_rate_radps: float = 1.5
    version: str = KINEMATIC_LIMITS_VERSION

    def __post_init__(self) -> None:
        if not self.version or any(
            not isfinite(value) or value < 0
            for value in (
                self.max_acceleration_mps2,
                self.max_deceleration_mps2,
                self.max_jerk_mps3,
                self.max_yaw_rate_radps,
            )
        ):
            raise ValueError("Kinematic limits must be finite, non-negative and versioned.")


@dataclass(frozen=True, slots=True)
class KinematicViolation:
    code: str
    state_index: int
    observed: float
    limit: float | None
    message: str


@dataclass(frozen=True, slots=True)
class CollisionCheck:
    status: str
    collisions: tuple[dict[str, object], ...] = ()
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class KinematicPreview:
    states: tuple[State, ...]
    source_state_version: str
    provenance: dict[str, str]
    violations: tuple[KinematicViolation, ...] = ()
    trace: ReplayTrace | None = None


def integrate_kinematic_open_loop(
    initial: State,
    source: SourceStateExtension,
    *,
    fixed_timestep_s: float = 0.05,
    limits: KinematicLimits = KinematicLimits(),
    actor_id: str = "ego",
) -> KinematicPreview:
    """Propagate measurements without changing canonical ``State`` or clamping."""
    if fixed_timestep_s <= 0 or not isfinite(fixed_timestep_s):
        raise ValueError("fixed_timestep_s must be finite and positive.")
    states = [initial]
    violations: list[KinematicViolation] = []
    accelerations: list[float] = []
    for index, measurement in enumerate(source.states[1:], 1):
        previous = states[-1]
        dt = min(
            fixed_timestep_s,
            max(0.0, measurement.timestamp_us - source.states[index - 1].timestamp_us) / 1_000_000,
        )
        acceleration = measurement.acceleration_mps2
        yaw_rate = measurement.yaw_rate_radps
        speed = previous.speed_mps + acceleration * dt
        yaw = previous.yaw_rad + yaw_rate * dt
        states.append(
            State(
                previous.time_s + dt,
                previous.x_m + speed * cos(yaw) * dt,
                previous.y_m + speed * sin(yaw) * dt,
                yaw,
                speed,
            )
        )
        accelerations.append(acceleration)
        _add_limit_violation(violations, "acceleration_exceeded", index, acceleration, limits.max_acceleration_mps2, actor_id, "Acceleration exceeds limit.")
        _add_limit_violation(violations, "deceleration_exceeded", index, -acceleration, limits.max_deceleration_mps2, actor_id, "Deceleration exceeds limit.", positive_only=True)
        _add_limit_violation(violations, "yaw_rate_exceeded", index, abs(yaw_rate), limits.max_yaw_rate_radps, actor_id, "Yaw rate exceeds limit.")
        if speed < 0:
            violations.append(KinematicViolation("negative_speed", index, speed, 0.0, f"{actor_id}: propagation produced negative speed; no clamp applied."))
        if len(accelerations) > 1:
            jerk = (accelerations[-1] - accelerations[-2]) / dt if dt else 0.0
            _add_limit_violation(violations, "jerk_exceeded", index, abs(jerk), limits.max_jerk_mps3, actor_id, "Jerk exceeds limit.")
    trace = ReplayTrace(tuple(ReplayState(actor_id, state) for state in states))
    provenance = {
        "simulator_version": KINEMATIC_VERSION,
        "kinematic_limits_version": limits.version,
        "fixed_timestep_s": format(fixed_timestep_s, ".12g"),
        "silent_clamps": "forbidden",
        **source.provenance,
    }
    return KinematicPreview(tuple(states), source.version, provenance, tuple(violations), trace)


def check_footprint_collisions(actors: Sequence[Actor]) -> CollisionCheck:
    """Check conservative center-distance footprints, failing closed on dimensions."""
    if any(actor.length_m is None or actor.width_m is None for actor in actors):
        return CollisionCheck("unsupported", reason="actor_dimensions_missing")
    collisions: list[dict[str, object]] = []
    for left_index, left in enumerate(actors):
        for right in actors[left_index + 1 :]:
            right_by_time = {round(state.time_s, 9): (index, state) for index, state in enumerate(right.trajectory)}
            left_radius = hypot(left.length_m or 0.0, left.width_m or 0.0) / 2
            right_radius = hypot(right.length_m or 0.0, right.width_m or 0.0) / 2
            for index, state in enumerate(left.trajectory):
                match = right_by_time.get(round(state.time_s, 9))
                if match is None:
                    continue
                right_index, other = match
                if hypot(state.x_m - other.x_m, state.y_m - other.y_m) <= left_radius + right_radius:
                    collisions.append({"left_actor_id": left.actor_id, "right_actor_id": right.actor_id, "left_state_index": index, "right_state_index": right_index})
    return CollisionCheck("collision" if collisions else "clear", tuple(collisions))


def _add_limit_violation(
    violations: list[KinematicViolation], code: str, index: int, observed: float,
    limit: float, actor_id: str, message: str, *, positive_only: bool = False,
) -> None:
    if (observed > limit if positive_only else observed > limit):
        violations.append(KinematicViolation(code, index, observed, limit, f"{actor_id}: {message}"))
