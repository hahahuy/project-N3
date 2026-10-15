"""Private, decimated nuScenes LIDAR_TOP payload service."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from real2scenario import lidar_payload_contract

from .config import WebSettings


class LidarService:
    def __init__(self, settings: WebSettings):
        self.settings = settings

    def capability(self) -> dict[str, object]:
        if self.settings.dataset_root is None:
            return {"available": False, "unavailable_reason": "dataset_not_configured"}
        if not (self.settings.dataset_root / self.settings.dataset_version / "sample_data.json").is_file():
            return {"available": False, "unavailable_reason": "sample_data_not_available"}
        try:
            import nuscenes.utils.data_classes  # noqa: F401
        except ImportError:
            return {"available": False, "unavailable_reason": "nuscenes_devkit_not_installed"}
        return {"available": True, "unavailable_reason": None, "channel": "LIDAR_TOP", "artifact_visibility": "local_private"}

    def payload(self, sample_data_token: str, decimation: int = 8) -> tuple[dict[str, object], bytes]:
        if decimation < 1 or decimation > 1024:
            raise ValueError("decimation must be between 1 and 1024")
        sample_data, calibration, ego_pose, source_path = self._records(sample_data_token)
        contract = lidar_payload_contract({**sample_data, "filename": str(source_path.relative_to(self.settings.dataset_root))}, calibration, decimation=decimation)
        try:
            from nuscenes.utils.data_classes import LidarPointCloud
            cloud = LidarPointCloud.from_file(str(source_path))
            points = cloud.points.T[::decimation]
            payload = b"".join(struct.pack("<ffff", float(point[0]), float(point[1]), float(point[2]), float(point[3])) for point in points)
            total_count = int(cloud.points.shape[1])
        except (ImportError, OSError, ValueError) as error:
            raise RuntimeError(f"lidar_payload_unavailable:{type(error).__name__}") from error
        return ({**self._metadata(sample_data, calibration, ego_pose, contract), "decimation": decimation, "total_count": total_count, "returned_count": len(points)}, payload)

    def availability(self, sample_data_token: str) -> dict[str, object]:
        """Return only whether the recorded sweep can be addressed, plus a reason."""
        if not sample_data_token:
            return {"available": False, "unavailable_reason": "recorded_lidar_sample_unavailable"}
        try:
            self.descriptor(sample_data_token)
        except (FileNotFoundError, ImportError, KeyError, OSError, RuntimeError, ValueError) as error:
            return {"available": False, "unavailable_reason": str(error)}
        return {"available": True, "unavailable_reason": None}

    def descriptor(self, sample_data_token: str) -> dict[str, object]:
        """Return safe metadata for a browser to address a private sweep."""
        sample_data, calibration, ego_pose, _ = self._records(sample_data_token)
        contract = lidar_payload_contract(sample_data, calibration)
        return {**self._metadata(sample_data, calibration, ego_pose, contract), "decimation": None, "total_count": None, "returned_count": None}

    def _metadata(self, sample_data: dict[str, Any], calibration: dict[str, Any], ego_pose: dict[str, Any], contract: Any) -> dict[str, object]:
        return {
            "version": contract.version,
            "channel": contract.channel,
            "timestamp_us": contract.timestamp_us,
            "frame": "sensor",
            "coordinate_frame": "nuscenes_global",
            "calibration_token": contract.calibration_token,
            "calibration_transform": _transform(calibration),
            "ego_pose_transform": _transform(ego_pose),
            "transform_version": "nuscenes-sensor-global-v1",
            "source_file": str(sample_data["filename"]),
            "artifact_visibility": "local_private",
        }

    def _records(self, token: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
        if self.settings.dataset_root is None:
            raise RuntimeError("dataset_not_configured")
        root = self.settings.dataset_root / self.settings.dataset_version
        tables = {name: json.loads((root / f"{name}.json").read_text(encoding="utf-8")) for name in ("sample_data", "calibrated_sensor", "sensor", "ego_pose")}
        candidates = [item for item in tables["sample_data"] if item.get("token") == token or item.get("sample_token") == token]
        sample_data = None
        calibration = None
        for candidate in candidates:
            candidate_calibration = next((item for item in tables["calibrated_sensor"] if item.get("token") == candidate.get("calibrated_sensor_token")), None)
            sensor = next((item for item in tables["sensor"] if item.get("token") == (candidate_calibration or {}).get("sensor_token")), None)
            if candidate_calibration is not None and sensor and sensor.get("channel") == "LIDAR_TOP":
                sample_data, calibration = candidate, candidate_calibration
                break
        if sample_data is None or calibration is None:
            raise ValueError("sample_data calibration is not LIDAR_TOP")
        ego_pose = next((item for item in tables["ego_pose"] if item.get("token") == sample_data.get("ego_pose_token")), None)
        if ego_pose is None:
            raise ValueError("LIDAR sample_data ego pose is unavailable")
        source_path = (self.settings.dataset_root / str(sample_data["filename"])).resolve()
        if not source_path.is_file() or self.settings.dataset_root not in source_path.parents:
            raise FileNotFoundError("LIDAR source file is unavailable")
        return sample_data, calibration, ego_pose, source_path


def _transform(record: dict[str, Any]) -> dict[str, object]:
    translation = record.get("translation")
    rotation = record.get("rotation")
    if not isinstance(translation, list) or len(translation) != 3 or not isinstance(rotation, list) or len(rotation) != 4:
        raise ValueError("LIDAR transform is unavailable")
    return {"translation_m": [float(value) for value in translation], "rotation_wxyz": [float(value) for value in rotation]}
