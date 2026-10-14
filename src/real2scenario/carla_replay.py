"""Pure-Python CP2-A exact-pose replay planning contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from math import atan2, cos, isfinite, sin
from pathlib import Path
from typing import Mapping, Protocol

from .xosc_subset import (
    ValidatedXoscScenario,
    XoscExecutionIdentity,
    XoscInterpretation,
    build_execution_identity,
    interpret_xosc_subset,
)

CARLA_ALIGNMENT_VERSION = "carla-alignment-v1"
BLUEPRINT_MAPPING_VERSION = "carla-blueprint-map-v1"
EXACT_POSE_MODE = "exact_pose"


@dataclass(frozen=True, slots=True)
class AlignmentCorrespondence:
    correspondence_id: str
    source_x_m: float
    source_y_m: float
    source_yaw_rad: float
    carla_x_m: float
    carla_y_m: float
    carla_yaw_rad: float
    position_residual_m: float
    heading_residual_rad: float


@dataclass(frozen=True, slots=True)
class CarlaAlignmentArtifact:
    source_dataset: str
    source_dataset_version: str
    source_scene: str
    source_coordinate_frame: str
    canonical_coordinate_frame: str
    carla_world: str
    carla_release: str
    carla_server_version: str
    translation_x_m: float
    translation_y_m: float
    translation_z_m: float
    yaw_rad: float
    max_position_residual_m: float
    max_heading_residual_rad: float
    position_tolerance_m: float
    heading_tolerance_rad: float
    actor_origin_convention: str
    map_reconstruction_mode: str
    fidelity_claim: str
    correspondences: tuple[AlignmentCorrespondence, ...]
    artifact_version: str = CARLA_ALIGNMENT_VERSION


@dataclass(frozen=True, slots=True)
class BlueprintRule:
    source_category: str
    blueprint_id: str
    origin_convention: str
    origin_offset_x_m: float = 0.0
    origin_offset_y_m: float = 0.0
    origin_offset_z_m: float = 0.0
    blueprint_length_m: float = 0.0
    blueprint_width_m: float = 0.0
    blueprint_height_m: float = 0.0


@dataclass(frozen=True, slots=True)
class BlueprintMapping:
    entity_name: str
    source_category: str
    blueprint_id: str
    origin_convention: str
    source_dimensions: tuple[float, float, float] | None
    blueprint_dimensions: tuple[float, float, float] | None


@dataclass(frozen=True, slots=True)
class ReplayGrid:
    timestep_s: float
    times_s: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ExactPoseCommand:
    actor_id: str
    blueprint_id: str
    source_time_s: float
    x_m: float
    y_m: float
    z_m: float
    yaw_rad: float
    physics_enabled: bool = False


@dataclass(frozen=True, slots=True)
class ExactPoseBatch:
    tick_index: int
    source_time_s: float
    commands: tuple[ExactPoseCommand, ...]
    do_tick: bool = False


@dataclass(frozen=True, slots=True)
class ExactPosePlan:
    replay_mode: str
    xosc_path: str
    xodr_path: str
    execution_identity: XoscExecutionIdentity
    alignment: CarlaAlignmentArtifact
    blueprint_mappings: tuple[BlueprintMapping, ...]
    grid: ReplayGrid


class ExactPoseRuntime(Protocol):
    def configure(self, timestep_s: float) -> None: ...
    def spawn(self, mappings: tuple[BlueprintMapping, ...]) -> None: ...
    def apply_batch_sync(self, batch: ExactPoseBatch) -> None: ...
    def tick(self) -> int: ...
    def cleanup(self) -> None: ...


def require_execution_identity(plan: ExactPosePlan) -> None:
    current = build_execution_identity(plan.xosc_path, plan.xodr_path)
    if current.xosc_sha256 != plan.execution_identity.xosc_sha256:
        raise ValueError("xosc_hash_mismatch")
    if current.xodr_sha256 != plan.execution_identity.xodr_sha256:
        raise ValueError("xodr_hash_mismatch")


def validate_alignment(artifact: CarlaAlignmentArtifact) -> None:
    if artifact.artifact_version != CARLA_ALIGNMENT_VERSION:
        raise ValueError("alignment_version_unsupported")
    if artifact.source_coordinate_frame != "local_road_aligned":
        raise ValueError("alignment_frame_unsupported")
    if not artifact.source_dataset or not artifact.source_scene or not artifact.carla_world:
        raise ValueError("alignment_invalid_identity")
    if not artifact.correspondences:
        raise ValueError("alignment_missing_correspondence")
    numeric = (artifact.translation_x_m, artifact.translation_y_m, artifact.translation_z_m, artifact.yaw_rad,
               artifact.max_position_residual_m, artifact.max_heading_residual_rad,
               artifact.position_tolerance_m, artifact.heading_tolerance_rad)
    if not all(isfinite(value) for value in numeric) or artifact.position_tolerance_m < 0 or artifact.heading_tolerance_rad < 0:
        raise ValueError("alignment_invalid")
    if artifact.max_position_residual_m > artifact.position_tolerance_m or artifact.max_heading_residual_rad > artifact.heading_tolerance_rad:
        raise ValueError("alignment_residual_exceeded")
    if not artifact.actor_origin_convention or not artifact.map_reconstruction_mode or not artifact.fidelity_claim:
        raise ValueError("alignment_invalid_policy")


def alignment_to_dict(artifact: CarlaAlignmentArtifact) -> dict[str, object]:
    validate_alignment(artifact)
    return {"artifact_version": artifact.artifact_version, "source_dataset": artifact.source_dataset,
            "source_dataset_version": artifact.source_dataset_version, "source_scene": artifact.source_scene,
            "source_coordinate_frame": artifact.source_coordinate_frame, "canonical_coordinate_frame": artifact.canonical_coordinate_frame,
            "carla_world": artifact.carla_world, "carla_release": artifact.carla_release, "carla_server_version": artifact.carla_server_version,
            "translation_x_m": artifact.translation_x_m, "translation_y_m": artifact.translation_y_m, "translation_z_m": artifact.translation_z_m,
            "yaw_rad": artifact.yaw_rad, "max_position_residual_m": artifact.max_position_residual_m,
            "max_heading_residual_rad": artifact.max_heading_residual_rad, "position_tolerance_m": artifact.position_tolerance_m,
            "heading_tolerance_rad": artifact.heading_tolerance_rad, "actor_origin_convention": artifact.actor_origin_convention,
            "map_reconstruction_mode": artifact.map_reconstruction_mode, "fidelity_claim": artifact.fidelity_claim,
            "correspondences": [asdict(item) for item in artifact.correspondences]}


def serialize_alignment(artifact: CarlaAlignmentArtifact) -> str:
    return json.dumps(alignment_to_dict(artifact), sort_keys=True, separators=(",", ":"), allow_nan=False)


def interpret_for_execution(xosc_path: str | Path, xodr_path: str | Path | None) -> tuple[ValidatedXoscScenario, XoscInterpretation]:
    """Return the validated subset scenario together with its strict interpretation.

    CP2-A plans are built from the interpreted file so the alignment artifact, the
    blueprint mapping and the exact-pose batches all reference the same resolved
    start times, trigger conditions and execution identity.
    """
    interpretation = interpret_xosc_subset(xosc_path, xodr_path)
    scenario = ValidatedXoscScenario(
        source_path=interpretation.source_path,
        map_reference=interpretation.map_reference,
        entity_names=tuple(entity.name for entity in interpretation.entities),
        initial_positions={entity.name: entity.initial_position for entity in interpretation.entities},
        trajectories={entity.name: entity.trajectory for entity in interpretation.entities},
    )
    return scenario, interpretation


def map_blueprints(scenario: ValidatedXoscScenario, registry: Mapping[str, BlueprintRule]) -> tuple[BlueprintMapping, ...]:
    mappings = []
    for entity in scenario.entity_names:
        spec = scenario.entity_specs.get(entity) if hasattr(scenario, "entity_specs") else None
        category = "car" if spec is None else spec.vehicle_category
        rule = registry.get(category)
        if rule is None:
            raise ValueError("blueprint_unmapped")
        dimensions = None if spec is None else (spec.length_m, spec.width_m, spec.height_m)
        target = None if rule.blueprint_length_m <= 0 else (rule.blueprint_length_m, rule.blueprint_width_m, rule.blueprint_height_m)
        mappings.append(BlueprintMapping(entity, category, rule.blueprint_id, rule.origin_convention, dimensions, target))
    return tuple(mappings)


def build_replay_grid(duration_s: float, timestep_s: float) -> ReplayGrid:
    if not isfinite(duration_s) or duration_s < 0 or not isfinite(timestep_s) or timestep_s <= 0:
        raise ValueError("replay_grid_invalid_timing")
    count = int(duration_s // timestep_s)
    times = [round(index * timestep_s, 12) for index in range(count + 1)]
    if not times or times[-1] < duration_s:
        times.append(duration_s)
    elif times[-1] > duration_s:
        times[-1] = duration_s
    return ReplayGrid(timestep_s, tuple(times))


def build_exact_pose_plan(
    xosc_path: str | Path,
    xodr_path: str | Path,
    scenario: ValidatedXoscScenario,
    alignment: CarlaAlignmentArtifact,
    blueprint_mappings: tuple[BlueprintMapping, ...],
    *,
    timestep_s: float,
) -> ExactPosePlan:
    if not Path(xodr_path).is_file():
        raise ValueError("map_asset_missing")
    validate_alignment(alignment)
    identity = build_execution_identity(xosc_path, xodr_path)
    if not scenario.trajectories:
        raise ValueError("xosc_trajectory_missing")
    duration = max((trajectory[-1][0] for trajectory in scenario.trajectories.values()), default=0.0)
    grid = build_replay_grid(duration, timestep_s)
    names = {mapping.entity_name for mapping in blueprint_mappings}
    if names != set(scenario.entity_names):
        raise ValueError("blueprint_mapping_incomplete")
    return ExactPosePlan(EXACT_POSE_MODE, str(xosc_path), str(xodr_path), identity, alignment, blueprint_mappings, grid)


def interpolate_trajectory(trajectory, time_s: float) -> tuple[float, float, float, float, float]:
    if time_s < trajectory[0][0] or time_s > trajectory[-1][0]:
        raise ValueError("replay_time_outside_source_trajectory")
    for left, right in zip(trajectory, trajectory[1:]):
        if time_s <= right[0]:
            if right[0] == left[0]:
                return left
            fraction = (time_s - left[0]) / (right[0] - left[0])
            yaw_delta = _wrap_angle(right[3] - left[3])
            return (time_s, left[1] + fraction * (right[1] - left[1]), left[2] + fraction * (right[2] - left[2]),
                    _wrap_angle(left[3] + fraction * yaw_delta), left[4] + fraction * (right[4] - left[4]))
    return trajectory[-1]


def build_exact_pose_batches(plan: ExactPosePlan, scenario: ValidatedXoscScenario) -> tuple[ExactPoseBatch, ...]:
    ordered = tuple(mapping.entity_name for mapping in plan.blueprint_mappings)
    mappings = {mapping.entity_name: mapping for mapping in plan.blueprint_mappings}
    batches = []
    for tick_index, time_s in enumerate(plan.grid.times_s):
        commands = []
        for entity in ordered:
            state = interpolate_trajectory(scenario.trajectories[entity], time_s)
            commands.append(ExactPoseCommand(entity, mappings[entity].blueprint_id, state[0], state[1], state[2], state[4], state[3], False))
        batches.append(ExactPoseBatch(tick_index, time_s, tuple(commands)))
    return tuple(batches)


def execute_exact_pose(runtime: ExactPoseRuntime, plan: ExactPosePlan, scenario: ValidatedXoscScenario) -> tuple[int, ...]:
    require_execution_identity(plan)
    runtime.configure(plan.grid.timestep_s)
    runtime.spawn(plan.blueprint_mappings)
    frames = []
    try:
        for batch in build_exact_pose_batches(plan, scenario):
            runtime.apply_batch_sync(batch)
            frames.append(runtime.tick())
    finally:
        runtime.cleanup()
    return tuple(frames)


def _wrap_angle(angle: float) -> float:
    return atan2(sin(angle), cos(angle))
