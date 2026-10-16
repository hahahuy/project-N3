"""Optional nuScenes-devkit-backed source measurements.

The canonical scenario remains dataset-agnostic.  This module only adapts
measurements that the official devkit can provide and reports capability and
fallback decisions through small, JSON-safe records.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


CAN_ADAPTER_VERSION = "nuscenes-can-pose-v1"
CAN_VEHICLE_MONITOR_ADAPTER_VERSION = "nuscenes-can-vehicle-monitor-v1"
VEHICLE_MONITOR_MESSAGES = ("vehicle_monitor",)
BRAKE_FIELD = "brake"


@dataclass(frozen=True, slots=True)
class CanPoseSample:
    """One CAN pose measurement normalized to SI units."""

    timestamp_us: int
    speed_mps: float | None
    acceleration_mps2: float | None
    yaw_rate_radps: float | None


@dataclass(frozen=True, slots=True)
class CanVehicleMonitorSample:
    """One recorded ego pedal/brake measurement normalized to SI-free units."""

    timestamp_us: int
    brake_pressure: float


class NuScenesSourceAdapter:
    """Lazy adapter for optional devkit sources used by ingestion."""

    def __init__(self, dataset_root: str | Path, *, max_misalignment: float = 5.0) -> None:
        self.dataset_root = Path(dataset_root).expanduser()
        self.max_misalignment = max_misalignment
        self._can_bus: Any | None = None
        self._can_error: str | None = None

    def _messages(self, scene_name: str, message_name: str) -> tuple[Mapping[str, Any], ...]:
        """Return normalized CAN messages, or an empty capability result."""
        if not (self.dataset_root / "can_bus").is_dir():
            self._can_error = "can_bus_directory_missing"
            return ()
        if self._can_bus is None and self._can_error is None:
            try:
                from nuscenes.can_bus.can_bus_api import NuScenesCanBus

                self._can_bus = NuScenesCanBus(
                    dataroot=str(self.dataset_root), max_misalignment=self.max_misalignment
                )
            except (Exception,) as error:
                self._can_error = type(error).__name__
        if self._can_bus is None:
            return ()
        if message_name not in getattr(self._can_bus, "all_messages", ()):
            return ()
        try:
            messages = self._can_bus.get_messages(scene_name, message_name, print_warnings=False)
        except (AssertionError, OSError, KeyError, TypeError, ValueError):
            return ()
        except Exception as error:
            # The devkit signals "no CAN data for this scene" with a bare
            # Exception, which the narrow tuple above cannot catch. CAN pose is
            # an optional capability with a documented finite-difference
            # fallback, so an unavailable source must degrade to an empty
            # capability result rather than abort the whole run.
            self._can_error = type(error).__name__
            return ()
        if not isinstance(messages, list):
            return ()
        return tuple(
            message for message in messages if isinstance(message, Mapping)
        )

    def can_vehicle_monitor(self, scene_name: str) -> tuple[CanVehicleMonitorSample, ...]:
        """Load recorded ego braking pedal samples, or an empty capability result."""
        samples = [
            sample
            for message in self._messages(scene_name, VEHICLE_MONITOR_MESSAGES[0])
            for sample in (_normalize_vehicle_monitor(message),)
            if sample is not None
        ]
        return tuple(sorted(samples, key=lambda sample: sample.timestamp_us))

    def can_pose(self, scene_name: str) -> tuple[CanPoseSample, ...]:
        """Load normalized CAN pose samples, or return an empty capability result."""
        samples = tuple(
            sample
            for message in self._messages(scene_name, "pose")
            for sample in (_normalize_can_pose(message),)
            if sample is not None
        )
        return tuple(sorted(samples, key=lambda sample: sample.timestamp_us))

    def provenance(self, *, scene_name: str, used: bool, sample_count: int) -> dict[str, str]:
        """Return compact source provenance without exposing private data paths."""
        return {
            "can_adapter_version": CAN_ADAPTER_VERSION,
            "can_scene": scene_name,
            "can_pose_status": "used" if used else "fallback_finite_difference",
            "can_pose_sample_count": str(sample_count),
            "can_max_misalignment_m": format(self.max_misalignment, ".6g"),
        }

    def source_state_extension(
        self,
        scene_name: str,
        timestamps_us: Sequence[int],
        positions: Sequence[tuple[float, float]],
        yaws: Sequence[float],
    ):
        """Build the versioned Tier 1 extension without changing canonical State."""
        from .source_state import build_source_state_extension

        return build_source_state_extension(
            timestamps_us, positions, yaws, self.can_pose(scene_name)
        )


def nearest_can_poses(
    timestamps_us: Sequence[int], poses: Sequence[CanPoseSample], *, max_gap_us: int = 100_000
) -> tuple[CanPoseSample | None, ...]:
    """Match requested timestamps to CAN poses without extrapolating."""
    if not poses:
        return tuple(None for _ in timestamps_us)
    result: list[CanPoseSample | None] = []
    for timestamp in timestamps_us:
        candidate = min(poses, key=lambda pose: abs(pose.timestamp_us - timestamp))
        result.append(candidate if abs(candidate.timestamp_us - timestamp) <= max_gap_us else None)
    return tuple(result)


def _normalize_vehicle_monitor(
    message: Mapping[str, Any],
) -> CanVehicleMonitorSample | None:
    """Normalize one recorded ego braking pedal message."""
    timestamp = message.get("utime")
    brake = message.get(BRAKE_FIELD)
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        return None
    if isinstance(brake, bool) or not isinstance(brake, (int, float)) or not math.isfinite(float(brake)):
        return None
    return CanVehicleMonitorSample(int(timestamp), float(brake))


def _normalize_can_pose(message: Mapping[str, Any]) -> CanPoseSample | None:
    timestamp = message.get("utime")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        return None
    speed = _vector_norm(message.get("vel"))
    acceleration = _vector_norm(message.get("accel"))
    yaw_rate = _yaw_rate(message.get("rotation_rate"))
    if speed is None and acceleration is None and yaw_rate is None:
        return None
    return CanPoseSample(int(timestamp), speed, acceleration, yaw_rate)


def _vector_norm(value: Any) -> float | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    numbers = value[:3]
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in numbers):
        return None
    return math.sqrt(sum(float(item) ** 2 for item in numbers))


def _yaw_rate(value: Any) -> float | None:
    if isinstance(value, (list, tuple)):
        if not value or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
            return None
        return float(value[-1])
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
