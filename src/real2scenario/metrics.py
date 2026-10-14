"""Timestamp-aligned fidelity metrics for recorded and replayed trajectories."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, sin, sqrt
from typing import Sequence

from .models import Scenario, State
from .simulation import ReplayTrace


ALIGNMENT_METHOD = "recorded_timestamps_linear_interpolation_within_overlap"


@dataclass(frozen=True, slots=True)
class ReplayMetrics:
    """Trajectory-fidelity metrics in SI units over one aligned actor trajectory."""

    sample_count: int
    alignment_method: str
    position_rmse_m: float
    final_displacement_m: float
    heading_mae_rad: float
    speed_mae_mps: float
    ade_m: float
    fde_m: float | None
    coverage_status: str


@dataclass(frozen=True, slots=True)
class MetricDistribution:
    mean: float
    median: float
    p95: float
    max: float


@dataclass(frozen=True, slots=True)
class ReplayMetricAggregate:
    actor_count: int
    ade_m: MetricDistribution
    fde_m: MetricDistribution | None


def aggregate_replay_metrics(metrics: Sequence[ReplayMetrics]) -> ReplayMetricAggregate:
    """Aggregate per-actor metrics without treating missing FDE as zero."""
    if not metrics:
        raise ValueError("At least one replay metric is required.")
    ade_values = [metric.ade_m for metric in metrics]
    fde_values = [metric.fde_m for metric in metrics if metric.fde_m is not None]
    return ReplayMetricAggregate(
        actor_count=len(metrics),
        ade_m=_distribution(ade_values),
        fde_m=None if not fde_values else _distribution(fde_values),
    )


def compute_replay_metrics(
    recorded_states: Sequence[State], replayed_states: Sequence[State]
) -> ReplayMetrics:
    """Compare trajectories using linearly interpolated replay states at recorded times."""
    _validate_trajectory(recorded_states, "Recorded")
    _validate_trajectory(replayed_states, "Replayed")
    replay_start_s = replayed_states[0].time_s
    replay_end_s = replayed_states[-1].time_s
    aligned = tuple(
        (recorded, _interpolate(replayed_states, recorded.time_s))
        for recorded in recorded_states
        if replay_start_s <= recorded.time_s <= replay_end_s
    )
    if not aligned:
        raise ValueError("Recorded and replayed trajectories do not have an overlapping timestamp.")

    squared_position_errors = tuple(
        (recorded.x_m - replayed.x_m) ** 2 + (recorded.y_m - replayed.y_m) ** 2
        for recorded, replayed in aligned
    )
    heading_errors = tuple(
        abs(_wrap_angle(recorded.yaw_rad - replayed.yaw_rad)) for recorded, replayed in aligned
    )
    speed_errors = tuple(abs(recorded.speed_mps - replayed.speed_mps) for recorded, replayed in aligned)
    final_recorded, final_replayed = aligned[-1]
    position_errors = tuple(squared_error**0.5 for squared_error in squared_position_errors)
    coverage_status = "complete" if replay_end_s >= recorded_states[-1].time_s else "insufficient_coverage"
    return ReplayMetrics(
        sample_count=len(aligned),
        alignment_method=ALIGNMENT_METHOD,
        position_rmse_m=sqrt(sum(squared_position_errors) / len(squared_position_errors)),
        final_displacement_m=hypot(
            final_recorded.x_m - final_replayed.x_m,
            final_recorded.y_m - final_replayed.y_m,
        ),
        heading_mae_rad=sum(heading_errors) / len(heading_errors),
        speed_mae_mps=sum(speed_errors) / len(speed_errors),
        ade_m=sum(position_errors) / len(position_errors),
        fde_m=(
            hypot(final_recorded.x_m - final_replayed.x_m, final_recorded.y_m - final_replayed.y_m)
            if coverage_status == "complete"
            else None
        ),
        coverage_status=coverage_status,
    )


def compute_scenario_replay_metrics(
    scenario: Scenario,
    replay_trace: ReplayTrace,
    *,
    min_track_duration_s: float = 0.0,
) -> "ScenarioReplayMetrics":
    """Compute metrics and explicit short-track exclusions for each actor."""
    if min_track_duration_s < 0:
        raise ValueError("min_track_duration_s must be non-negative.")
    metrics: dict[str, ReplayMetrics] = {}
    excluded: list[str] = []
    for actor in scenario.actors:
        duration_s = actor.trajectory[-1].time_s - actor.trajectory[0].time_s
        if duration_s < min_track_duration_s:
            excluded.append(actor.actor_id)
            continue
        metrics[actor.actor_id] = compute_replay_metrics(
            actor.trajectory, replay_trace.states_for(actor.actor_id)
        )
    return ScenarioReplayMetrics(metrics=metrics, excluded_short_tracks=tuple(excluded))


@dataclass(frozen=True, slots=True)
class ScenarioReplayMetrics:
    """Per-actor metrics plus actors excluded by the short-track policy."""

    metrics: dict[str, ReplayMetrics]
    excluded_short_tracks: tuple[str, ...]

    def __getitem__(self, actor_id: str) -> ReplayMetrics:
        return self.metrics[actor_id]

    def __iter__(self):
        return iter(self.metrics)

    def items(self):
        return self.metrics.items()

    def keys(self):
        return self.metrics.keys()


def _validate_trajectory(states: Sequence[State], label: str) -> None:
    if not states:
        raise ValueError(f"{label} trajectory is empty.")
    if any(later.time_s <= earlier.time_s for earlier, later in zip(states, states[1:])):
        raise ValueError(f"{label} trajectory timestamps must strictly increase.")


def _interpolate(states: Sequence[State], time_s: float) -> State:
    if time_s == states[0].time_s:
        return states[0]
    for earlier, later in zip(states, states[1:]):
        if time_s == later.time_s:
            return later
        if earlier.time_s < time_s < later.time_s:
            fraction = (time_s - earlier.time_s) / (later.time_s - earlier.time_s)
            return State(
                time_s=time_s,
                x_m=_lerp(earlier.x_m, later.x_m, fraction),
                y_m=_lerp(earlier.y_m, later.y_m, fraction),
                yaw_rad=_interpolate_angle(earlier.yaw_rad, later.yaw_rad, fraction),
                speed_mps=_lerp(earlier.speed_mps, later.speed_mps, fraction),
            )
    raise ValueError(f"Cannot interpolate replay state at timestamp {time_s}.")


def _lerp(start: float, end: float, fraction: float) -> float:
    return start + (end - start) * fraction


def _interpolate_angle(start_rad: float, end_rad: float, fraction: float) -> float:
    return _wrap_angle(start_rad + _wrap_angle(end_rad - start_rad) * fraction)


def _wrap_angle(angle_rad: float) -> float:
    return atan2(sin(angle_rad), cos(angle_rad))


def _distribution(values: Sequence[float]) -> MetricDistribution:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    median = ordered[midpoint] if len(ordered) % 2 else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    p95_index = min(len(ordered) - 1, max(0, int(0.95 * len(ordered) + 0.999999) - 1))
    return MetricDistribution(
        mean=sum(ordered) / len(ordered),
        median=median,
        p95=ordered[p95_index],
        max=ordered[-1],
    )
