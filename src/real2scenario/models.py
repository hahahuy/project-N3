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
    source_timestamp_us: int | None = None
    source_record_token: str | None = None

    def __post_init__(self) -> None:
        values = (self.time_s, self.x_m, self.y_m, self.yaw_rad, self.speed_mps)
        if not all(isfinite(value) for value in values):
            raise ValueError("State values must be finite.")
        if self.time_s < 0:
            raise ValueError("State time_s must be non-negative.")
        if self.source_timestamp_us is not None and (
            isinstance(self.source_timestamp_us, bool)
            or not isinstance(self.source_timestamp_us, int)
            or self.source_timestamp_us < 0
        ):
            raise ValueError("State source_timestamp_us must be a non-negative integer.")
        if self.source_record_token is not None and not self.source_record_token:
            raise ValueError("State source_record_token must not be empty.")


@dataclass(frozen=True, slots=True)
class Actor:
    """A tracked entity with a strictly time-ordered trajectory."""

    actor_id: str
    actor_type: str
    trajectory: tuple[State, ...]
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None

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
        for dimension in (self.length_m, self.width_m, self.height_m):
            if dimension is not None and (not isfinite(dimension) or dimension <= 0):
                raise ValueError("Actor dimensions must be finite and positive.")

    @property
    def observed_start_s(self) -> float:
        """First recorded state time, in scenario-relative seconds."""
        return self.trajectory[0].time_s

    @property
    def observed_end_s(self) -> float:
        """Last recorded state time, in scenario-relative seconds."""
        return self.trajectory[-1].time_s

    @property
    def observation_count(self) -> int:
        """Number of recorded states backing this actor track."""
        return len(self.trajectory)

    def lifecycle_status(self, window_start_s: float, window_end_s: float) -> str:
        """Classify how this track sits inside the requested scenario window.

        The status is descriptive, never a motion instruction: the recorded
        trajectory is the only source of actor timing, and a replayer must not
        invent movement before ``observed_start_s`` or after ``observed_end_s``.
        """
        if self.observed_start_s <= window_start_s and self.observed_end_s >= window_end_s:
            return "full_window"
        if self.observed_start_s > window_start_s and self.observed_end_s >= window_end_s:
            return "late_entry"
        if self.observed_start_s <= window_start_s and self.observed_end_s < window_end_s:
            return "early_exit"
        if self.observed_start_s > window_start_s and self.observed_end_s < window_end_s:
            return "late_entry_and_early_exit"
        return "bounded_track"


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    """A derived, non-binding annotation of an interaction between actors.

    These are analysis outputs derived from recorded positions. They are never
    recorded source facts and must not be used to generate motion, gates or
    metrics on their own.
    """

    label: str
    actor_ids: tuple[str, ...]
    start_time_s: float
    end_time_s: float
    derivation: str = "derived_analysis"
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("InteractionEvent label must not be empty.")
        if not self.actor_ids:
            raise ValueError("InteractionEvent actor_ids must not be empty.")
        if len(self.actor_ids) != len(set(self.actor_ids)):
            raise ValueError("InteractionEvent actor_ids must be unique.")
        if not isfinite(self.start_time_s) or not isfinite(self.end_time_s):
            raise ValueError("InteractionEvent times must be finite.")
        if self.start_time_s < 0:
            raise ValueError("InteractionEvent start_time_s must be non-negative.")
        if self.end_time_s < self.start_time_s:
            raise ValueError("InteractionEvent end_time_s must not precede start_time_s.")
        if not self.derivation:
            raise ValueError("InteractionEvent derivation must not be empty.")
        if self.confidence is not None and (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not isfinite(float(self.confidence))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("InteractionEvent confidence must be within [0, 1].")


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
    replay_mode: str = "open_loop_trajectory"
    interaction_events: tuple[InteractionEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("Scenario scenario_id must not be empty.")
        if not isfinite(self.duration_s) or self.duration_s <= 0:
            raise ValueError("Scenario duration_s must be finite and positive.")
        if not self.coordinate_frame:
            raise ValueError("Scenario coordinate_frame must not be empty.")
        if not self.actors:
            raise ValueError("Scenario must contain at least one actor.")
        if not self.replay_mode:
            raise ValueError("Scenario replay_mode must not be empty.")

        actor_ids = [actor.actor_id for actor in self.actors]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("Scenario actor IDs must be unique.")
        if self.ego_actor_id not in actor_ids:
            raise ValueError("Scenario ego_actor_id must identify an actor.")
        if any(actor.trajectory[-1].time_s > self.duration_s for actor in self.actors):
            raise ValueError("Scenario duration_s must cover every actor trajectory.")
        for event in self.interaction_events:
            unknown = [actor_id for actor_id in event.actor_ids if actor_id not in actor_ids]
            if unknown:
                raise ValueError(
                    f"InteractionEvent {event.label!r} references unknown actors: {sorted(unknown)}"
                )
            if event.end_time_s > self.duration_s:
                raise ValueError(
                    f"InteractionEvent {event.label!r} end_time_s must not exceed scenario duration_s."
                )
