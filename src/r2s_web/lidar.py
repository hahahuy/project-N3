"""Private, decimated nuScenes LIDAR_TOP payload service."""

from __future__ import annotations

from typing import Any


from real2scenario import lidar_payload_contract

from .config import WebSettings
from .nuscenes_adapter import NuScenesDatasetAdapter


class LidarService:
    def __init__(self, settings: WebSettings):
        self.settings = settings
        self._dataset: NuScenesDatasetAdapter | None = None

    def _adapter(self) -> NuScenesDatasetAdapter:
        if self.settings.dataset_root is None:
            raise RuntimeError("dataset_not_configured")
        if self._dataset is None:
            self._dataset = NuScenesDatasetAdapter.for_dataset(self.settings.dataset_root, self.settings.dataset_version)
        return self._dataset

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
        sample_data, calibration, ego_pose, source_path = self._adapter().records(sample_data_token)
        contract = lidar_payload_contract({**sample_data, "filename": str(source_path.relative_to(self.settings.dataset_root))}, calibration, decimation=decimation)
        try:
            from nuscenes.utils.data_classes import LidarPointCloud
            import numpy as np
            cloud = LidarPointCloud.from_file(str(source_path))
            points = np.ascontiguousarray(cloud.points[:4, ::decimation].T, dtype="<f4")
            payload = points.tobytes(order="C")
            total_count = int(cloud.points.shape[1])
        except (ImportError, OSError, ValueError) as error:
            raise RuntimeError(f"lidar_payload_unavailable:{type(error).__name__}") from error
        return ({**self._metadata(sample_data, calibration, ego_pose, contract), "decimation": decimation, "total_count": total_count, "returned_count": int(len(points))}, payload)

    def sample_data_token(self, window_token: str) -> str:
        """Resolve a scenario window token to the LIDAR_TOP sweep it stands for."""
        return self._adapter().lidar_sample_data_token(window_token)

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
        sample_data, calibration, ego_pose, _ = self._adapter().records(sample_data_token)
        contract = lidar_payload_contract(sample_data, calibration)
        return {**self._metadata(sample_data, calibration, ego_pose, contract), "decimation": None, "total_count": None, "returned_count": None}

    def sweep_window(self, first_sample_token: str, last_sample_token: str) -> list[dict[str, object]]:
        """List the LIDAR_TOP sweeps spanning a scenario window, oldest first.

        Each entry carries its payload address plus a ``time_s`` relative to
        the first sweep, so a browser overlay can follow the playhead. Empty
        (never invented) when the window holds no sweep.
        """
        dataset = self._adapter()
        entries = []
        first_us: int | None = None
        for sample_data_token, timestamp_us in dataset.sweep_window_tokens(first_sample_token, last_sample_token):
            if first_us is None:
                first_us = timestamp_us
            entries.append({
                "sample_data_token": sample_data_token,
                "timestamp_us": timestamp_us,
                "time_s": (timestamp_us - first_us) / 1e6,
                "payload_url": f"/api/workspace/lidar/{sample_data_token}",
            })
        return entries

    def sensor_evidence(self, sample_data_token: str, nsweeps: int = 5) -> dict[str, object]:
        """Describe recorded LIDAR_TOP history using nuScenes sweep semantics."""
        if not 1 <= nsweeps <= 20:
            raise ValueError("nsweeps must be between 1 and 20")
        dataset = self._adapter()
        records = dataset.sweep_records(sample_data_token, nsweeps)
        if not records:
            raise ValueError("recorded_lidar_sweeps_unavailable")
        sweeps = []
        for sample_data, calibration, ego_pose, source_path in records:
            contract = lidar_payload_contract(sample_data, calibration)
            transforms = dataset.transform(calibration, ego_pose)
            sweeps.append({
                **self._metadata(sample_data, calibration, ego_pose, contract),
                "sample_data_token": sample_data["token"],
                "sample_token": sample_data.get("sample_token"),
                "timestamp_us": int(sample_data.get("timestamp", contract.timestamp_us)),
                "offset_us": int(sample_data.get("timestamp", contract.timestamp_us)) - int(records[0][0].get("timestamp", contract.timestamp_us)),
                "historical": sample_data["token"] != records[0][0]["token"],
                "transforms": transforms,
                "payload_url": f"/api/workspace/lidar/{sample_data['token']}",
                "source_file": str(source_path.relative_to(self.settings.dataset_root)),
            })
        first = sweeps[0]
        return {
            "contract_version": "nuscenes-sensor-evidence-v1",
            "channel": "LIDAR_TOP",
            "sample_data_token": first["sample_data_token"],
            "sample_token": first["sample_token"],
            "timestamp_us": first["timestamp_us"],
            "nsweeps": len(sweeps),
            "requested_nsweeps": nsweeps,
            "sweeps": sweeps,
            "reference": {"sample_data_token": first["sample_data_token"], "sample_token": first["sample_token"], "timestamp_us": first["timestamp_us"]},
            "annotations": dataset.annotations(first["sample_data_token"]),
            "map_underlay": dataset.map_underlay(first["sample_data_token"]),
            "can_telemetry": dataset.can_alignment(first["sample_data_token"]),
            "synchronization": {
                "status": "recorded_history",
                "reference_timestamp_us": first["timestamp_us"],
                "historical_sweep_smearing": "expected_motion_smear_across_historical_sweeps",
            },
            "provenance": {
                "source": "nuscenes-devkit-sensor-evidence",
                "render_equivalent": "render_sample_data:LIDAR_TOP:nsweeps",
                **dataset.multisweep_provenance(first["sample_data_token"], nsweeps),
                "artifact_visibility": "local_private",
                "post_edit_frames": "unsupported",
            },
            "artifact_visibility": "local_private",
        }

    def topdown(self, sample_data_token: str, source: str = "lidar", nsweeps: int = 5) -> bytes:
        if source not in {"lidar", "radar"}:
            raise ValueError("unsupported_top_down_source")
        dataset = self._adapter()
        if source == "radar":
            sample_data = dataset.sample_data(sample_data_token)
            sample = dataset.nusc.get("sample", sample_data["sample_token"])
            sample_data_token = sample["data"].get("RADAR_FRONT", "")
            if not sample_data_token:
                raise ValueError("RADAR_FRONT_sample_unavailable")
        return dataset.render_topdown(sample_data_token, nsweeps=nsweeps, radar=source == "radar")

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

def _transform(record: dict[str, Any]) -> dict[str, object]:
    translation = record.get("translation")
    rotation = record.get("rotation")
    if not isinstance(translation, list) or len(translation) != 3 or not isinstance(rotation, list) or len(rotation) != 4:
        raise ValueError("LIDAR transform is unavailable")
    return {"translation_m": [float(value) for value in translation], "rotation_wxyz": [float(value) for value in rotation]}
