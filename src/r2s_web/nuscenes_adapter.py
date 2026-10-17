"""Cached, local-private nuScenes devkit access for browser evidence."""

from __future__ import annotations

import bisect
import tempfile
import threading
from pathlib import Path
from typing import Any

import numpy as np


# One nuScenes object per (dataroot, version) per process. Measured 2026-10-17:
# a single `NuScenes(v1.0-trainval)` load costs 7.74GB of resident memory. Three
# call sites each built their own, so the api process could hold ~23GB and the
# kernel OOM-killed the worker once dev's `--reload` churn added another copy.
# All three now share this cache.
_SHARED_NUSC: dict[tuple[str, str], Any] = {}
_SHARED_NUSC_LOCK = threading.RLock()


def shared_nuscenes(root: str | Path, version: str) -> Any:
    """Return the process-wide nuScenes object for one dataset.

    Read-only metadata lookups only. Callers must not mutate the returned
    object; the devkit exposes tables, and sharing them is the point.
    """
    resolved_root = str(Path(root).expanduser().resolve())
    key = (resolved_root, version)
    with _SHARED_NUSC_LOCK:
        instance = _SHARED_NUSC.get(key)
        if instance is None:
            try:
                from nuscenes.nuscenes import NuScenes
            except ImportError as error:
                raise RuntimeError("nuscenes_devkit_not_installed") from error
            instance = NuScenes(version=version, dataroot=resolved_root, verbose=False)
            _SHARED_NUSC[key] = instance
        return instance


def shared_nuscenes_cache_size() -> int:
    """Report how many devkit instances this process holds."""
    with _SHARED_NUSC_LOCK:
        return len(_SHARED_NUSC)


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
            self._nusc = shared_nuscenes(self.root, self.version)
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

    def lidar_sample_data_token(self, token: str) -> str:
        """Resolve a provenance window token to its LIDAR_TOP ``sample_data`` token.

        ``source_window`` stores sample tokens, while every sensor consumer needs the
        LIDAR_TOP ``sample_data`` token of the first sample in that window. A token that
        already addresses a recorded sweep is returned unchanged.
        """
        if not token:
            raise ValueError("recorded_lidar_sample_unavailable")
        try:
            return str(self.sample_data(token)["token"])
        except (KeyError, ValueError):
            pass
        sample = self.nusc.get("sample", token)
        lidar_token = str(sample.get("data", {}).get("LIDAR_TOP") or "")
        if not lidar_token:
            raise ValueError("recorded_lidar_sample_unavailable")
        self.sample_data(lidar_token)
        return lidar_token

    def camera_records(self, first_sample_token: str, last_sample_token: str, channel: str) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]]:
        """Return camera records across one source window, oldest first."""
        if not channel.startswith("CAM_"):
            raise ValueError("unsupported_camera_channel")
        records = []
        current_token = first_sample_token
        seen: set[str] = set()
        while current_token and current_token not in seen:
            seen.add(current_token)
            sample = self.nusc.get("sample", current_token)
            sample_data_token = str(sample.get("data", {}).get(channel) or "")
            if sample_data_token:
                sample_data = self.nusc.get("sample_data", sample_data_token)
                calibrated = self.nusc.get("calibrated_sensor", sample_data["calibrated_sensor_token"])
                sensor = self.nusc.get("sensor", calibrated["sensor_token"])
                if sensor.get("channel") != channel:
                    raise ValueError("camera_channel_calibration_mismatch")
                ego_pose = self.nusc.get("ego_pose", sample_data["ego_pose_token"])
                path = (self.root / sample_data["filename"]).resolve()
                if self.root not in path.parents or not path.is_file():
                    raise FileNotFoundError("camera source file is unavailable")
                sample_data = {**sample_data, "source_timestamp": int(sample.get("timestamp", sample_data["timestamp"]))}
                records.append((sample_data, calibrated, ego_pose, path))
            if current_token == last_sample_token:
                break
            current_token = str(sample.get("next") or "")
        return records

    def camera_annotations(self, sample_data_token: str) -> tuple[list[dict[str, Any]], list[list[float]]]:
        """Return recorded boxes and camera intrinsic using official devkit semantics."""
        sample_data = self.nusc.get("sample_data", sample_data_token)
        if not str(sample_data.get("channel", "")).startswith("CAM_"):
            raise ValueError("sample_data calibration is not a camera")
        _, boxes, intrinsic = self.nusc.get_sample_data(sample_data_token)
        from nuscenes.utils.geometry_utils import view_points
        return (
            [
                {
                    "token": box.token,
                    "category_name": box.name,
                    "corners_camera": box.corners().astype(float).tolist(),
                    "corners_2d": view_points(box.corners(), intrinsic, normalize=True)[:2].T.astype(float).tolist() if intrinsic is not None else [],
                    "size_m": [float(value) for value in box.wlh],
                    "visibility": "recorded_annotation",
                }
                for box in boxes
            ],
            intrinsic.astype(float).tolist() if intrinsic is not None else [],
        )

    def camera_file(self, sample_data_token: str) -> tuple[dict[str, Any], Path]:
        sample_data = self.nusc.get("sample_data", sample_data_token)
        if not str(sample_data.get("channel", "")).startswith("CAM_"):
            raise ValueError("sample_data calibration is not a camera")
        path = (self.root / sample_data["filename"]).resolve()
        if self.root not in path.parents or not path.is_file():
            raise FileNotFoundError("camera source file is unavailable")
        return sample_data, path

    def camera_lidar_projection(self, camera_sample_data_token: str) -> list[dict[str, float]]:
        """Project the matching keyframe LIDAR_TOP cloud with official devkit semantics."""
        camera = self.nusc.get("sample_data", camera_sample_data_token)
        sample = self.nusc.get("sample", camera["sample_token"])
        lidar_token = str(sample.get("data", {}).get("LIDAR_TOP") or "")
        if not lidar_token:
            raise ValueError("recorded_lidar_sample_unavailable")
        points, coloring, _ = self.explorer.map_pointcloud_to_image(lidar_token, camera_sample_data_token)
        return [
            {"u": float(points[0, index]), "v": float(points[1, index]), "depth_m": float(coloring[index])}
            for index in range(points.shape[1])
        ]

    def recorded_annotations_window(self, first_sample_token: str, last_sample_token: str, requested_time_s: float) -> dict[str, Any]:
        """Resolve one recorded sample and return all nuScenes annotation boxes."""
        tokens: list[str] = []
        timestamps: list[int] = []
        current = first_sample_token
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            sample = self.nusc.get("sample", current)
            tokens.append(current)
            timestamps.append(int(sample["timestamp"]))
            if current == last_sample_token:
                break
            current = str(sample.get("next") or "")
        if not tokens:
            raise ValueError("recorded_annotation_sample_unavailable")
        from .preview_time import resolve_preview_time
        resolution = resolve_preview_time(requested_time_s, timestamps, policy="nearest")
        sample = self.nusc.get("sample", tokens[resolution.index])
        lidar_token = str(sample.get("data", {}).get("LIDAR_TOP") or "")
        if not lidar_token:
            raise ValueError("recorded_annotation_lidar_unavailable")
        boxes = self.nusc.get_boxes(lidar_token)
        return {
            "requested_time_s": resolution.requested_time_s,
            "resolved_time_s": resolution.resolved_time_s,
            "timestamp_us": resolution.timestamp_us,
            "sample_token": tokens[resolution.index],
            "boxes": [
                {
                    "token": box.token,
                    "category_name": box.name,
                    "center_global": [float(value) for value in box.center],
                    "size_m": [float(value) for value in box.wlh],
                    "rotation_wxyz": [float(value) for value in box.orientation.elements],
                    "visibility": "recorded_annotation",
                }
                for box in boxes
            ],
        }

    def records(self, token: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
        sample_data = self.sample_data(token)
        calibration = self.nusc.get("calibrated_sensor", sample_data["calibrated_sensor_token"])
        ego_pose = self.nusc.get("ego_pose", sample_data["ego_pose_token"])
        path = (self.root / sample_data["filename"]).resolve()
        if self.root not in path.parents or not path.is_file():
            raise FileNotFoundError("LIDAR source file is unavailable")
        return sample_data, calibration, ego_pose, path

    def sweep_records(self, token: str, limit: int) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]]:
        """Walk recorded history exactly as the devkit multisweep walk does.

        LIDAR_TOP keyframes carry no ``sample_data.prev`` chain, so history has to be
        walked through ``sample.prev`` and the LIDAR_TOP sweep of each earlier sample.
        """
        result = []
        current = self.sample_data(token)
        seen: set[str] = set()
        while len(result) < limit and current["token"] not in seen:
            seen.add(current["token"])
            result.append(self.records(current["token"]))
            previous_sample = str(self.nusc.get("sample", current["sample_token"]).get("prev") or "")
            if not previous_sample:
                break
            previous_token = str(self.nusc.get("sample", previous_sample).get("data", {}).get("LIDAR_TOP") or "")
            if not previous_token:
                break
            current = self.sample_data(previous_token)
        return result

    def sweep_window_tokens(self, first_sample_token: str, last_sample_token: str, limit: int = 500) -> list[tuple[str, int]]:
        """Walk FORWARD from the first to the last sample of a scenario window.

        Returns ``(sample_data_token, timestamp_us)`` per sample that carries a
        LIDAR_TOP sweep, oldest first. The backward ``sweep_records`` walk only
        covers pre-start history; the WASM overlay needs the play range itself.
        """
        tokens: list[tuple[str, int]] = []
        seen: set[str] = set()
        current_token = first_sample_token
        while current_token and current_token not in seen and len(tokens) < limit:
            seen.add(current_token)
            sample = self.nusc.get("sample", current_token)
            if not sample:
                break
            lidar_token = str(sample.get("data", {}).get("LIDAR_TOP") or "")
            if lidar_token:
                record = self.sample_data(lidar_token)
                tokens.append((lidar_token, int(record.get("timestamp", 0))))
            if current_token == last_sample_token:
                break
            current_token = str(sample.get("next") or "")
        return tokens

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
            annotation = self.nusc.get("sample_annotation", box.token)
            output.append({
                "token": box.token,
                "instance_token": annotation.get("instance_token"),
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

    def render_topdown(self, sample_data_token: str, *, nsweeps: int = 5, radar: bool = False) -> bytes:
        """Render the official devkit sample view, including its map underlay."""
        sample_data = self.nusc.get("sample_data", sample_data_token) if radar else self.sample_data(sample_data_token)
        if radar and sample_data.get("channel") != "RADAR_FRONT":
            raise ValueError("sample_data calibration is not RADAR_FRONT")
        try:
            from nuscenes.utils.data_classes import RadarPointCloud
        except ImportError as error:
            raise RuntimeError("nuscenes_devkit_not_installed") from error
        with tempfile.NamedTemporaryFile(suffix=".png") as output:
            try:
                if radar:
                    RadarPointCloud.disable_filters()
                self.explorer.render_sample_data(sample_data_token, nsweeps=nsweeps, underlay_map=True, out_path=output.name)
                output.flush()
                return Path(output.name).read_bytes()
            finally:
                if radar:
                    RadarPointCloud.default_filters()

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
