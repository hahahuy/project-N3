import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from r2s_web.app import create_app
from r2s_web.config import WebSettings


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic-variant-artifact.json"


def _client(tmp_path: Path) -> TestClient:
    artifact_root = tmp_path / "scenarios"
    artifact_root.mkdir()
    shutil.copy(FIXTURE, artifact_root / "baseline.json")
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=artifact_root,
        output_root=tmp_path / "reports",
        dataset_root=None,
        esmini_bin=None,
        esmini_dat2csv=None,
    )
    return TestClient(create_app(settings))


def test_empty_artifact_root_is_a_valid_health_state(tmp_path: Path) -> None:
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "missing",
        output_root=tmp_path / "reports",
        dataset_root=None,
        esmini_bin=None,
        esmini_dat2csv=None,
    )

    response = TestClient(create_app(settings)).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "artifact_root_configured": False,
        "scenario_count": 0,
        "source_scene_count": 0,
    }


def test_catalog_detail_trajectory_and_path_safety(tmp_path: Path) -> None:
    client = _client(tmp_path)

    scenarios = client.get("/api/scenarios")
    detail = client.get("/api/scenarios/synthetic-variant-001")
    trajectory = client.get("/api/scenarios/synthetic-variant-001/trajectory")
    download = client.get("/api/artifacts/scenarios/baseline.json")
    traversal = client.get("/api/artifacts/../pyproject.toml")

    assert scenarios.status_code == 200
    assert scenarios.json()[0]["scenario_id"] == "synthetic-variant-001"
    assert detail.json()["provenance"]["dataset_name"] == "synthetic-fixture"
    assert trajectory.json()["paths"][0]["path_kind"] == "generated"
    assert trajectory.json()["map_warning"].startswith("OpenDRIVE output uses")
    assert download.status_code == 200
    assert json.loads(download.text)["artifact_type"] == "variant"
    assert traversal.status_code in {404, 400}


def test_batch_is_deterministic_and_reconciles_three_statuses(tmp_path: Path) -> None:
    client = _client(tmp_path)
    request = {
        "scenario_id": "synthetic-variant-001",
        "generation_mode": "grid",
        "speed_multipliers": [0.9, 1.0],
        "initial_gap_deltas_m": [-2.0, 0.0],
        "timing_offsets_s": [0.0, 0.25, 0.5, 0.75, 1.0],
        "seed": 7,
        "replay_enabled": True,
    }

    first_job = client.post("/api/batches", json=request)
    first = client.get(f"/api/batches/{first_job.json()['job_id']}/results")
    second_job = client.post("/api/batches", json=request)
    second = client.get(f"/api/batches/{second_job.json()['job_id']}/results")

    assert first_job.status_code == 202
    assert first.json()["job"]["status"] == "completed"
    assert first.json()["counts"] == {"generated": 20, "valid": 0, "invalid": 0, "simulator_failed": 20}
    assert first.json()["manifest"]["seed"] == 7
    assert [item["variant_id"] for item in first.json()["results"]] == [
        item["variant_id"] for item in second.json()["results"]
    ]
    assert all(item["status"] == "simulator-failed" for item in first.json()["results"])
    assert all(item["simulator_error"] for item in first.json()["results"])


def test_batch_can_surface_structured_invalid_reasons_before_ranking(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "validation_limits": {
                "road_boundary": {"min_x_m": 0.0, "max_x_m": 10.0, "min_y_m": -1.0, "max_y_m": 1.0}
            },
        },
    )
    results = client.get(f"/api/batches/{response.json()['job_id']}/results").json()
    variant_id = results["results"][0]["variant_id"]
    single = client.get(
        f"/api/batches/{response.json()['job_id']}/results/{variant_id}"
    )

    assert results["counts"] == {"generated": 1, "valid": 0, "invalid": 1, "simulator_failed": 0}
    assert results["results"][0]["ranking"] is None
    assert results["results"][0]["validation"]["reasons"][0]["code"] == "road_boundary_x"
    assert single.status_code == 200
    assert single.json()["variant_id"] == variant_id


def test_valid_batch_result_exposes_generated_trajectory_and_export(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
        },
    )
    job_id = response.json()["job_id"]
    results = client.get(f"/api/batches/{job_id}/results").json()
    valid = next(item for item in results["results"] if item["status"] == "valid")

    trajectory = client.get(
        f"/api/batches/{job_id}/results/{valid['variant_id']}/trajectory"
    )
    exported = client.post(
        f"/api/batches/{job_id}/results/{valid['variant_id']}/export"
    )

    assert trajectory.status_code == 200
    assert {path["path_kind"] for path in trajectory.json()["paths"]} == {"generated"}
    assert exported.status_code == 200
    assert any(item["kind"] == "openscenario" for item in exported.json()["artifacts"])


def test_settings_and_source_scene_import_can_use_configured_local_dataset(tmp_path: Path) -> None:
    dataset_root = Path(__file__).parents[1] / "data" / "v1.0-mini"
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "scenarios",
        output_root=tmp_path / "reports",
        dataset_root=dataset_root,
        esmini_bin=None,
        esmini_dat2csv=None,
    )
    client = TestClient(create_app(settings))

    current = client.get("/api/settings")
    scenes = client.get("/api/source-scenes")
    imported = client.post(f"/api/source-scenes/{scenes.json()[0]['scene_token']}/import", json={})
    catalog = client.get("/api/scenarios")

    assert current.status_code == 200
    assert current.json()["dataset_root_exists"] is True
    assert scenes.status_code == 200
    assert len(scenes.json()) == 10
    assert imported.status_code == 200
    assert imported.json()["scenario"]["coordinate_frame"] == "local_road_aligned"
    assert len(imported.json()["selected_actor_ids"]) >= 1
    assert any(item["scenario_id"] == imported.json()["scenario_id"] for item in catalog.json())
