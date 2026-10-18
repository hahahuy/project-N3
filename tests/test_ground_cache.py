"""Full-map cache persistence contract (handoff item 7).

The preview full map used to be rebuilt from the nuScenes map-expansion files
on every process start, once per (map, transform) key, with no persistence.
It is now a versioned, compressed artifact under the shared metadata cache so
a restart reuses it. These tests pin the parts that are easy to regress:
atomicity, invalidation, bounded memory, and single-build-under-concurrency.
"""

from __future__ import annotations

import gzip
import json
import threading
from pathlib import Path

import pytest

from r2s_web.config import WebSettings
from r2s_web.ground import GroundService
from real2scenario import RoadAlignedTransform, Scenario, State


def _transform(x: float = 0.0, y: float = 0.0, heading: float = 0.0) -> RoadAlignedTransform:
    return RoadAlignedTransform(x, y, heading)


def _settings(tmp_path: Path, cache: Path, *, dataset_root: Path | None = None) -> WebSettings:
    artifact_root = tmp_path / "scenarios"
    artifact_root.mkdir(exist_ok=True)
    return WebSettings(
        project_root=tmp_path,
        artifact_root=artifact_root,
        output_root=tmp_path / "reports",
        dataset_root=dataset_root,
        esmini_bin=None,
        esmini_dat2csv=None,
        dataset_version="v1.0-trainval",
    )


def _scenario(scene_token: str = "scene-token-1") -> Scenario:
    return Scenario(
        scenario_id="scenario-1",
        duration_s=20.0,
        ego_actor_id="ego",
        coordinate_frame="local_road_aligned",
        actors=(
            _actor("ego"),
        ),
        provenance={
            "source_scene_token": scene_token,
            "coordinate_transform_origin_x_m": 0.0,
            "coordinate_transform_origin_y_m": 0.0,
            "coordinate_transform_heading_rad": 0.0,
            "coordinate_transform_source_frame": "nuscenes_global",
            "coordinate_transform_target_frame": "local_road_aligned",
            "coordinate_transform_version": "local-road-aligned-v1",
        },
    )


def _actor(actor_id: str):
    from real2scenario import Actor

    return Actor(
        actor_id=actor_id,
        actor_type="vehicle.ego",
        trajectory=(State(time_s=0.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0),),
    )


@pytest.fixture()
def stub_build(monkeypatch: pytest.MonkeyPatch):
    """Replace the devkit extraction with a deterministic, countable build."""
    calls: list[int] = []

    def fake_build(self, scenario, map_name, transform):  # noqa: ANN001
        calls.append(1)
        return {
            "contract_version": "ground-full-map-v1",
            "frame": "local_road_aligned",
            "map_name": map_name,
            "layers": {"lane": [{"token": f"t{len(calls)}", "geometry": [[0.0, 0.0], [1.0, 1.0]]}]},
            "artifact_visibility": "local_private",
        }

    monkeypatch.setattr(GroundService, "_build_full_layers", fake_build)
    monkeypatch.setattr(
        "r2s_web.ground.resolve_scene_map_name", lambda scene_token, settings: "boston-seaport"
    )
    monkeypatch.setattr(GroundService, "_dataset_signature", lambda self, map_name: "sig-1")
    return calls


def test_first_request_writes_one_versioned_artifact(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    service = GroundService(_settings(tmp_path, cache))

    result = service.full_layers(_scenario())

    assert result["contract_version"] == "ground-full-map-v1"
    assert len(stub_build) == 1
    artifacts = list((cache / "map-cache").glob("*.json.gz"))
    assert len(artifacts) == 1, "exactly one artifact per map and transform"
    # The filename carries dataset version, map, transform hash, signature and
    # contract version, so a stale artifact can never collide with a good one.
    name = artifacts[0].name
    assert name.startswith("map-v1.0-trainval-boston-seaport-")
    assert name.endswith("-full-map-v1.json.gz")


def test_artifact_survives_a_fresh_service_in_a_new_process(tmp_path, monkeypatch, stub_build) -> None:
    """A restart must reuse the artifact rather than re-extract the map."""
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    scenario = _scenario()

    first = GroundService(_settings(tmp_path, cache)).full_layers(scenario)
    # A new service models a restarted process: no in-process cache survives.
    second = GroundService(_settings(tmp_path, cache)).full_layers(scenario)

    assert len(stub_build) == 1, "second service must hit the persisted artifact"
    assert first == second


def test_transform_change_regenerates_instead_of_reusing(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    service = GroundService(_settings(tmp_path, cache))

    service.full_layers(_scenario())

    moved = Scenario(
        scenario_id="scenario-1",
        duration_s=20.0,
        ego_actor_id="ego",
        coordinate_frame="local_road_aligned",
        actors=(_actor("ego"),),
        provenance={
            **_scenario().provenance,
            "coordinate_transform_origin_x_m": 12.5,
            "coordinate_transform_heading_rad": 0.75,
        },
    )
    service.full_layers(moved)

    assert len(stub_build) == 2, "a different transform must not reuse the old artifact"
    assert len(list((cache / "map-cache").glob("*.json.gz"))) == 2


def test_dataset_signature_change_regenerates(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    scenario = _scenario()

    GroundService(_settings(tmp_path, cache)).full_layers(scenario)

    # The dataset changed underneath us, so the recorded signature no longer
    # matches and the artifact must be rebuilt rather than silently reused.
    monkeypatch.setattr(GroundService, "_dataset_signature", lambda self, map_name: "sig-2")
    rebuilt = GroundService(_settings(tmp_path, cache)).full_layers(scenario)

    assert len(stub_build) == 2
    assert rebuilt["layers"]["lane"][0]["token"] == "t2"


def test_corrupt_or_hand_edited_artifact_is_rebuilt(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    service = GroundService(_settings(tmp_path, cache))
    service.full_layers(_scenario())

    artifact = next((cache / "map-cache").glob("*.json.gz"))
    with gzip.open(artifact, "wt", encoding="utf-8") as handle:
        json.dump({"contract_version": "something-else", "layers": {}}, handle)

    fresh = GroundService(_settings(tmp_path, cache)).full_layers(_scenario())

    assert len(stub_build) == 2, "a contract mismatch must rebuild, never reuse"
    assert fresh["contract_version"] == "ground-full-map-v1"


def test_truncated_artifact_does_not_crash_the_preview(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    GroundService(_settings(tmp_path, cache)).full_layers(_scenario())

    artifact = next((cache / "map-cache").glob("*.json.gz"))
    artifact.write_bytes(artifact.read_bytes()[:20])

    result = GroundService(_settings(tmp_path, cache)).full_layers(_scenario())

    assert result["contract_version"] == "ground-full-map-v1"
    assert len(stub_build) == 2


def test_no_temporary_files_are_left_behind(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    GroundService(_settings(tmp_path, cache)).full_layers(_scenario())

    leftovers = [p.name for p in (cache / "map-cache").iterdir() if not p.name.endswith(".json.gz")]
    assert leftovers == [], f"atomic write left debris: {leftovers}"


def test_in_process_cache_is_bounded(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    service = GroundService(_settings(tmp_path, cache))

    for index in range(6):
        service.full_layers(
            Scenario(
                scenario_id=f"scenario-{index}",
                duration_s=20.0,
                ego_actor_id="ego",
                coordinate_frame="local_road_aligned",
                actors=(_actor("ego"),),
                provenance={
                    **_scenario().provenance,
                    "coordinate_transform_origin_x_m": float(index),
                },
            )
        )

    assert len(service._full_cache) <= 4, "in-process map cache must stay bounded"


def test_concurrent_requests_build_the_map_once(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    service = GroundService(_settings(tmp_path, cache))
    scenario = _scenario()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            service.full_layers(scenario)
        except BaseException as error:  # pragma: no cover - surfaced via assert
            errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"concurrent build raised: {errors}"
    assert len(stub_build) == 1, "a burst for one map must not duplicate the build"
    assert len(list((cache / "map-cache").glob("*.json.gz"))) == 1


def test_read_only_cache_volume_does_not_break_the_preview(tmp_path, monkeypatch, stub_build) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("PROJECT_N3_METADATA_CACHE", str(cache))
    cache.chmod(0o500)
    try:
        result = GroundService(_settings(tmp_path, cache)).full_layers(_scenario())
    finally:
        cache.chmod(0o700)
    assert result["contract_version"] == "ground-full-map-v1"