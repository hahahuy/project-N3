import json
from pathlib import Path

import pytest

from real2scenario import SourceWindow, extract_scenario


def _write_tables(root: Path) -> SourceWindow:
    metadata = root / "v1.0-mini"
    metadata.mkdir()
    tables = {
        "scene": [
            {
                "token": "scene-1",
                "first_sample_token": "sample-1",
            }
        ],
        "sample": [
            {
                "token": "sample-1",
                "scene_token": "scene-1",
                "timestamp": 1_000_000,
                "next": "sample-2",
            },
            {
                "token": "sample-2",
                "scene_token": "scene-1",
                "timestamp": 2_000_000,
                "next": "",
            },
        ],
        "sample_data": [
            {
                "token": "lidar-1",
                "sample_token": "sample-1",
                "ego_pose_token": "pose-1",
                "calibrated_sensor_token": "calibration-1",
                "is_key_frame": True,
            },
            {
                "token": "lidar-2",
                "sample_token": "sample-2",
                "ego_pose_token": "pose-2",
                "calibrated_sensor_token": "calibration-1",
                "is_key_frame": True,
            },
        ],
        "sample_annotation": [
            {
                "token": "annotation-1",
                "sample_token": "sample-1",
                "instance_token": "instance-1",
                "translation": [10.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "size": [2.0, 4.0, 1.5],
            },
            {
                "token": "annotation-2",
                "sample_token": "sample-2",
                "instance_token": "instance-1",
                "translation": [12.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "size": [2.0, 4.0, 1.5],
            },
        ],
        "instance": [{"token": "instance-1", "category_token": "category-1"}],
        "ego_pose": [
            {
                "token": "pose-1",
                "translation": [0.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
            },
            {
                "token": "pose-2",
                "translation": [1.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
            },
        ],
        "calibrated_sensor": [{"token": "calibration-1", "sensor_token": "sensor-1"}],
        "sensor": [{"token": "sensor-1", "channel": "LIDAR_TOP"}],
        "category": [{"token": "category-1", "name": "vehicle.car"}],
    }
    for name, rows in tables.items():
        (metadata / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")
    return SourceWindow("scene-1", "sample-1", "sample-2")


def test_extract_scenario_from_synthetic_nuscenes_window(tmp_path: Path) -> None:
    window = _write_tables(tmp_path)

    scenario = extract_scenario(tmp_path, window, ["instance-1"])

    ego, actor = scenario.actors
    assert scenario.coordinate_frame == "nuscenes_global"
    assert scenario.duration_s == 1.0
    assert scenario.provenance["source_window"] == "sample-1:sample-2"
    assert [(state.time_s, state.x_m, state.speed_mps) for state in ego.trajectory] == [
        (0.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
    ]
    assert actor.actor_id == "instance-instance-1"
    assert actor.actor_type == "vehicle.car"
    assert actor.length_m == 4.0
    assert actor.width_m == 2.0
    assert [(state.time_s, state.x_m, state.speed_mps) for state in actor.trajectory] == [
        (0.0, 10.0, 2.0),
        (1.0, 12.0, 2.0),
    ]


def test_extract_scenario_rejects_actor_not_observed_in_window(tmp_path: Path) -> None:
    window = _write_tables(tmp_path)
    metadata = tmp_path / "v1.0-mini"
    instances = json.loads((metadata / "instance.json").read_text())
    instances.append({"token": "instance-2", "category_token": "category-1"})
    (metadata / "instance.json").write_text(json.dumps(instances), encoding="utf-8")

    with pytest.raises(ValueError, match="no annotations"):
        extract_scenario(tmp_path, window, ["instance-2"])


def test_extract_scenario_rejects_window_end_before_start(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    window = SourceWindow("scene-1", "sample-2", "sample-1")

    with pytest.raises(ValueError, match="does not follow"):
        extract_scenario(tmp_path, window, ["instance-1"])


def test_extract_scenario_rejects_empty_actor_selection(tmp_path: Path) -> None:
    window = _write_tables(tmp_path)

    with pytest.raises(ValueError, match="at least one"):
        extract_scenario(tmp_path, window, [])


def test_actor_timestamps_remain_relative_to_the_source_window(tmp_path: Path) -> None:
    window = _write_tables(tmp_path)
    metadata = tmp_path / "v1.0-mini"
    annotations = json.loads((metadata / "sample_annotation.json").read_text())
    (metadata / "sample_annotation.json").write_text(json.dumps(annotations[1:]), encoding="utf-8")

    scenario = extract_scenario(tmp_path, window, ["instance-1"])

    assert scenario.actors[1].trajectory[0].time_s == 1.0
