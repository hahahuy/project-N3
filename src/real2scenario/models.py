"""Simulator-independent scenario contracts used throughout the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


@dataclass(frozen=True, slots=True)
class State:
    """One actor state in SI units within a declared coordinate frame."""

    time_s: float
    x_m: float
    y_m: float
    yaw_rad: float
    speed_mps: float

    def __post_init__(self) -> None:
        values = (self.time_s, self.x_m, self.y_m, self.yaw_rad, self.speed_mps)
        if not all(isfinite(value) for value in values):
            raise ValueError("State values must be finite.")
        if self.time_s < 0:
            raise ValueError("State time_s must be non-negative.")


@dataclass(frozen=True, slots=True)
class Actor:
    """A tracked entity with a strictly time-ordered trajectory."""

    actor_id: str
    actor_type: str
    trajectory: tuple[State, ...]
    length_m: float | None = None
    width_m: float | None = None

    def __post_init__(self) -> None:
        if not self.actor_id:
            raise ValueError("Actor actor_id must not be empty.")
        if not self.actor_type:
            raise ValueError("Actor actor_type must not be empty.")
        if not self.trajectory:
            raise ValueError("Actor trajectory must contain at least one state.")
        if any(
            later.time_s <= earlier.time_s
            for earlier, later in zip(self.trajectory, self.trajectory[1:])
        ):
            raise ValueError("Actor trajectory timestamps must strictly increase.")
        for dimension in (self.length_m, self.width_m):
            if dimension is not None and (not isfinite(dimension) or dimension <= 0):
                raise ValueError("Actor dimensions must be finite and positive.")


@dataclass(frozen=True, slots=True)
class VariantConfig:
    """Replayable controlled changes applied to a baseline scenario."""

    speed_multiplier: float = 1.0
    initial_gap_delta_m: float = 0.0
    timing_offset_s: float = 0.0
    seed: int = 0

    def __post_init__(self) -> None:
        if not isfinite(self.speed_multiplier) or self.speed_multiplier <= 0:
            raise ValueError("Variant speed_multiplier must be finite and positive.")
        if not isfinite(self.initial_gap_delta_m):
            raise ValueError("Variant initial_gap_delta_m must be finite.")
        if not isfinite(self.timing_offset_s):
            raise ValueError("Variant timing_offset_s must be finite.")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("Variant seed must be an integer.")


@dataclass(frozen=True, slots=True)
class Scenario:
    """A complete recorded or generated scenario in one named frame."""

    scenario_id: str
    duration_s: float
    ego_actor_id: str
    actors: tuple[Actor, ...]
    coordinate_frame: str
    provenance: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("Scenario scenario_id must not be empty.")
        if not isfinite(self.duration_s) or self.duration_s <= 0:
            raise ValueError("Scenario duration_s must be finite and positive.")
        if not self.coordinate_frame:
            raise ValueError("Scenario coordinate_frame must not be empty.")
        if not self.actors:
            raise ValueError("Scenario must contain at least one actor.")

        actor_ids = [actor.actor_id for actor in self.actors]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("Scenario actor IDs must be unique.")
        if self.ego_actor_id not in actor_ids:
            raise ValueError("Scenario ego_actor_id must identify an actor.")
        if any(actor.trajectory[-1].time_s > self.duration_s for actor in self.actors):
            raise ValueError("Scenario duration_s must cover every actor trajectory.")
