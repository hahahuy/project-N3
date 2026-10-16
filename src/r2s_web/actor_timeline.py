"""Time-indexed actor state tracks for the Workspace timeline.

Every track is derived from canonical actor states.  Position, heading and
speed are canonical values.  Acceleration is a declared deterministic derivative
of the canonical speed series.  Braking is a recorded nuScenes CAN pedal channel
when the dataset supplies it and is otherwise reported as unavailable or
unsupported with an API-owned reason.

A sample value that cannot be resolved is ``None``.  ``None`` means ``n/a`` in
the browser and is never rendered as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from real2scenario.models import Scenario

from .config import WebSettings


ACTOR_TIMELINE_VERSION = "workspace-actor-timeline-v1"
ACCELERATION_VERSION = "workspace-finite-difference-acceleration-v1"
BRAKING_VERSION = "nuscenes-can-vehicle-monitor-v1"
BRAKING_MAX_GAP_US = 100_000

REASON_NO_SOURCE_TIMESTAMPS = "canonical_states_missing_source_timestamp_us"
REASON_DATASET_NOT_CONFIGURED = "dataset_not_configured"
REASON_NO_SOURCE_SCENE = "scenario_provenance_declares_no_can_scene"
REASON_BRAKE_CHANNEL_ABSENT = "recorded_brake_channel_absent_for_source_scene"
REASON_BRAKE_CHANNEL_UNAVAILABLE = "recorded_brake_channel_unavailable"
REASON_NON_EGO_BRAKE = "recorded_brake_channel_records_ego_only"
REASON_INSUFFICIENT_STATES = "insufficient_states_for_finite_difference"


@dataclass(frozen=True, slots=True)
class TimelineSample:
    """One resolved actor state; missing channels stay ``None``."""

    time_s: float
    x_m: float
    y_m: float
    yaw_rad: float
    speed_mps: float
    acceleration_mps2: float | None = None
    acceleration_source: str | None = None
    braking_pressure: float | None = None
    braking_source: str | None = None

    def __post_init__(self) -> None:
        values = (self.time_s, self.x_m, self.y_m, self.yaw_rad, self.speed_mps)
        if not all(isfinite(value) for value in values):
            raise ValueError("Canonical timeline sample values must be finite.")
        for optional in (
            self.acceleration_mps2,
            self.braking_pressure,
        ):
            if optional is not None and not isfinite(optional):
                raise ValueError("Derived timeline sample values must be finite.")
        if (self.acceleration_mps2 is None) != (self.acceleration_source is None):
            raise ValueError("Acceleration and its source must be resolved together.")
        if (self.braking_pressure is None) != (self.braking_source is None):
            raise ValueError("Braking and its source must be resolved together.")


@dataclass(frozen=True, slots=True)
class BrakingMeasurement:
    """One recorded ego braking pedal sample."""

    timestamp_us: int
    brake_pressure: float

    def __post_init__(self) -> None:
        if self.timestamp_us < 0 or not isfinite(self.brake_pressure):
            raise ValueError("Braking measurements must be finite and non-negative in time.")


def actor_timeline(scenario: Scenario, settings: WebSettings | None = None) -> dict[str, object]:
    """Return one time-indexed track per actor with explicit channel status."""
    braking, braking_reason = _resolve_braking_channel(scenario, settings)
    return {
        "contract_version": ACTOR_TIMELINE_VERSION,
        "scenario_id": scenario.scenario_id,
        "coordinate_frame": scenario.coordinate_frame,
        "time_domain": {"start_s": 0.0, "end_s": scenario.duration_s},
        "tracks": [
            _track(scenario, actor, braking, braking_reason) for actor in scenario.actors
        ],
        "artifact_visibility": "local_private",
    }


def _track(
    scenario: Scenario,
    actor: object,
    braking: Sequence[BrakingMeasurement],
    braking_reason: str | None,
) -> dict[str, object]:
    """Build one actor track from its canonical states."""
    states = actor.trajectory
    is_ego = actor.actor_id == scenario.ego_actor_id
    brake_reason = braking_reason if is_ego else REASON_NON_EGO_BRAKE
    accelerations, acceleration_reason = _accelerations(states)
    timestamps = [state.source_timestamp_us for state in states]
    if is_ego and brake_reason is None and any(timestamp is None for timestamp in timestamps):
        brake_reason = REASON_NO_SOURCE_TIMESTAMPS
    brake_channel = braking if is_ego and brake_reason is None else ()
    brake_values = _match_braking(timestamps, brake_channel)
    samples = [
        TimelineSample(
            time_s=state.time_s,
            x_m=state.x_m,
            y_m=state.y_m,
            yaw_rad=state.yaw_rad,
            speed_mps=state.speed_mps,
            acceleration_mps2=accelerations[index],
            acceleration_source=None if accelerations[index] is None else "finite_difference",
            braking_pressure=brake_values[index],
            braking_source=None if brake_values[index] is None else "can_vehicle_monitor",
        )
        for index, state in enumerate(states)
    ]
    return {
        "actor_id": actor.actor_id,
        "actor_type": actor.actor_type,
        "role": "ego" if is_ego else "actor",
        "channels": {
            "position": _available("canonical-state-v1", None),
            "heading": _available("canonical-state-v1", None),
            "speed": _available("canonical-state-v1", None),
            "acceleration": _available(
                ACCELERATION_VERSION, acceleration_reason, accelerations
            ),
            "braking": _available(BRAKING_VERSION, brake_reason, brake_values),
        },
        "samples": [
            {
                "time_s": sample.time_s,
                "x_m": sample.x_m,
                "y_m": sample.y_m,
                "yaw_rad": sample.yaw_rad,
                "speed_mps": sample.speed_mps,
                "acceleration_mps2": sample.acceleration_mps2,
                "acceleration_source": sample.acceleration_source,
                "braking_pressure": sample.braking_pressure,
                "braking_source": sample.braking_source,
            }
            for sample in samples
        ],
    }


def _available(
    version: str, reason: str | None, values: Sequence[float | None] = ()
) -> dict[str, object]:
    """Report availability, coverage and the API-owned reason for one channel."""
    resolved = [value for value in values if value is not None]
    return {
        "available": reason is None,
        "unavailable_reason": reason,
        "version": version,
        "coverage": None if not values else len(resolved) / len(values),
    }


def _accelerations(states: Sequence[object]) -> tuple[list[float | None], str | None]:
    """Differentiate the canonical speed series without clamping or defaults."""
    if len(states) < 2:
        return [None] * len(states), REASON_INSUFFICIENT_STATES
    times = [state.time_s for state in states]
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        return [None] * len(states), REASON_INSUFFICIENT_STATES
    speeds = [state.speed_mps for state in states]
    values: list[float | None] = []
    for index in range(len(states)):
        left, right = max(0, index - 1), min(len(states) - 1, index + 1)
        span = times[right] - times[left]
        values.append(None if span <= 0 else (speeds[right] - speeds[left]) / span)
    return values, None


def _resolve_braking_channel(
    scenario: Scenario, settings: WebSettings | None
) -> tuple[tuple[BrakingMeasurement, ...], str | None]:
    """Resolve the recorded ego braking channel or name why it is absent."""
    scene_name = scenario.provenance.get("can_scene")
    if not scene_name:
        return (), REASON_NO_SOURCE_SCENE
    if settings is None or settings.dataset_root is None:
        return (), REASON_DATASET_NOT_CONFIGURED
    from real2scenario.nuscenes_backend import NuScenesSourceAdapter

    try:
        samples = NuScenesSourceAdapter(settings.dataset_root).can_vehicle_monitor(scene_name)
    except (ImportError, OSError, RuntimeError, ValueError, KeyError):
        return (), REASON_BRAKE_CHANNEL_UNAVAILABLE
    if not samples:
        return (), REASON_BRAKE_CHANNEL_ABSENT
    return samples, None


def _match_braking(
    timestamps: Sequence[int | None], braking: Sequence[BrakingMeasurement]
) -> list[float | None]:
    """Match recorded pedal samples to canonical timestamps without extrapolation."""
    if not timestamps or any(timestamp is None for timestamp in timestamps):
        return [None] * len(timestamps)
    if not braking:
        # No channel to match against. The caller keeps the unavailable reason,
        # so this must degrade to empty rather than fail.
        return [None] * len(timestamps)
    result: list[float | None] = []
    for timestamp in timestamps:
        nearest = min(braking, key=lambda item: abs(item.timestamp_us - timestamp))
        gap = abs(nearest.timestamp_us - timestamp)
        result.append(nearest.brake_pressure if gap <= BRAKING_MAX_GAP_US else None)
    return result