"""Cached, local-private nuScenes devkit access for browser evidence."""

from __future__ import annotations

import bisect
import threading
from pathlib import Path
from typing import Any

import numpy as np


class NuScenesDatasetAdapter:
    """Own official nuScenes semantics while keeping request payloads JSON-safe."""

    _cache: dict[tuple[str, str], "NuScenesDatasetAdapter"] = {}
    _cache_lock = threading.RLock()

    @classmethod
    def for_dataset(cls, root: str | Path, version: str) -> "NuScenesDatasetAdapter":
        key = (str(Path(root).expanduser().resolve()), version)
        with cls._cache_lock:
            if key not in cls._cache:
                cls._cache[key] = cls(Path(key[0]), version)
            return cls._cache[key]

    def __init__(self, root: Path, version: str) -> None:
        self.root = root
        self.version = version
        self._nusc: Any | None = None
        self._maps: dict[str, Any] = {}
        self._explorer: Any | None = None
        self._can: Any | None = None
        self._can_messages: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {}

    @property
    def nusc(self) -> Any:
        if self._nusc is None:
            try:
                from nuscenes.nuscenes import NuScenes
            except ImportError as error:
                raise RuntimeError("nuscenes_devkit_not_installed") from error
            self._nusc = NuScenes(version=self.version, dataroot=str(self.root), verbose=False)
        return self._nusc

    @property
    def explorer(self) -> Any:
        """Expose the official projection/render semantics lazily for future camera evidence."""
        if self._explorer is None:
            try:
                from nuscenes.nuscenes import NuScenesExplorer
            except ImportError as error:
                raise RuntimeError("nuscenes_devkit_not_installed") from error
            self._explorer = NuScenesExplorer(self.nusc)
        return self._explorer

    def sample_data(self, token: str) -> dict[str, Any]:
        record = self.nusc.get("sample_data", token)
        if record.get("channel") not in (None, "LIDAR_TOP"):
            raise ValueError("sample_data calibration is not LIDAR_TOP")
        calibrated = self.nusc.get("calibrated_sensor", record["calibrated_sensor_token"])
        sensor = self.nusc.get("sensor", calibrated["sensor_token"])
        if sensor.get("channel") != "LIDAR_TOP":
            raise ValueError("sample_data calibration is not LIDAR_TOP")
        return record

    def records(self, token: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
        sample_data = self.sample_data(token)
        calibration = self.nusc.get("calibrated_sensor", sample_data["calibrated_sensor_token"])
        ego_pose = self.nusc.get("ego_pose", sample_data["ego_pose_token"])
        path = (self.root / sample_data["filename"]).resolve()
        if self.root not in path.parents or not path.is_file():
            raise FileNotFoundError("LIDAR source file is unavailable")
        return sample_data, calibration, ego_pose, path

    def sweep_records(self, token: str, limit: int) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]]:
        result = []
        current = token
        for _ in range(limit):
            record = self.records(current)
            result.append(record)
            current = str(record[0].get("prev") or "")
            if not current:
                break
        return result

    def multisweep(self, token: str, nsweeps: int) -> tuple[Any, np.ndarray]:
        sample_data, _, _, _ = self.records(token)
        sample = self.nusc.get("sample", sample_data["sample_token"])
        try:
            from nuscenes.utils.data_classes import LidarPointCloud
        except ImportError as error:
            raise RuntimeError("nuscenes_devkit_not_installed") from error
        return LidarPointCloud.from_file_multisweep(
            self.nusc, sample, "LIDAR_TOP", "LIDAR_TOP", nsweeps=nsweeps
        )

    def transform(self, calibration: dict[str, Any], ego_pose: dict[str, Any]) -> dict[str, Any]:
        try:
            from nuscenes.utils.geometry_utils import transform_matrix
            from pyquaternion import Quaternion
        except ImportError as error:
            raise RuntimeError("nuscenes_devkit_not_installed") from error
        sensor_to_ego = transform_matrix(calibration["translation"], Quaternion(calibration["rotation"]))
        ego_to_global = transform_matrix(ego_pose["translation"], Quaternion(ego_pose["rotation"]))
        composed = np.asarray(ego_to_global) @ np.asarray(sensor_to_ego)
        return {
            "source_frame": "lidar_sensor",
            "target_frame": "nuscenes_global",
            "matrix_4x4": composed.astype(float).tolist(),
            "calibrated_sensor_token": calibration["token"],
            "ego_pose_token": ego_pose["token"],
            "composition": ["sensor_to_ego", "ego_to_global"],
            "transform_version": "nuscenes-devkit-transform-v1",
            "translation_m": [float(x) for x in calibration["translation"]],
            "rotation_wxyz": [float(x) for x in calibration["rotation"]],
        }

    def annotations(self, sample_data_token: str) -> dict[str, Any]:
        self.nusc.get_sample_data(sample_data_token)
        boxes = self.nusc.get_boxes(sample_data_token)
        output = []
        for box in boxes:
            output.append({
                "token": box.token,
                "instance_token": box.instance_token,
                "category_name": box.name,
                "translation_m": [float(x) for x in box.center],
                "size_m": [float(x) for x in box.wlh],
                "rotation_wxyz": [float(x) for x in box.orientation.elements],
                "coordinate_frame": "nuscenes_global",
            })
        return {"available": True, "source": "NuScenes.get_sample_data/get_boxes/Box", "boxes": output, "provenance": {"annotation_semantics": "nuscenes-devkit-box-v1"}}

    def multisweep_provenance(self, token: str, nsweeps: int) -> dict[str, str]:
        """Exercise the devkit's canonical history traversal for this evidence request."""
        cloud, _ = self.multisweep(token, nsweeps)
        return {
            "multisweep_api": "LidarPointCloud.from_file_multisweep",
            "multisweep_point_count": str(int(cloud.points.shape[1])),
            "projection_semantics": "NuScenesExplorer",
        }

    def map_underlay(self, sample_data_token: str) -> dict[str, Any]:
        sample_data, _, ego_pose, _ = self.records(sample_data_token)
        scene = self.nusc.get("scene", self.nusc.get("sample", sample_data["sample_token"])["scene_token"])
        map_name = scene.get("log_token")
        log = self.nusc.get("log", map_name) if map_name else {}
        map_name = log.get("location")
        if not map_name:
            return {"available": False, "source": "NuScenesMap", "unavailable_reason": "map_name_unavailable", "provenance": {}}
        try:
            from nuscenes.map_expansion.map_api import NuScenesMap
            api = self._maps.get(map_name)
            if api is None:
                api = NuScenesMap(dataroot=str(self.root), map_name=map_name)
                self._maps[map_name] = api
            x, y = ego_pose["translation"][:2]
            patch = (float(x - 50), float(y - 50), float(x + 50), float(y + 50))
            layers = ["road_segment", "road_block", "lane", "ped_crossing", "walkway", "drivable_area", "lane_divider", "road_divider", "stop_line", "traffic_light"]
            selected = api.get_records_in_patch(list(patch), layers) or {}
            return {"available": True, "source": "NuScenesMap", "map_name": map_name, "patch": list(patch), "layers": {name: list(selected.get(name, [])) for name in layers}, "provenance": {"map_api": "nuscenes-devkit-NuScenesMap-v1", "reference_sample_data_token": sample_data["token"]}, "artifact_visibility": "local_private"}
        except (ImportError, OSError, RuntimeError, ValueError, KeyError) as error:
            return {"available": False, "source": "NuScenesMap", "unavailable_reason": f"map_unavailable:{type(error).__name__}", "provenance": {}}

    def can_alignment(self, sample_data_token: str) -> dict[str, Any]:
        sample_data, _, _, _ = self.records(sample_data_token)
        scene = self.nusc.get("scene", self.nusc.get("sample", sample_data["sample_token"])["scene_token"])
        try:
            from nuscenes.can_bus.can_bus_api import NuScenesCanBus
            if self._can is None:
                self._can = NuScenesCanBus(dataroot=str(self.root), max_misalignment=5.0)
            scene_name = scene["name"]
            key = (scene_name, "pose")
            if key not in self._can_messages:
                self._can_messages[key] = tuple(self._can.get_messages(scene_name, "pose", print_warnings=False))
            messages = self._can_messages[key]
            if not messages:
                raise ValueError("can_messages_unavailable")
            timestamps = [int(message["utime"]) for message in messages if isinstance(message.get("utime"), (int, float))]
            if not timestamps:
                raise ValueError("can_timestamps_unavailable")
            index = bisect.bisect_left(timestamps, int(sample_data["timestamp"]))
            candidates = [timestamps[max(0, min(index + offset, len(timestamps) - 1))] for offset in (-1, 0)]
            aligned = min(candidates, key=lambda value: abs(value - int(sample_data["timestamp"])))
            return {"available": True, "source": "NuScenesCanBus", "reference_timestamp_us": int(sample_data["timestamp"]), "aligned_timestamp_us": aligned, "alignment_delta_us": abs(aligned - int(sample_data["timestamp"])), "provenance": {"can_semantics": "NuScenesCanBus.timestamp-nearest-v1"}}
        except (ImportError, OSError, RuntimeError, ValueError, KeyError, AssertionError):
            return {"available": False, "source": "NuScenesCanBus", "unavailable_reason": "can_bus_unavailable", "provenance": {}}
