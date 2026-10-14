"""Normalized CARLA trace and cleanup report contracts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


TRACE_SCHEMA_VERSION = "normalized-replay-trace-v2"


@dataclass(frozen=True, slots=True)
class CarlaTraceState:
    run_id: str
    backend_id: str
    backend_version: str
    replay_mode: str
    timestamp_s: float
    tick_index: int
    actor_id: str
    x_m: float
    y_m: float
    z_m: float
    velocity_x_mps: float
    velocity_y_mps: float
    velocity_z_mps: float
    speed_mps: float
    target_x_m: float | None = None
    target_y_m: float | None = None
    target_yaw_rad: float | None = None
    target_speed_mps: float | None = None
    coordinate_frame: str = "carla_world"
    xosc_sha256: str | None = None
    xodr_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.run_id or not self.backend_id or not self.actor_id:
            raise ValueError("CARLA trace identity fields must not be empty.")
        if self.tick_index < 0 or not isfinite(self.timestamp_s):
            raise ValueError("CARLA trace time values are invalid.")
        if not all(
            isfinite(value)
            for value in (
                self.x_m,
                self.y_m,
                self.z_m,
                self.velocity_x_mps,
                self.velocity_y_mps,
                self.velocity_z_mps,
                self.speed_mps,
            )
        ):
            raise ValueError("CARLA trace state values must be finite.")


@dataclass(frozen=True, slots=True)
class CarlaCleanupReport:
    actors_destroyed: int
    sensors_destroyed: int
    world_settings_restored: bool
    cleanup_error: str | None = None

    @property
    def complete(self) -> bool:
        return self.cleanup_error is None and self.world_settings_restored
