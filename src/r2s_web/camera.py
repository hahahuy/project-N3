"""Display-only camera evidence contracts.

Dataset access and HTTP wiring stay outside this module. Callers provide the
resolved camera sample and overlay inputs, which keeps recorded evidence
separate from canonical scenario state and from replay metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .camera_projection import ProjectedPoint, project_camera_points
from .preview_time import resolve_preview_time


@dataclass(frozen=True, slots=True)
class CameraEvidenceFrame:
    contract_version: str
    channel: str
    requested_time_s: float
    resolved_time_s: float
    timestamp_us: int
    selection_policy: str
    image: Mapping[str, Any]
    calibration: Mapping[str, Any]
    recorded_cuboids: tuple[Mapping[str, Any], ...]
    canonical_cuboids: tuple[Mapping[str, Any], ...]
    lidar_points: tuple[ProjectedPoint, ...]
    provenance: Mapping[str, str]


class CameraEvidenceService:
    """Compose one time-addressed camera evidence response without side effects."""

    CONTRACT_VERSION = "nuscenes-camera-evidence-v1"

    def __init__(self, resolver: Callable[..., Any]) -> None:
        self._resolver = resolver

    @staticmethod
    def from_dataset_window(
        *,
        adapter: Any,
        first_sample_token: str,
        last_sample_token: str,
        channel: str,
        requested_time_s: float,
        canonical_cuboids: Sequence[Mapping[str, Any]] = (),
        policy: str = "nearest",
    ) -> CameraEvidenceFrame:
        records = adapter.camera_records(first_sample_token, last_sample_token, channel)
        if not records:
            raise ValueError("recorded_camera_sample_unavailable")
        timestamps = tuple(int(record[0].get("source_timestamp", record[0]["timestamp"])) for record in records)
        resolution = resolve_preview_time(requested_time_s, timestamps, policy=policy)
        sample_data, calibration, ego_pose, path = records[resolution.index]
        recorded_cuboids, intrinsic = adapter.camera_annotations(sample_data["token"])
        lidar_points = adapter.camera_lidar_projection(sample_data["token"])
        return CameraEvidenceFrame(
            contract_version=CameraEvidenceService.CONTRACT_VERSION,
            channel=channel,
            requested_time_s=resolution.requested_time_s,
            resolved_time_s=resolution.resolved_time_s,
            timestamp_us=resolution.timestamp_us,
            selection_policy=resolution.policy,
            image={
                "sample_data_token": str(sample_data["token"]),
                "filename": str(sample_data["filename"]),
                "path": str(path),
                "width": sample_data.get("width"),
                "height": sample_data.get("height"),
            },
            calibration={
                "intrinsic": intrinsic,
                "translation_m": [float(value) for value in calibration["translation"]],
                "rotation_wxyz": [float(value) for value in calibration["rotation"]],
            },
            recorded_cuboids=tuple(recorded_cuboids),
            canonical_cuboids=tuple(dict(item) for item in canonical_cuboids),
            lidar_points=tuple(ProjectedPoint(point["u"], point["v"], point["depth_m"]) for point in lidar_points),
            provenance={
                "source": "nuscenes-devkit-camera-evidence",
                "artifact_visibility": "local_private",
                "calibration_token": str(calibration["token"]),
                "ego_pose_token": str(ego_pose["token"]),
                "intrinsic": str(intrinsic),
            },
        )

    def frame(
        self,
        *,
        channel: str,
        requested_time_s: float,
        timestamps_us: Sequence[int],
        image: Mapping[str, Any],
        recorded_cuboids: Sequence[Mapping[str, Any]] = (),
        canonical_cuboids: Sequence[Mapping[str, Any]] = (),
        lidar_points_camera: Sequence[Sequence[float]] = (),
        intrinsic: Sequence[Sequence[float]] | None = None,
        policy: str = "nearest",
    ) -> CameraEvidenceFrame:
        resolution = self._resolver(requested_time_s, timestamps_us, policy=policy)
        projected = () if intrinsic is None else tuple(project_camera_points(lidar_points_camera, intrinsic))
        return CameraEvidenceFrame(
            contract_version=self.CONTRACT_VERSION,
            channel=channel,
            requested_time_s=resolution.requested_time_s,
            resolved_time_s=resolution.resolved_time_s,
            timestamp_us=resolution.timestamp_us,
            selection_policy=resolution.policy,
            image=dict(image),
            calibration={},
            recorded_cuboids=tuple(dict(item) for item in recorded_cuboids),
            canonical_cuboids=tuple(dict(item) for item in canonical_cuboids),
            lidar_points=projected,
            provenance={
                "source": "nuscenes-devkit-camera-evidence",
                "artifact_visibility": "local_private",
                "cuboid_sources": "recorded_annotations_and_canonical_scenario",
            },
        )
