import json
from pathlib import Path
import threading

import pytest

from real2scenario import SourceWindow, extract_scenario
from real2scenario.metadata_index import MetadataIndex, default_cache_dir


def _write_tables(root: Path, *, line_delimited: bool = True) -> None:
    metadata = root / "v1.0-mini"
    metadata.mkdir(parents=True)
    tables = {
        "scene": [
            {
                "token": "scene-1",
                "name": "scene-0001",
                "description": "first",
                "first_sample_token": "sample-1",
                "last_sample_token": "sample-2",
            },
            {
                "token": "scene-2",
                "name": "scene-0002",
                "description": "second",
                "first_sample_token": "sample-3",
                "last_sample_token": "sample-3",
            },
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
            {
                "token": "sample-3",
                "scene_token": "scene-2",
                "timestamp": 3_000_000,
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
                "filename": "samples/LIDAR_TOP/a.pcd",
            },
            {
                "token": "lidar-2",
                "sample_token": "sample-2",
                "ego_pose_token": "pose-2",
                "calibrated_sensor_token": "calibration-1",
                "is_key_frame": True,
                "filename": "samples/LIDAR_TOP/b.pcd",
            },
            {
                "token": "sweep-3",
                "sample_token": "sample-3",
                "ego_pose_token": "pose-3",
                "calibrated_sensor_token": "calibration-2",
                "is_key_frame": False,
                "filename": "sweeps/LIDAR_TOP/c.pcd",
            },
            {
                "token": "camera-1",
                "sample_token": "sample-1",
                "ego_pose_token": "pose-9",
                "calibrated_sensor_token": "calibration-3",
                "is_key_frame": True,
                "filename": "samples/CAM_FRONT/d.jpg",
            },
        ],
        "sample_annotation": [
            {
                "token": "annotation-1",
                "sample_token": "sample-1",
                "instance_token": "instance-car",
                "translation": [10.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "size": [2.0, 4.0, 1.5],
            },
            {
                "token": "annotation-2",
                "sample_token": "sample-2",
                "instance_token": "instance-car",
                "translation": [12.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "size": [2.0, 4.0, 1.5],
            },
            {
                "token": "annotation-3",
                "sample_token": "sample-3",
                "instance_token": "instance-bus",
                "translation": [0.0, 5.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "size": [3.0, 12.0, 3.5],
            },
        ],
        "instance": [
            {"token": "instance-car", "category_token": "category-car"},
            {"token": "instance-bus", "category_token": "category-bus"},
        ],
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
            {
                "token": "pose-3",
                "translation": [2.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
            },
        ],
        "calibrated_sensor": [
            {"token": "calibration-1", "sensor_token": "sensor-lidar"},
            {"token": "calibration-2", "sensor_token": "sensor-lidar"},
            {"token": "calibration-3", "sensor_token": "sensor-camera"},
        ],
        "sensor": [
            {"token": "sensor-lidar", "channel": "LIDAR_TOP"},
            {"token": "sensor-camera", "channel": "CAM_FRONT"},
        ],
        "category": [
            {"token": "category-car", "name": "vehicle.car"},
            {"token": "category-bus", "name": "vehicle.bus"},
        ],
    }
    for name, rows in tables.items():
        if line_delimited:
            lines = ["["]
            for position, row in enumerate(rows):
                lines.extend(json.dumps(row, indent=4).splitlines())
                if position < len(rows) - 1:
                    lines[-1] = lines[-1] + ","
            lines.append("]")
            (metadata / f"{name}.json").write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            (metadata / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")


def test_index_exposes_scene_metadata(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    with MetadataIndex(tmp_path, "v1.0-mini", cache_dir=tmp_path / "cache") as index:
        assert index.index_version == "nuscenes-metadata-index-v1"
        assert [record["token"] for record in index.scene_records()] == ["scene-1", "scene-2"]
        assert index.sample_tokens("scene-1") == ("sample-1", "sample-2")
        assert index.instance_tokens("scene-1") == ("instance-car",)
        assert index.instance_tokens("scene-2") == ("instance-bus",)
        assert index.instance_tokens("scene-1", category_prefix=None) == ("instance-car",)
        assert index.built_now is True


def test_index_tables_match_direct_table_loading(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    window = SourceWindow("scene-1", "sample-1", "sample-2")
    expected = extract_scenario(tmp_path, window, ["instance-car"], version="v1.0-mini")
    with MetadataIndex(tmp_path, "v1.0-mini", cache_dir=tmp_path / "cache") as index:
        tables = index.tables_for_scenes(["scene-1"])
        assert [record["token"] for record in tables["sample_data"]] == ["lidar-1", "lidar-2"]
        assert {record["token"] for record in tables["ego_pose"]} == {"pose-1", "pose-2"}
        actual = extract_scenario(
            tmp_path, window, ["instance-car"], version="v1.0-mini", tables=tables
        )
    assert actual == expected


def test_index_reuses_matching_persistent_cache(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    cache_dir = tmp_path / "cache"
    with MetadataIndex(tmp_path, "v1.0-mini", cache_dir=cache_dir) as index:
        assert index.built_now is True
        cache_path = index.cache_path
        first = index.tables_for_scenes(["scene-1"])
    assert cache_path is not None and cache_path.exists()
    with MetadataIndex(tmp_path, "v1.0-mini", cache_dir=cache_dir) as index:
        assert index.built_now is False
        assert index.tables_for_scenes(["scene-1"]) == first


def test_index_rebuilds_when_source_tables_change(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    cache_dir = tmp_path / "cache"
    with MetadataIndex(tmp_path, "v1.0-mini", cache_dir=cache_dir):
        pass
    (tmp_path / "v1.0-mini" / "category.json").write_text(
        json.dumps([{"token": "category-car", "name": "vehicle.car"}]), encoding="utf-8"
    )
    with MetadataIndex(tmp_path, "v1.0-mini", cache_dir=cache_dir) as index:
        assert index.built_now is True
        assert index.instance_tokens("scene-2") == ()


def test_index_streams_line_delimited_and_compact_layouts(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    with MetadataIndex(tmp_path, "v1.0-mini") as memory_index:
        memory_tables = memory_index.tables_for_scenes(["scene-1"])
        compact_root = tmp_path / "compact"
        _write_tables(compact_root, line_delimited=False)
        with MetadataIndex(compact_root, "v1.0-mini") as compact_index:
            assert compact_index.tables_for_scenes(["scene-1"]) == memory_tables


def test_index_in_memory_mode_is_not_persistent(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    with MetadataIndex(tmp_path, "v1.0-mini") as index:
        assert index.cache_path is None
        assert index.status()["cache_mode"] == "in_memory"


def test_index_rejects_unknown_scene_and_empty_selection(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    with MetadataIndex(tmp_path, "v1.0-mini") as index:
        with pytest.raises(KeyError):
            index.scene("scene-missing")
        with pytest.raises(ValueError):
            index.tables_for_scenes([])
        with pytest.raises(KeyError):
            index.tables_for_scenes(["scene-missing"])


def test_index_requires_existing_metadata_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        MetadataIndex(tmp_path, "v1.0-mini")
    with pytest.raises(ValueError):
        MetadataIndex(tmp_path, "")


def test_default_cache_dir_is_local_and_private() -> None:
    assert default_cache_dir().name == "metadata-index"
    assert default_cache_dir().is_absolute()


def test_extract_scenario_rejects_incomplete_supplied_tables(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    with MetadataIndex(tmp_path, "v1.0-mini") as index:
        tables = index.tables_for_scenes(["scene-1"])
    incomplete = {name: value for name, value in tables.items() if name != "ego_pose"}
    with pytest.raises(ValueError, match="ego_pose"):
        extract_scenario(
            tmp_path,
            SourceWindow("scene-1", "sample-1", "sample-2"),
            ["instance-car"],
            version="v1.0-mini",
            tables=incomplete,
        )

def test_index_is_usable_from_multiple_threads(tmp_path: Path) -> None:
    _write_tables(tmp_path)
    with MetadataIndex(tmp_path, "v1.0-mini", cache_dir=tmp_path / "cache") as index:
        expected = index.tables_for_scenes(["scene-1"])
        results: list[object] = []
        errors: list[BaseException] = []

        def query() -> None:
            try:
                results.append(index.tables_for_scenes(["scene-1"]))
            except BaseException as error:  # pragma: no cover - failure detail
                errors.append(error)

        threads = [threading.Thread(target=query) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert errors == []
    assert results == [expected] * 4
