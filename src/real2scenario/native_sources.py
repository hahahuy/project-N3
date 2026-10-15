"""Read-only nuScenes capability contracts that keep private payloads local."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


NATIVE_MAP_VERSION = "nuscenes-native-map-query-v1"
LIDAR_CONTRACT_VERSION = "nuscenes-lidar-payload-v1"
PREDICTION_EVAL_VERSION = "nuscenes-prediction-advisory-v1"
MAP_LAYERS = ("road_segment", "road_block", "stop_line", "traffic_light", "ped_crossing", "walkway", "lane_divider", "road_divider", "drivable_area")


def native_map_records(map_api: Any, layer: str) -> tuple[Mapping[str, Any], ...]:
    """Return sorted copies of a supported devkit layer; never mutate the API."""
    if layer not in MAP_LAYERS:
        raise ValueError(f"Unsupported native map layer: {layer}")
    records = getattr(map_api, layer, None)
    if not isinstance(records, list):
        raise ValueError(f"Native map layer is unavailable: {layer}")
    return tuple(dict(record) for record in sorted(records, key=lambda item: str(item.get("token", ""))))


def road_ahead_query(map_api: Any, x_m: float, y_m: float) -> dict[str, object]:
    """Expose devkit lookahead as diagnostic oracle data with provenance."""
    if not hasattr(map_api, "get_next_roads"):
        return {"version": NATIVE_MAP_VERSION, "status": "unavailable", "reason": "devkit_query_missing", "records": []}
    records = map_api.get_next_roads(x_m, y_m) or []
    return {"version": NATIVE_MAP_VERSION, "status": "available", "records": list(records), "artifact_visibility": "local_private"}


def native_map_patch(
    map_api: Any,
    patch: tuple[float, float, float, float],
    layers: Sequence[str] = MAP_LAYERS,
) -> dict[str, object]:
    """Return read-only native record tokens intersecting an XY patch."""
    if len(patch) != 4 or patch[0] >= patch[2] or patch[1] >= patch[3]:
        raise ValueError("patch must be (x_min, y_min, x_max, y_max) with positive area.")
    unknown = sorted(set(layers) - set(MAP_LAYERS))
    if unknown:
        raise ValueError(f"Unsupported native map layer: {unknown[0]}")
    if not hasattr(map_api, "get_records_in_patch"):
        return {"version": NATIVE_MAP_VERSION, "status": "unavailable", "reason": "devkit_query_missing", "patch": list(patch), "layers": {}}
    selected = map_api.get_records_in_patch(list(patch), list(layers)) or {}
    return {
        "version": NATIVE_MAP_VERSION,
        "status": "available",
        "patch": list(patch),
        "layers": {layer: sorted(list(selected.get(layer, []))) for layer in layers},
        "artifact_visibility": "local_private",
    }


@dataclass(frozen=True, slots=True)
class LidarPayloadContract:
    version: str
    channel: str
    timestamp_us: int
    source_file: str
    frame: str
    calibration_token: str
    decimation: int
    artifact_visibility: str = "local_private"

    def __post_init__(self) -> None:
        if self.version != LIDAR_CONTRACT_VERSION or self.channel != "LIDAR_TOP" or self.decimation < 1:
            raise ValueError("Invalid private LiDAR payload contract.")
        if self.artifact_visibility != "local_private":
            raise ValueError("LiDAR payloads must remain local_private.")


def lidar_payload_contract(sample_data: Mapping[str, Any], calibration: Mapping[str, Any], *, decimation: int = 8) -> LidarPayloadContract:
    """Describe a decimated payload without loading or returning point-cloud bytes."""
    return LidarPayloadContract(LIDAR_CONTRACT_VERSION, "LIDAR_TOP", int(sample_data["timestamp"]), str(sample_data["filename"]), "ego_vehicle", str(calibration["token"]), decimation)


def evaluate_prediction_advisory(predicted: Sequence[Sequence[tuple[float, float]]], actual: Sequence[tuple[float, float]]) -> dict[str, object]:
    """Compute minADE/minFDE as a separate, non-replay advisory result."""
    if not predicted or not actual or any(len(path) != len(actual) for path in predicted):
        raise ValueError("Prediction and reference horizons must be non-empty and equal.")
    errors = [sum(((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5 for p, a in zip(path, actual)) / len(actual) for path in predicted]
    fde = [((path[-1][0] - actual[-1][0]) ** 2 + (path[-1][1] - actual[-1][1]) ** 2) ** 0.5 for path in predicted]
    return {"evaluation_version": PREDICTION_EVAL_VERSION, "metric_role": "advisory_prediction_only", "min_ade_m": min(errors), "min_fde_m": min(fde), "scientific_status": "PROVISIONAL"}
