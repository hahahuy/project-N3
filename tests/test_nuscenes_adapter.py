from pathlib import Path

import numpy as np

from r2s_web.nuscenes_adapter import NuScenesDatasetAdapter


def test_dataset_adapter_is_cached_by_root_and_version(tmp_path: Path) -> None:
    first = NuScenesDatasetAdapter.for_dataset(tmp_path, "v1.0-mini")
    second = NuScenesDatasetAdapter.for_dataset(tmp_path, "v1.0-mini")
    other = NuScenesDatasetAdapter.for_dataset(tmp_path, "v1.0-trainval")

    assert first is second
    assert first is not other


def test_vectorized_lidar_payload_has_little_endian_xyzi_layout() -> None:
    cloud = np.array([[1, 2], [3, 4], [5, 6], [7, 8]], dtype=np.float64)
    payload = np.ascontiguousarray(cloud[:, ::2].T, dtype="<f4").tobytes()

    assert len(payload) == 16
    assert np.frombuffer(payload, dtype="<f4").tolist() == [1, 3, 5, 7]


def test_transform_composition_uses_official_matrix_shape(monkeypatch, tmp_path: Path) -> None:
    adapter = NuScenesDatasetAdapter(tmp_path, "v1.0-mini")

    class Quaternion:
        def __init__(self, values):
            self.values = values

    monkeypatch.setitem(__import__("sys").modules, "pyquaternion", type("M", (), {"Quaternion": Quaternion}))
    geometry = type("G", (), {"transform_matrix": staticmethod(lambda translation, rotation: np.eye(4))})
    monkeypatch.setitem(__import__("sys").modules, "nuscenes.utils.geometry_utils", geometry)

    result = adapter.transform(
        {"token": "cal", "translation": [1, 2, 3], "rotation": [1, 0, 0, 0]},
        {"token": "pose", "translation": [4, 5, 6], "rotation": [1, 0, 0, 0]},
    )

    assert len(result["matrix_4x4"]) == 4
    assert result["composition"] == ["sensor_to_ego", "ego_to_global"]
