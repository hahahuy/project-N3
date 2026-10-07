from pathlib import Path
from types import SimpleNamespace

import pytest

from real2scenario import devkit


def _fake_nuscenes() -> SimpleNamespace:
    return SimpleNamespace(
        category=[{}],
        instance=[{}],
        scene=[
            {
                "name": "scene-0001",
                "token": "scene-token",
                "nbr_samples": 2,
                "first_sample_token": "first-sample",
                "last_sample_token": "last-sample",
                "log_token": "log-token",
            }
        ],
        sample=[{}, {}],
        sample_annotation=[{}],
        sample_data=[{}],
        ego_pose=[{}],
        calibrated_sensor=[{}],
        sensor=[{}],
        log=[{}],
        map=[{}],
    )


def test_inventory_returns_reviewable_table_and_scene_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(devkit, "_load_nuscenes", lambda root, version: _fake_nuscenes())

    inventory = devkit.inventory_dataset(tmp_path, "v1.0-mini")

    assert inventory["dataset_root"] == str(tmp_path)
    assert inventory["table_counts"]["scene"] == 1
    assert inventory["scenes"] == [
        {
            "name": "scene-0001",
            "token": "scene-token",
            "sample_count": 2,
            "first_sample_token": "first-sample",
            "last_sample_token": "last-sample",
            "log_token": "log-token",
        }
    ]


def test_render_requires_exactly_one_selector(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        devkit.render_sample(tmp_path, "v1.0-mini", tmp_path / "sample.png")


def test_render_rejects_scene_index_outside_loaded_dataset(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(devkit, "_load_nuscenes", lambda root, version: _fake_nuscenes())

    with pytest.raises(ValueError, match="out of range"):
        devkit.render_sample(tmp_path, "v1.0-mini", tmp_path / "sample.png", scene_index=1)
