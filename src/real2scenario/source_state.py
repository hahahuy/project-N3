"""Versioned source measurements for physics-adjacent preview paths.

These records deliberately do not extend :class:`models.State`.  They are
adapter output consumed by Tier 1 and carry the measurement/fallback decision
at the boundary where it is still meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from .nuscenes_backend import CanPoseSample, nearest_can_poses


SOURCE_STATE_VERSION = "source-state-extension-v1"


@dataclass(frozen=True, slots=True)
class SourceState:
    """Optional measured kinematic inputs aligned to one canonical timestamp."""

    timestamp_us: int
    acceleration_mps2: float
    yaw_rate_radps: float
    acceleration_source: str
    yaw_rate_source: str

    def __post_init__(self) -> None:
        if self.timestamp_us < 0 or not all(
            isfinite(value) for value in (self.acceleration_mps2, self.yaw_rate_radps)
        ):
            raise ValueError("SourceState values must be finite and timestamp non-negative.")
        if self.acceleration_source not in {"can_pose", "finite_difference"}:
            raise ValueError("Unsupported acceleration source.")
        if self.yaw_rate_source not in {"can_pose", "finite_difference"}:
            raise ValueError("Unsupported yaw-rate source.")


@dataclass(frozen=True, slots=True)
class SourceStateExtension:
    version: str
    states: tuple[SourceState, ...]
    provenance: dict[str, str]

    def __post_init__(self) -> None:
        if self.version != SOURCE_STATE_VERSION or not self.states:
            raise ValueError("SourceStateExtension requires the supported version and states.")


def build_source_state_extension(
    timestamps_us: Sequence[int],
    positions: Sequence[tuple[float, float]],
    yaws: Sequence[float],
    can_samples: Sequence[CanPoseSample] = (),
    *,
    max_gap_us: int = 100_000,
) -> SourceStateExtension:
    """Align CAN pose acceleration/yaw-rate, explicitly differentiating gaps."""
    if not (len(timestamps_us) == len(positions) == len(yaws)) or not timestamps_us:
        raise ValueError("Source-state inputs must have equal, non-empty lengths.")
    if any(later <= earlier for earlier, later in zip(timestamps_us, timestamps_us[1:])):
        raise ValueError("Source-state timestamps must strictly increase.")
    matches = nearest_can_poses(timestamps_us, can_samples, max_gap_us=max_gap_us)
    accelerations = _finite_difference_acceleration(timestamps_us, positions)
    yaw_rates = _finite_difference_yaw_rate(timestamps_us, yaws)
    states = tuple(
        SourceState(
            timestamp_us=int(timestamp),
            acceleration_mps2=(match.acceleration_mps2 if match and match.acceleration_mps2 is not None else accelerations[index]),
            yaw_rate_radps=(match.yaw_rate_radps if match and match.yaw_rate_radps is not None else yaw_rates[index]),
            acceleration_source="can_pose" if match and match.acceleration_mps2 is not None else "finite_difference",
            yaw_rate_source="can_pose" if match and match.yaw_rate_radps is not None else "finite_difference",
        )
        for index, (timestamp, match) in enumerate(zip(timestamps_us, matches))
    )
    can_count = sum(state.acceleration_source == "can_pose" or state.yaw_rate_source == "can_pose" for state in states)
    return SourceStateExtension(
        SOURCE_STATE_VERSION,
        states,
        {
            "source_state_version": SOURCE_STATE_VERSION,
            "source_state_status": "can_pose" if can_count else "fallback_finite_difference",
            "source_state_can_matched_count": str(can_count),
            "source_state_fallback": "explicit_finite_difference",
        },
    )


def _finite_difference_acceleration(timestamps: Sequence[int], positions: Sequence[tuple[float, float]]) -> list[float]:
    speeds = _finite_difference_speed(timestamps, positions)
    return _finite_difference_scalar(timestamps, speeds)


def _finite_difference_speed(timestamps: Sequence[int], positions: Sequence[tuple[float, float]]) -> list[float]:
    if len(timestamps) == 1:
        return [0.0]
    result = []
    for index in range(len(timestamps)):
        left, right = max(0, index - 1), min(len(timestamps) - 1, index + 1)
        dt = (timestamps[right] - timestamps[left]) / 1_000_000
        if dt <= 0:
            raise ValueError("Source-state timestamps must increase.")
        result.append(((positions[right][0] - positions[left][0]) ** 2 + (positions[right][1] - positions[left][1]) ** 2) ** 0.5 / dt)
    return result


def _finite_difference_scalar(timestamps: Sequence[int], values: Sequence[float]) -> list[float]:
    if len(timestamps) == 1:
        return [0.0]
    result = []
    for index in range(len(timestamps)):
        left, right = max(0, index - 1), min(len(timestamps) - 1, index + 1)
        dt = (timestamps[right] - timestamps[left]) / 1_000_000
        if dt <= 0:
            raise ValueError("Source-state timestamps must increase.")
        result.append((values[right] - values[left]) / dt)
    return result


def _finite_difference_yaw_rate(timestamps: Sequence[int], yaws: Sequence[float]) -> list[float]:
    from math import atan2, cos, sin
    unwrapped = list(yaws)
    result = []
    for index in range(len(timestamps)):
        left, right = max(0, index - 1), min(len(timestamps) - 1, index + 1)
        dt = (timestamps[right] - timestamps[left]) / 1_000_000
        if dt <= 0:
            raise ValueError("Source-state timestamps must increase.")
        result.append(atan2(sin(unwrapped[right] - unwrapped[left]), cos(unwrapped[right] - unwrapped[left])) / dt)
    return result
