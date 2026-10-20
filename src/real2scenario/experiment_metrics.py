"""Metrics for diagnostic trajectory experiment arms.

These metrics are intentionally separate from the official replay metric role.
They compare a candidate trace to a frozen authored/reference trajectory.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, sin, sqrt
from statistics import mean
from typing import Sequence

from .models import State


EXPERIMENT_METRICS_VERSION = "trajectory-experiment-metrics-v1"


@dataclass(frozen=True, slots=True)
class ExperimentMetrics:
    version: str
    sample_count: int
    coverage_status: str
    overlap_start_s: float
    overlap_end_s: float
    position_ade_m: float
    position_fde_m: float | None
    position_rmse_m: float
    position_p95_m: float
    heading_mae_rad: float
    speed_mae_mps: float
    max_position_error_m: float
    max_heading_error_rad: float
    max_speed_error_mps: float


def compare_trajectory(reference: Sequence[State], candidate: Sequence[State]) -> ExperimentMetrics:
    """Compare candidate states on the reference time grid without extrapolation."""
    _validate(reference, "reference")
    _validate(candidate, "candidate")
    start = max(reference[0].time_s, candidate[0].time_s)
    end = min(reference[-1].time_s, candidate[-1].time_s)
    aligned = [(state, _interpolate(candidate, state.time_s)) for state in reference if start <= state.time_s <= end]
    if not aligned:
        raise ValueError("reference and candidate have no temporal overlap")
    position = [hypot(ref.x_m - got.x_m, ref.y_m - got.y_m) for ref, got in aligned]
    heading = [abs(_wrap(ref.yaw_rad - got.yaw_rad)) for ref, got in aligned]
    speed = [abs(ref.speed_mps - got.speed_mps) for ref, got in aligned]
    complete = candidate[0].time_s <= reference[0].time_s and candidate[-1].time_s >= reference[-1].time_s
    return ExperimentMetrics(
        version=EXPERIMENT_METRICS_VERSION,
        sample_count=len(aligned),
        coverage_status="complete" if complete else "partial",
        overlap_start_s=start,
        overlap_end_s=end,
        position_ade_m=mean(position),
        position_fde_m=position[-1] if complete else None,
        position_rmse_m=sqrt(mean(error * error for error in position)),
        position_p95_m=_percentile(position, 0.95),
        heading_mae_rad=mean(heading),
        speed_mae_mps=mean(speed),
        max_position_error_m=max(position),
        max_heading_error_rad=max(heading),
        max_speed_error_mps=max(speed),
    )


def _interpolate(states: Sequence[State], time_s: float) -> State:
    if time_s < states[0].time_s or time_s > states[-1].time_s:
        raise ValueError("candidate interpolation outside overlap")
    for left, right in zip(states, states[1:]):
        if time_s <= right.time_s:
            fraction = (time_s - left.time_s) / (right.time_s - left.time_s)
            yaw_delta = _wrap(right.yaw_rad - left.yaw_rad)
            return State(time_s, left.x_m + fraction * (right.x_m - left.x_m), left.y_m + fraction * (right.y_m - left.y_m), _wrap(left.yaw_rad + fraction * yaw_delta), left.speed_mps + fraction * (right.speed_mps - left.speed_mps))
    return states[-1]


def _validate(states: Sequence[State], name: str) -> None:
    if not states or any(right.time_s <= left.time_s for left, right in zip(states, states[1:])):
        raise ValueError(f"{name} trajectory must be non-empty and strictly time ordered")


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _wrap(angle: float) -> float:
    return atan2(sin(angle), cos(angle))
