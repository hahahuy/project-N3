"""Read nuScenes metadata into simulator-independent canonical scenarios."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import atan2, hypot
from pathlib import Path
from typing import Any

from .models import Actor, Scenario, State
from .nuscenes_backend import NuScenesSourceAdapter, nearest_can_poses


# Recording-vehicle dimensions (nuScenes ego is a Renault Zoe; the ego has no
# sample_annotation, so these documented manufacturer specs stand in for the
# missing measurement — previously the generic 4.5 x 1.8 x 1.5 fallbacks
# applied). Width is body-only, mirrors excluded (1.945 m with mirrors),
# per standard bounding-box convention. Owner-confirmed 2026-10-17.
EGO_LENGTH_M = 4.084
EGO_WIDTH_M = 1.730
EGO_HEIGHT_M = 1.562
EGO_DIMENSIONS_SOURCE = "renault-zoe-manufacturer-specs-mirrors-excluded"


@dataclass(frozen=True, slots=True)
class SourceWindow:
    """An inclusive, ordered keyframe range from one nuScenes scene."""

    scene_token: str
    start_sample_token: str
    end_sample_token: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("scene_token", self.scene_token),
            ("start_sample_token", self.start_sample_token),
            ("end_sample_token", self.end_sample_token),
        ):
            if not value:
                raise ValueError(f"SourceWindow {field_name} must not be empty.")


def extract_scenario(
    dataset_root: str | Path,
    window: SourceWindow,
    actor_instance_tokens: Sequence[str],
    *,
    version: str = "v1.0-mini",
    tables: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    use_devkit_sources: bool = True,
) -> Scenario:
    """Extract global-frame ego and explicitly selected actor trajectories.

    The window endpoints are inclusive keyframes from the requested scene.
    ``actor_instance_tokens`` intentionally selects tracked actors explicitly;
    interaction ranking and automatic selection belong to R2S-103. Positions
    remain in nuScenes global coordinates. R2S-201 converts them to the local
    road-aligned frame used by simulation.

    ``tables`` optionally supplies already loaded or cached metadata records for
    the same dataset version. It must contain every table required below and must
    be a subset of the requested window's scenes; it exists so repeated scene
    preparation does not rescan the source tables. Supplying tables never changes
    the canonical result.
    """
    if not version:
        raise ValueError("version must not be empty.")
    if not actor_instance_tokens:
        raise ValueError("actor_instance_tokens must contain at least one instance token.")
    if len(actor_instance_tokens) != len(set(actor_instance_tokens)):
        raise ValueError("actor_instance_tokens must be unique.")

    root = Path(dataset_root).expanduser()
    tables = _validated_tables(root, version, tables)
    scenes = _index_by_token(tables["scene"], "scene")
    samples = _index_by_token(tables["sample"], "sample")
    instances = _index_by_token(tables["instance"], "instance")
    poses = _index_by_token(tables["ego_pose"], "ego_pose")
    calibrations = _index_by_token(tables["calibrated_sensor"], "calibrated_sensor")
    sensors = _index_by_token(tables["sensor"], "sensor")
    categories = _index_by_token(tables["category"], "category")

    scene = _required_record(scenes, window.scene_token, "scene")
    sample_window = _resolve_sample_window(samples, scene, window)
    timestamps_s = [_timestamp_s(sample) for sample in sample_window]
    if timestamps_s[-1] <= timestamps_s[0]:
        raise ValueError("Source window must contain at least two distinct timestamps.")

    lidar_by_sample = _lidar_keyframes_by_sample(
        tables["sample_data"], calibrations, sensors
    )
    ego_positions: list[tuple[float, float]] = []
    ego_yaws: list[float] = []
    ego_tokens: list[str] = []
    for sample in sample_window:
        sample_token = _required_string(sample, "token", "sample")
        lidar = _required_record(lidar_by_sample, sample_token, "LIDAR_TOP sample_data")
        pose = _required_record(
            poses,
            _required_string(lidar, "ego_pose_token", "LIDAR_TOP sample_data"),
            "ego_pose",
        )
        ego_positions.append(_translation_xy(pose, "ego_pose"))
        ego_yaws.append(_yaw_from_record(pose, "ego_pose"))
        ego_tokens.append(_required_string(lidar, "ego_pose_token", "LIDAR_TOP sample_data"))

    can_samples = ()
    source_adapter = NuScenesSourceAdapter(root)
    scene_name = _required_string(scene, "name", "scene") if scene.get("name") else window.scene_token
    if use_devkit_sources:
        can_samples = source_adapter.can_pose(scene_name)
    can_matches = nearest_can_poses(
        [round(timestamp_s * 1_000_000) for timestamp_s in timestamps_s], can_samples
    )
    matched_can = any(match is not None and match.speed_mps is not None for match in can_matches)

    actors = [
        _build_actor(
            instance_token,
            sample_window,
            timestamps_s,
            tables["sample_annotation"],
            instances,
            categories,
            timestamps_s[0],
        )
        for instance_token in actor_instance_tokens
    ]
    ego = Actor(
        actor_id="ego",
        actor_type="vehicle.ego",
        trajectory=_states_from_positions(
            timestamps_s,
            ego_positions,
            ego_yaws,
            origin_time_s=timestamps_s[0],
            source_tokens=ego_tokens,
            measured_speeds=[match.speed_mps if match is not None else None for match in can_matches]
            if can_matches
            else None,
        ),
        length_m=EGO_LENGTH_M,
        width_m=EGO_WIDTH_M,
        height_m=EGO_HEIGHT_M,
    )
    duration_s = timestamps_s[-1] - timestamps_s[0]
    return Scenario(
        scenario_id=(
            f"nuscenes-{window.scene_token}-{window.start_sample_token}-{window.end_sample_token}"
        ),
        duration_s=duration_s,
        ego_actor_id=ego.actor_id,
        actors=(ego, *actors),
        coordinate_frame="nuscenes_global",
        provenance={
            "dataset_name": "nuScenes",
            "dataset_version": version,
            "source_scene_token": window.scene_token,
            "source_window": f"{window.start_sample_token}:{window.end_sample_token}",
            "coordinate_transform_version": "source-global-v1",
            "map_reconstruction_mode": "not-applicable-source-global",
            "map_reconstruction_version": "not-applicable",
            "generator_version": "real2scenario-ingestion-v1",
            "ego_dimensions_m": f"{EGO_LENGTH_M}x{EGO_WIDTH_M}x{EGO_HEIGHT_M}",
            "ego_dimensions_source": EGO_DIMENSIONS_SOURCE,
            "selected_instance_tokens": ",".join(actor_instance_tokens),
            **source_adapter.provenance(
                scene_name=scene_name, used=matched_can, sample_count=len(can_samples)
            ),
        },
    )


def source_reference_convention() -> dict[str, str]:
    """Return the immutable nuScenes reference-point convention used at CP1."""
    return {
        "trajectory_position": "sample_annotation.translation_xy",
        "annotation_box_origin": "3D bounding-box center translation",
        "annotation_heading": "sample_annotation.rotation yaw",
        "lane_reference": "map discretized centerline pose",
        "footprint_origin": "annotation box center when dimensions are available",
        "correction": "none",
        "version": "source-reference-convention-v1",
    }


_REQUIRED_TABLES = (
    "scene",
    "sample",
    "sample_data",
    "sample_annotation",
    "instance",
    "ego_pose",
    "calibrated_sensor",
    "sensor",
    "category",
)


def _validated_tables(
    root: Path,
    version: str,
    tables: Mapping[str, Sequence[Mapping[str, Any]]] | None,
) -> Mapping[str, Sequence[Mapping[str, Any]]]:
    if tables is not None:
        missing = [name for name in _REQUIRED_TABLES if name not in tables]
        if missing:
            raise ValueError(f"Supplied tables are missing {', '.join(missing)}.")
        return tables
    return _load_tables(root, version, _REQUIRED_TABLES)


def _load_tables(
    dataset_root: Path, version: str, names: Iterable[str]
) -> dict[str, list[dict[str, Any]]]:
    metadata_path = dataset_root / version
    tables: dict[str, list[dict[str, Any]]] = {}
    for name in names:
        path = metadata_path / f"{name}.json"
        try:
            with path.open(encoding="utf-8") as file:
                value = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Unable to load required {name}.json at {path}: {error}.") from error
        if not isinstance(value, list) or not all(isinstance(record, dict) for record in value):
            raise ValueError(f"Required {name}.json at {path} must contain a JSON array of objects.")
        tables[name] = value
    return tables


def _index_by_token(records: Iterable[Mapping[str, Any]], name: str) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for record in records:
        token = _required_string(record, "token", name)
        if token in index:
            raise ValueError(f"{name} contains duplicate token {token!r}.")
        index[token] = record
    return index


def _resolve_sample_window(
    samples: Mapping[str, Mapping[str, Any]], scene: Mapping[str, Any], window: SourceWindow
) -> list[Mapping[str, Any]]:
    first_token = _required_string(scene, "first_sample_token", "scene")
    current_token = first_token
    records: list[Mapping[str, Any]] = []
    found_start = False
    while current_token:
        sample = _required_record(samples, current_token, "sample")
        if _required_string(sample, "scene_token", "sample") != window.scene_token:
            raise ValueError("Sample chain leaves the requested scene.")
        if current_token == window.start_sample_token:
            found_start = True
        if found_start:
            records.append(sample)
        if found_start and current_token == window.end_sample_token:
            return records
        current_token = _optional_string(sample.get("next"), "sample.next")

    if not found_start:
        raise ValueError("Source window start_sample_token is not in the requested scene.")
    raise ValueError("Source window end_sample_token does not follow start_sample_token in the scene.")


def _lidar_keyframes_by_sample(
    sample_data: Iterable[Mapping[str, Any]],
    calibrations: Mapping[str, Mapping[str, Any]],
    sensors: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    lidar_by_sample: dict[str, Mapping[str, Any]] = {}
    for record in sample_data:
        if not record.get("is_key_frame"):
            continue
        calibration = _required_record(
            calibrations,
            _required_string(record, "calibrated_sensor_token", "sample_data"),
            "calibrated_sensor",
        )
        sensor = _required_record(
            sensors,
            _required_string(calibration, "sensor_token", "calibrated_sensor"),
            "sensor",
        )
        if sensor.get("channel") != "LIDAR_TOP":
            continue
        sample_token = _required_string(record, "sample_token", "sample_data")
        if sample_token in lidar_by_sample:
            raise ValueError(f"Multiple LIDAR_TOP keyframes exist for sample {sample_token!r}.")
        lidar_by_sample[sample_token] = record
    return lidar_by_sample


def _build_actor(
    instance_token: str,
    samples: Sequence[Mapping[str, Any]],
    timestamps_s: Sequence[float],
    annotations: Sequence[Mapping[str, Any]],
    instances: Mapping[str, Mapping[str, Any]],
    categories: Mapping[str, Mapping[str, Any]],
    origin_time_s: float,
) -> Actor:
    instance = _required_record(instances, instance_token, "instance")
    category = _required_record(
        categories,
        _required_string(instance, "category_token", "instance"),
        "category",
    )
    annotation_index = {
        (_required_string(annotation, "sample_token", "sample_annotation"),
         _required_string(annotation, "instance_token", "sample_annotation")): annotation
        for annotation in annotations
    }
    positions: list[tuple[float, float]] = []
    yaws: list[float] = []
    actor_timestamps: list[float] = []
    actor_tokens: list[str] = []
    dimensions: tuple[float, float, float] | None = None
    for sample, timestamp_s in zip(samples, timestamps_s):
        annotation = annotation_index.get((_required_string(sample, "token", "sample"), instance_token))
        if annotation is None:
            continue
        positions.append(_translation_xy(annotation, "sample_annotation"))
        yaws.append(_yaw_from_record(annotation, "sample_annotation"))
        actor_timestamps.append(timestamp_s)
        actor_tokens.append(_required_string(annotation, "token", "sample_annotation"))
        size = _size(annotation)
        if dimensions is None:
            dimensions = size
        elif dimensions != size:
            raise ValueError(
                f"Instance {instance_token!r} changes dimensions within the source window."
            )

    if not positions:
        raise ValueError(f"Instance {instance_token!r} has no annotations in the source window.")
    states = _states_from_positions(
        actor_timestamps,
        positions,
        yaws,
        origin_time_s=origin_time_s,
        source_tokens=actor_tokens,
    )
    length_m, width_m, height_m = dimensions or (None, None, None)
    return Actor(
        actor_id=f"instance-{instance_token}",
        actor_type=_required_string(category, "name", "category"),
        trajectory=states,
        length_m=length_m,
        width_m=width_m,
        height_m=height_m,
    )


def _states_from_positions(
    timestamps_s: Sequence[float],
    positions: Sequence[tuple[float, float]],
    yaws: Sequence[float],
    *,
    origin_time_s: float | None = None,
    source_tokens: Sequence[str] | None = None,
    measured_speeds: Sequence[float | None] | None = None,
) -> tuple[State, ...]:
    if not (len(timestamps_s) == len(positions) == len(yaws)):
        raise ValueError("Trajectory timestamps, positions, and yaws must have equal length.")
    if not timestamps_s:
        raise ValueError("Trajectory must contain at least one state.")
    if source_tokens is not None and len(source_tokens) != len(timestamps_s):
        raise ValueError("Trajectory source tokens must match state count.")
    if measured_speeds is not None and len(measured_speeds) != len(timestamps_s):
        raise ValueError("Measured speeds must match trajectory state count.")
    start_time_s = timestamps_s[0] if origin_time_s is None else origin_time_s
    relative_times = [timestamp_s - start_time_s for timestamp_s in timestamps_s]
    speeds = _finite_difference_speeds(relative_times, positions)
    if measured_speeds is not None:
        speeds = [
            measured if measured is not None and measured >= 0 else fallback
            for measured, fallback in zip(measured_speeds, speeds)
        ]
    return tuple(
        State(
            time_s=time_s,
            x_m=position[0],
            y_m=position[1],
            yaw_rad=yaw,
            speed_mps=speed,
            source_timestamp_us=round(timestamp_s * 1_000_000),
            source_record_token=None if source_tokens is None else source_tokens[index],
        )
        for index, (time_s, timestamp_s, position, yaw, speed) in enumerate(
            zip(relative_times, timestamps_s, positions, yaws, speeds)
        )
    )


def _finite_difference_speeds(
    times_s: Sequence[float], positions: Sequence[tuple[float, float]]
) -> list[float]:
    if len(times_s) == 1:
        return [0.0]
    speeds: list[float] = []
    for index in range(len(times_s)):
        left = max(0, index - 1)
        right = min(len(times_s) - 1, index + 1)
        delta_time_s = times_s[right] - times_s[left]
        if delta_time_s <= 0:
            raise ValueError("Trajectory timestamps must strictly increase for speed estimation.")
        delta_x_m = positions[right][0] - positions[left][0]
        delta_y_m = positions[right][1] - positions[left][1]
        speeds.append(hypot(delta_x_m, delta_y_m) / delta_time_s)
    return speeds


def _timestamp_s(record: Mapping[str, Any]) -> float:
    timestamp = record.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise ValueError("sample.timestamp must be an integer number of microseconds.")
    return timestamp / 1_000_000.0


def _translation_xy(record: Mapping[str, Any], name: str) -> tuple[float, float]:
    translation = record.get("translation")
    if (
        not isinstance(translation, list)
        or len(translation) != 3
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in translation)
    ):
        raise ValueError(f"{name}.translation must contain three numeric coordinates.")
    return float(translation[0]), float(translation[1])


def _yaw_from_record(record: Mapping[str, Any], name: str) -> float:
    rotation = record.get("rotation")
    if (
        not isinstance(rotation, list)
        or len(rotation) != 4
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in rotation)
    ):
        raise ValueError(f"{name}.rotation must contain a numeric [w, x, y, z] quaternion.")
    w, x, y, z = (float(value) for value in rotation)
    return atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _size(record: Mapping[str, Any]) -> tuple[float, float, float]:
    size = record.get("size")
    if (
        not isinstance(size, list)
        or len(size) != 3
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in size)
    ):
        raise ValueError("sample_annotation.size must contain numeric [width, length, height].")
    width_m, length_m, height_m = (float(size[0]), float(size[1]), float(size[2]))
    return length_m, width_m, height_m


def _required_record(
    records: Mapping[str, Mapping[str, Any]], token: str, name: str
) -> Mapping[str, Any]:
    try:
        return records[token]
    except KeyError as error:
        raise ValueError(f"Required {name} record {token!r} is missing.") from error


def _required_string(record: Mapping[str, Any], field: str, name: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name}.{field} must be a non-empty string.")
    return value


def _optional_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    return value
