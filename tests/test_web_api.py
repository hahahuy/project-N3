import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from r2s_web.app import create_app
from r2s_web.config import WebSettings
from r2s_web.adapter import ArtifactAdapter
from r2s_web.schemas import ValidationLimitsRequest
from r2s_web.jobs import BatchService
from r2s_web.schemas import BatchRequest
from real2scenario import (
    RoadAlignedTransform,
    BenchmarkRun,
    ReplayReport,
    ReplayState,
    ReplayTrace,
    State,
    aggregate_benchmark_runs,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic-variant-artifact.json"


def _client(tmp_path: Path, *, simulator_configured: bool = False) -> TestClient:
    artifact_root = tmp_path / "scenarios"
    artifact_root.mkdir()
    shutil.copy(FIXTURE, artifact_root / "baseline.json")
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=artifact_root,
        output_root=tmp_path / "reports",
        dataset_root=None,
        esmini_bin="fake-esmini" if simulator_configured else None,
        esmini_dat2csv="fake-dat2csv" if simulator_configured else None,
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
        "dataset_configured": False,
        "dataset_version": "v1.0-trainval",
        "dataset_metadata_available": False,
        "configuration": {
            "project_root": tmp_path.as_posix(),
            "artifact_root": (tmp_path / "missing").as_posix(),
            "output_root": (tmp_path / "reports").as_posix(),
            "dataset_root": None,
            "roots_present": {
                "project_root": True,
                "artifact_root": False,
                "output_root": False,
                "dataset_root": None,
            },
        },
    }


def test_health_reports_which_roots_the_stack_actually_reads(tmp_path: Path) -> None:
    """A wrong artifact root looks exactly like an empty catalog from the UI.

    Two stacks on one host can serve the same UI while reading different
    directories, so health must name every root and whether it exists rather
    than only reporting a boolean.
    """
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "scenarios",
        output_root=tmp_path / "reports",
        dataset_root=None,
        esmini_bin=None,
        esmini_dat2csv=None,
    )
    (tmp_path / "scenarios").mkdir()
    shutil.copy(FIXTURE, tmp_path / "scenarios" / "baseline.json")

    configuration = TestClient(create_app(settings)).get("/api/health").json()["configuration"]

    assert configuration["artifact_root"] == (tmp_path / "scenarios").as_posix()
    assert configuration["roots_present"]["artifact_root"] is True
    assert configuration["roots_present"]["dataset_root"] is None


def test_canvas_branch_is_session_only_and_returns_capability_boundary(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/workspace/scenarios/synthetic-variant-001/branches",
        json={
            "actor_id": "lead",
            "coordinate_frame": "local_road_aligned",
            "keyframes": [
                {"keyframe_id": "k0", "time_s": 0, "x_m": 20, "y_m": 0, "yaw_rad": 0, "speed_mps": 8},
                {"keyframe_id": "k1", "time_s": 1, "x_m": 28, "y_m": 1, "yaw_rad": 0.1, "speed_mps": 8},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["provenance"]["authoring_mode"] == "canvas_keyframes"
    assert payload["sensor_status"]["status"] == "unsupported"
    branch_id = payload["scenario"]["scenario_id"]
    assert client.get(f"/api/scenarios/{branch_id}/trajectory").status_code == 200


def test_live_esmini_capability_and_unavailable_session_are_explicit(tmp_path: Path) -> None:
    client = _client(tmp_path)
    xosc = tmp_path / "scenario.xosc"
    xodr = tmp_path / "road.xodr"
    xosc.write_text("<OpenSCENARIO version='1.1'/>")
    xodr.write_text("<OpenDRIVE revMajor='1' revMinor='6'/>")

    capability = client.get("/api/esmini/live/capability")
    created = client.post("/api/esmini/live/sessions", json={
        "scenario_id": "synthetic-variant-001",
        "xosc_path": str(xosc),
        "xodr_path": str(xodr),
        "timestep_s": 0.05,
    })

    assert capability.status_code == 200
    assert capability.json()["contract_version"] == "esmini-live-session-v1"
    assert capability.json()["available"] is False
    assert created.status_code == 200
    payload = created.json()
    assert payload["status"] == "unavailable"
    assert payload["xosc_sha256"].startswith("sha256:")
    state = client.get(f"/api/esmini/live/sessions/{payload['session_id']}")
    assert state.json()["rendering"]["screenshot_stream"] is False
    command = client.post(f"/api/esmini/live/sessions/{payload['session_id']}/commands", json={"command": "step"})
    assert command.status_code == 200
    assert command.json()["message_type"] == "command_result"


def test_sensor_evidence_is_separate_and_fails_closed_without_dataset(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/workspace/scenarios/synthetic-variant-001/sensor-evidence?nsweeps=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "nuscenes-sensor-evidence-v1"
    assert payload["channel"] == "LIDAR_TOP"
    assert payload["sweeps"] == []
    assert payload["artifact_visibility"] == "local_private"


def test_live_scenario_pair_flow_materializes_private_pair(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/esmini/live/scenario-pairs",
        json={"scenario_id": "synthetic-variant-001", "timestep_s": 0.05},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["artifacts"]["openscenario"].startswith("/api/artifacts/reports/live-pairs/")
    assert payload["artifacts"]["opendrive"].endswith("straight-two-lane-v1.xodr")
    assert (tmp_path / "reports" / "live-pairs").is_dir()


def test_wasm_pair_flow_materializes_private_pair_without_native_session(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/workspace/scenarios/synthetic-variant-001/wasm-pair")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_visibility"] == "local_private"
    assert payload["openscenario"].startswith("/api/artifacts/reports/wasm-pairs/")
    assert payload["opendrive"].endswith("straight-two-lane-v1.xodr")
    assert (tmp_path / "reports" / "wasm-pairs").is_dir()
    assert client.get(payload["openscenario"]).status_code == 200
    assert client.get(payload["opendrive"]).status_code == 200


def test_settings_fails_closed_when_dataset_directory_has_no_scene_metadata(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dataset"
    (dataset_root / "v1.0-trainval").mkdir(parents=True)
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "scenarios",
        output_root=tmp_path / "reports",
        dataset_root=dataset_root,
        esmini_bin=None,
        esmini_dat2csv=None,
    )

    response = TestClient(create_app(settings)).get("/api/settings")

    assert response.status_code == 200
    assert response.json()["source_scene_count"] == 0


def test_cp1_review_dashboard_is_read_only_and_preserves_baseline(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/cp1/review")
    payload = response.json()

    assert response.status_code == 200
    assert payload["diagnostic_status"] == "diagnostic"
    assert payload["scientific_status"] == "PROVISIONAL"
    assert payload["corridor_baseline"]["display"] == "20/143 = 13.99%"
    assert payload["corridor_baseline"]["must_remain_unchanged"] is True
    assert {item["item_id"] for item in payload["items"]} >= {
        "baseline", "sequence-evaluation", "topology", "direction", "geometry",
        "footprint", "manual-intervals", "acceptance",
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


def test_workspace_contract_exposes_metadata_layers_and_explicit_unavailability(tmp_path: Path) -> None:
    client = _client(tmp_path)

    document = client.get("/api/workspace/documents/synthetic-variant-001")
    view = client.get("/api/workspace/scenarios/synthetic-variant-001")

    assert document.status_code == 200
    assert document.json()["active_scenario_id"] == "synthetic-variant-001"
    assert document.json()["coordinate_frame"] == "local_road_aligned"
    assert document.json()["dataset"]["available"] is False
    assert document.json()["dataset"]["unavailable_reason"] == "dataset_not_configured"
    assert document.json()["native_map"] == {
        "available": False,
        "unavailable_reason": "dataset_not_configured",
    }
    assert client.get("/api/workspace/lidar/capability").json()["available"] is False
    assert view.status_code == 200
    payload = view.json()
    assert payload["layers"]["map_lanes"] == {
        "available": False,
        "unavailable_reason": "map_lane_geometry_not_available_in_current_artifact",
    }
    assert payload["layers"]["lidar"]["unavailable_reason"] == "dataset_not_configured"
    lidar = client.get("/api/workspace/scenarios/synthetic-variant-001/lidar")
    assert lidar.status_code == 200
    assert lidar.json() == {"available": False, "unavailable_reason": "dataset_not_configured"}
    assert payload["metrics"]["available"] is False
    assert all(actor["dimensions"]["available"] for actor in payload["actors"])
    assert payload["layers"]["third_person"]["available"] is True
    assert payload["layers"]["in_car"]["available"] is True


def test_workspace_internal_simulator_returns_timestamped_pov_frame(tmp_path: Path) -> None:
    client = _client(tmp_path)

    workspace = client.get("/api/workspace/scenarios/synthetic-variant-001").json()
    frame = client.get(
        "/api/workspace/scenarios/synthetic-variant-001/frames/in-car",
        params={"time_s": 0.5},
    )

    assert workspace["simulator_frames"]["available"] is True
    assert workspace["simulator_frames"]["frame_contract"] == "simulator-frame-v1"
    assert frame.status_code == 200
    payload = frame.json()
    assert payload["status"] == "rendered"
    assert payload["mode"] == "in-car"
    assert payload["simulator"] == "internal-kinematic-preview"
    assert payload["timestamp_s"] == 0.5
    assert payload["camera_transform"]["reference"] == "ego_mount"
    assert payload["provenance"]["artifact_visibility"] == "local_private"


def test_workspace_frame_interpolates_yaw_across_pi_boundary(tmp_path: Path) -> None:
    client = _client(tmp_path)
    fixture_path = tmp_path / "scenarios" / "baseline.json"
    fixture = json.loads(fixture_path.read_text())
    for actor in fixture["scenario"]["actors"]:
        actor["trajectory"] = [
            {**actor["trajectory"][0], "yaw_rad": 3.13},
            {**actor["trajectory"][1], "yaw_rad": -3.13},
        ]
    fixture["scenario"]["duration_s"] = 1.0
    fixture_path.write_text(json.dumps(fixture))

    response = client.get(
        "/api/workspace/scenarios/synthetic-variant-001/frames/in-car",
        params={"time_s": 0.5},
    )

    assert response.status_code == 200
    assert response.json()["camera_transform"]["yaw_rad"] > 3.0


def test_invalid_recipe_step_cannot_be_activated(tmp_path: Path) -> None:
    client = _client(tmp_path)
    added = client.post(
        "/api/workspace/scenarios/synthetic-variant-001/recipe/steps",
        json={
            "step_id": "invalid-step",
            "name": "Impossible braking",
            "actor_edit": {"actor_id": "ego", "braking_mps2": 100},
        },
    )
    assert added.status_code == 200
    assert added.json()["steps"][0]["status"] == "invalid"

    response = client.post(
        "/api/workspace/scenarios/synthetic-variant-001/recipe/steps/invalid-step/active",
        json={"active": True},
    )

    assert response.status_code == 409
    assert "is not valid" in response.json()["detail"]


def test_workspace_reports_variant_sensor_status_and_unavailable_image_artifact(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    sensor = client.get("/api/workspace/scenarios/synthetic-variant-001/sensor-status")
    image = client.get(
        "/api/workspace/scenarios/synthetic-variant-001/image-frames/third-person",
        params={"time_s": 0.5},
    )

    assert sensor.status_code == 200
    assert sensor.json()["contract_version"] == "workspace-variant-sensor-v1"
    assert sensor.json()["status"] == "unsupported"
    assert sensor.json()["post_edit_frames"] == {
        "available": False,
        "unavailable_reason": "post_edit_sensor_frames_not_generated",
    }
    assert sensor.json()["parent_sweep"]["available"] is False
    assert sensor.json()["parent_sweep"]["unavailable_reason"] == "dataset_not_configured"
    assert image.status_code == 200
    assert image.json()["contract_version"] == "workspace-pov-image-v1"
    assert image.json()["status"] == "unavailable"
    assert image.json()["unavailable_reason"] == "esmini_image_capture_artifact_unavailable"
    assert image.json()["artifact"] is None


def test_native_map_capability_and_queries_fail_closed_without_dataset(tmp_path: Path) -> None:
    client = _client(tmp_path)

    capability = client.get("/api/workspace/maps/singapore-onenorth/capability")
    patch = client.get(
        "/api/workspace/maps/singapore-onenorth/patch",
        params={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10, "layers": "road_segment"},
    )

    assert capability.status_code == 200
    assert capability.json()["available"] is False
    assert capability.json()["unavailable_reason"] == "dataset_not_configured"
    assert patch.status_code == 404


def test_native_map_capability_rejects_unknown_map_names(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/workspace/maps/not-a-map/capability")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert "unsupported_map_name" in response.json()["unavailable_reason"]


def test_workspace_gate_timeline_reports_backend_statuses_and_extents(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/workspace/scenarios/synthetic-variant-001/gate-timeline")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "workspace-gate-timeline-v1"
    assert payload["time_domain"] == {"start_s": 0.0, "end_s": 1.0}
    assert [gate["gate_id"] for gate in payload["gates"]] == ["G1", "G2", "G3", "G4", "G5", "G6", "G7"]
    by_id = {gate["gate_id"]: gate for gate in payload["gates"]}
    assert by_id["G1"]["status"] == "unsupported"
    assert by_id["G1"]["reasons"] == ["xosc_subset_not_evaluated_in_workspace_surface"]
    assert by_id["G2"]["status"] == "unsupported"
    assert by_id["G3"]["status"] == "skipped"
    assert by_id["G3"]["scientific_status"] == "PROVISIONAL"
    assert by_id["G5"]["status"] == "skipped"
    assert by_id["G5"]["reasons"] == ["event_definition_not_declared"]
    assert by_id["G6"]["scientific_status"] == "PROVISIONAL"
    assert all(gate["status"] != "pass" for gate in (by_id["G1"], by_id["G2"], by_id["G3"]))
    assert all(gate["start_s"] >= 0.0 and gate["end_s"] <= 1.0 for gate in payload["gates"])
    assert all(gate["extent_source"] == "scenario_time_domain" for gate in payload["gates"])
    assert sum(payload["counts"].values()) == 7
    assert payload["counts"]["unsupported"] == 2
    assert payload["provisional_count"] == 3


def test_workspace_gate_timeline_uses_a_declared_event_window(tmp_path: Path) -> None:
    client = _client(tmp_path)
    fixture = json.loads((tmp_path / "scenarios" / "baseline.json").read_text())
    fixture["scenario"]["provenance"].update(
        {
            "main_event_start_s": "0.25",
            "main_event_end_s": "0.75",
            "event_type": "longitudinal_cut_in",
            "event_target_actor_id": fixture["scenario"]["actors"][0]["actor_id"],
        }
    )
    (tmp_path / "scenarios" / "baseline.json").write_text(json.dumps(fixture))

    payload = client.get(
        "/api/workspace/scenarios/synthetic-variant-001/gate-timeline"
    ).json()

    g5 = next(gate for gate in payload["gates"] if gate["gate_id"] == "G5")
    assert g5["extent_source"] == "declared_main_event_window"
    assert (g5["start_s"], g5["end_s"]) == (0.25, 0.75)


def test_workspace_actor_timeline_is_time_indexed_and_keeps_missing_channels_empty(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get("/api/workspace/scenarios/synthetic-variant-001/timeline")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "workspace-actor-timeline-v1"
    assert payload["time_domain"] == {"start_s": 0.0, "end_s": 1.0}
    assert [track["actor_id"] for track in payload["tracks"]] == ["ego", "lead"]
    for track in payload["tracks"]:
        channels = track["channels"]
        assert channels["position"] == {
            "available": True,
            "unavailable_reason": None,
            "version": "canonical-state-v1",
            "coverage": None,
        }
        assert channels["speed"]["available"] is True
        assert channels["acceleration"]["version"] == "workspace-finite-difference-acceleration-v1"
        assert channels["braking"]["available"] is False
        assert [sample["time_s"] for sample in track["samples"]] == [0.0, 1.0]
        assert all(sample["braking_pressure"] is None for sample in track["samples"])
        assert all(sample["braking_source"] is None for sample in track["samples"])
        assert all(sample["acceleration_mps2"] == 0.0 for sample in track["samples"])
        assert all(sample["acceleration_source"] == "finite_difference" for sample in track["samples"])
    ego, other = payload["tracks"]
    assert ego["role"] == "ego"
    assert ego["channels"]["braking"]["unavailable_reason"] == "scenario_provenance_declares_no_can_scene"
    assert other["role"] == "actor"
    assert other["channels"]["braking"]["unavailable_reason"] == "recorded_brake_channel_records_ego_only"


def test_workspace_actor_timeline_reports_unsupported_braking_for_non_ego_tracks(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    fixture = json.loads((tmp_path / "scenarios" / "baseline.json").read_text())
    fixture["scenario"]["provenance"]["can_scene"] = "scene-0001"
    (tmp_path / "scenarios" / "baseline.json").write_text(json.dumps(fixture))

    payload = client.get("/api/workspace/scenarios/synthetic-variant-001/timeline").json()

    ego = payload["tracks"][0]
    other = payload["tracks"][1]
    assert ego["role"] == "ego"
    assert ego["channels"]["braking"]["unavailable_reason"] == "dataset_not_configured"
    assert other["role"] == "actor"
    assert other["channels"]["braking"]["unavailable_reason"] == "recorded_brake_channel_records_ego_only"


def test_workspace_gate_timeline_reports_error_for_malformed_event_evidence(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    fixture = json.loads((tmp_path / "scenarios" / "baseline.json").read_text())
    fixture["scenario"]["provenance"].update(
        {
            "main_event_start_s": "0.9",
            "main_event_end_s": "0.2",
            "event_type": "longitudinal_cut_in",
            "event_target_actor_id": fixture["scenario"]["actors"][0]["actor_id"],
        }
    )
    (tmp_path / "scenarios" / "baseline.json").write_text(json.dumps(fixture))

    payload = client.get("/api/workspace/scenarios/synthetic-variant-001/gate-timeline").json()

    g5 = next(gate for gate in payload["gates"] if gate["gate_id"] == "G5")
    assert g5["status"] == "error"
    assert g5["reasons"] == ["invalid_event_window"]
    assert payload["counts"]["error"] == 1


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


def test_successful_controlled_replay_exposes_aggregate_metrics_and_gates(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, simulator_configured=True)

    def fake_run_esmini(scenario_path, trace_path, config):
        trace = ReplayTrace(
            (
                ReplayState("ego", State(0.0, 0.0, 0.0, 0.0, 10.0)),
                ReplayState("ego", State(1.0, 10.0, 0.0, 0.0, 10.0)),
                ReplayState("lead", State(0.0, 20.0, 0.0, 0.0, 8.0)),
                ReplayState("lead", State(1.0, 28.0, 0.0, 0.0, 8.0)),
            )
        )
        return ReplayReport(
            command=("fake-esmini",),
            completed=True,
            timed_out=False,
            exit_code=0,
            stdout="controlled replay",
            stderr="",
            tool_version="fake-esmini-1.0",
            trace_path=Path(trace_path),
            trace=trace,
        )

    monkeypatch.setattr("r2s_web.jobs.run_esmini", fake_run_esmini)
    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "replay_enabled": True,
        },
    )
    results = client.get(f"/api/batches/{response.json()['job_id']}/results")

    assert response.status_code == 202
    payload = results.json()
    assert payload["counts"] == {"generated": 1, "valid": 1, "invalid": 0, "simulator_failed": 0}, payload
    aggregate = payload["replay_metric_aggregate"]
    assert aggregate["actor_count"] == 2
    assert aggregate["ade_m"] == {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    assert aggregate["fde_m"] == {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    variant = payload["results"][0]
    assert set(variant["replay_metrics"]) == {"ego", "lead"}
    assert {gate["gate_id"] for gate in variant["gates"]} == {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    gate_status = {gate["gate_id"]: gate["status"] for gate in variant["gates"]}
    assert gate_status == {"G1": "pass", "G2": "pass", "G3": "skipped", "G4": "pass", "G5": "skipped", "G6": "fail", "G7": "pass"}
    assert all(gate["scientific_status"] == "PROVISIONAL" for gate in variant["gates"] if gate["gate_id"] in {"G3", "G6", "G7"})
    assert payload["gate_funnel"]["generated"] == 1

    single = client.get(
        f"/api/batches/{response.json()['job_id']}/results/{variant['variant_id']}"
    )
    assert single.json()["replay_metric_aggregate"] == variant["replay_metric_aggregate"]


def test_controlled_mixed_batch_reconciles_cp4_funnel_statuses(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, simulator_configured=True)
    calls = []

    def fake_run_esmini(scenario_path, trace_path, config):
        calls.append(scenario_path)
        if len(calls) == 1:
            return ReplayReport(
                command=("fake-esmini",), completed=True, timed_out=False, exit_code=0,
                stdout="controlled success", stderr="", tool_version="fake-esmini-1.0",
                trace_path=Path(trace_path), trace=ReplayTrace((
                    ReplayState("ego", State(0.0, 0.0, 0.0, 0.0, 10.0)),
                    ReplayState("ego", State(1.0, 10.0, 0.0, 0.0, 10.0)),
                    ReplayState("lead", State(0.0, 20.0, 0.0, 0.0, 8.0)),
                    ReplayState("lead", State(1.0, 28.0, 0.0, 0.0, 8.0)),
                )),
            )
        return ReplayReport(
            command=("fake-esmini",), completed=False, timed_out=False, exit_code=7,
            stdout="", stderr="controlled failure", tool_version="fake-esmini-1.0",
            trace_path=Path(trace_path), trace=None,
        )

    monkeypatch.setattr("r2s_web.jobs.run_esmini", fake_run_esmini)
    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [-20.0, 0.0],
            "timing_offsets_s": [0.0, 0.1],
            "validation_limits": {
                "road_boundary": {"min_x_m": -1.0, "max_x_m": 20.0, "min_y_m": -1.0, "max_y_m": 1.0}
            },
            "replay_enabled": True,
        },
    )
    payload = client.get(f"/api/batches/{response.json()['job_id']}/results").json()

    assert response.status_code == 202
    assert payload["counts"] == {"generated": 4, "valid": 1, "invalid": 2, "simulator_failed": 1}
    assert {item["status"] for item in payload["results"]} == {"valid", "invalid", "simulator-failed"}
    assert len(calls) == 2
    funnel = payload["gate_funnel"]
    assert funnel["generated"] == 4
    assert funnel["pass_counts"]["G2"] == 1
    assert funnel["evaluated_counts"]["G2"] == 2
    assert funnel["scientific_status"] == "PROVISIONAL"


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


def test_preview_is_deterministic_and_behavior_is_fail_closed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    request = {
        "actor_edits": [{"actor_id": "ego", "speed_multiplier": 1.1, "heading_offset_rad": 0.1}],
        "seed": 7,
    }
    first = client.post("/api/scenarios/synthetic-variant-001/variants/preview", json=request)
    second = client.post("/api/scenarios/synthetic-variant-001/variants/preview", json=request)

    assert first.status_code == 200
    assert first.json()["variant_id"] == second.json()["variant_id"]
    assert {gate["gate_id"] for gate in first.json()["gates"]} == {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    assert all(gate["scientific_status"] == "PROVISIONAL" for gate in first.json()["gates"] if gate["gate_id"] in {"G3", "G6", "G7"})

    unsupported = client.post(
        "/api/scenarios/synthetic-variant-001/variants/preview",
        json={"actor_edits": [{"actor_id": "ego"}], "behavior": "behavior"},
    )
    assert unsupported.status_code == 200
    assert unsupported.json()["status"] == "unsupported"
    assert unsupported.json()["variant_id"] is None


def test_preview_accepts_constrained_maneuver_fields_and_rejects_displacement(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/scenarios/synthetic-variant-001/variants/preview",
        json={"recipe_steps": [{"step_id": "step-1", "name": "Brake for merge", "actor_edit": {"actor_id": "ego", "acceleration_mps2": 1.5, "braking_mps2": 0.2, "steering_angle_rad": 0.03, "target_speed_mps": 8.0, "start_time_s": 0.1, "end_time_s": 1.5}}], "actor_edits": [{"actor_id": "ego", "acceleration_mps2": 1.5, "braking_mps2": 0.2, "steering_angle_rad": 0.03, "target_speed_mps": 8.0, "start_time_s": 0.1, "end_time_s": 1.5}], "seed": 3},
    )
    rejected = client.post(
        "/api/scenarios/synthetic-variant-001/variants/preview",
        json={"actor_edits": [{"actor_id": "ego", "x_m": 4.0}], "seed": 3},
    )
    assert response.status_code == 200
    assert response.json()["configuration"]["actor_edits"][0]["target_speed_mps"] == 8.0
    assert response.json()["recipe_steps"][0]["name"] == "Brake for merge"
    assert response.json()["limits"]["silent_clamps"] == "forbidden"
    assert response.json()["provenance"]["simulator_version"] == "kinematic-open-loop-v1"
    assert response.json()["rollback_marker"]["immutable_parent"] is True
    assert rejected.status_code == 422


def test_settings_and_source_scene_import_can_use_configured_local_dataset(tmp_path: Path) -> None:
    dataset_root = Path(__file__).parents[1] / "data" / "v1.0-mini"
    if not dataset_root.is_dir():
        pytest.skip("local nuScenes v1.0-mini metadata is not available in this checkout")
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
    assert scenes.json()[0]["vehicle_candidate_count"] >= 1
    assert scenes.json()[0]["pedestrian_candidate_count"] >= 0
    assert any(item["scenario_id"] == imported.json()["scenario_id"] for item in catalog.json())


def _dataset_with_expansions() -> Path | None:
    """Return a local dataset root with map expansions, if any is present.

    Fresh clones have neither: the subset needs built artifacts and the HDD
    release is machine-local. Callers skip without them.
    """
    repo = Path(__file__).parents[1]
    for candidate in (repo / "data" / "v1.0-subset80", Path("/mnt/backup/nuscenes")):
        expansions = candidate / "maps" / "expansion"
        if expansions.is_dir() and any(expansions.glob("*.json")):
            return candidate
    return None


def test_wasm_pair_serves_scene_map_when_expansions_exist(tmp_path: Path) -> None:
    dataset_root = _dataset_with_expansions()
    if dataset_root is None:
        pytest.skip("no local dataset with map expansions is available in this checkout")
    version_file = dataset_root / "v1.0-subset80"
    version = "v1.0-subset80" if version_file.is_dir() else "v1.0-trainval"
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "scenarios",
        output_root=tmp_path / "reports",
        dataset_root=dataset_root,
        esmini_bin=None,
        esmini_dat2csv=None,
        dataset_version=version,
    )
    client = TestClient(create_app(settings))
    scenes = client.get("/api/source-scenes")
    assert scenes.status_code == 200 and len(scenes.json()) > 0
    imported = client.post(f"/api/source-scenes/{scenes.json()[0]['scene_token']}/import", json={})
    assert imported.status_code == 200
    pair = client.post(f"/api/workspace/scenarios/{imported.json()['scenario_id']}/wasm-pair")
    assert pair.status_code == 200
    payload = pair.json()
    assert payload["opendrive"].endswith(".xodr")
    assert "straight-two-lane" not in payload["opendrive"]
    assert payload["map_warning"].startswith("OpenDRIVE is a full nuScenes map")
    assert client.get(payload["openscenario"]).status_code == 200
    assert client.get(payload["opendrive"]).status_code == 200


def test_ground_layers_serve_local_frame_polygons_or_unavailable(tmp_path: Path) -> None:
    dataset_root = _dataset_with_expansions()
    if dataset_root is None:
        pytest.skip("no local dataset with map expansions is available in this checkout")
    version_file = dataset_root / "v1.0-subset80"
    version = "v1.0-subset80" if version_file.is_dir() else "v1.0-trainval"
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "scenarios",
        output_root=tmp_path / "reports",
        dataset_root=dataset_root,
        esmini_bin=None,
        esmini_dat2csv=None,
        dataset_version=version,
    )
    client = TestClient(create_app(settings))
    scenes = client.get("/api/source-scenes")
    imported = client.post(f"/api/source-scenes/{scenes.json()[0]['scene_token']}/import", json={})
    ground = client.get(f"/api/workspace/scenarios/{imported.json()['scenario_id']}/ground-layers")
    assert ground.status_code == 200
    payload = ground.json()
    assert payload["contract_version"] == "ground-layers-v1"
    assert payload["frame"] == "local_road_aligned"
    assert sum(len(layer["polygons"]) for layer in payload["layers"]) > 0
    # Correspondence: patch vertices are rebased onto the patch center before
    # the trajectory transform, so the actor bbox must sit inside drivable.
    # (Catches patch-relative vs map-global confusion — silently wrong coords.)
    scenario = client.get(f"/api/workspace/scenarios/{imported.json()['scenario_id']}").json()
    actor_xs = [s["x_m"] for p in scenario["paths"] for s in p["states"]]
    actor_ys = [s["y_m"] for p in scenario["paths"] for s in p["states"]]
    drivable = next(layer for layer in payload["layers"] if layer["name"] == "drivable_area")
    ground_xs = [x for poly in drivable["polygons"] for x, _ in poly["exterior"]]
    ground_ys = [y for poly in drivable["polygons"] for _, y in poly["exterior"]]
    assert min(ground_xs) <= min(actor_xs) and max(ground_xs) >= max(actor_xs)
    assert min(ground_ys) <= min(actor_ys) and max(ground_ys) >= max(actor_ys)
    missing = client.get("/api/workspace/scenarios/does-not-exist/ground-layers")
    assert missing.status_code == 200
    assert missing.json()["status"] == "unavailable"


def test_lidar_sweeps_span_play_range_or_unavailable(tmp_path: Path) -> None:
    dataset_root = _dataset_with_expansions()
    if dataset_root is None:
        pytest.skip("no local dataset with map expansions is available in this checkout")
    version_file = dataset_root / "v1.0-subset80"
    version = "v1.0-subset80" if version_file.is_dir() else "v1.0-trainval"
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "scenarios",
        output_root=tmp_path / "reports",
        dataset_root=dataset_root,
        esmini_bin=None,
        esmini_dat2csv=None,
        dataset_version=version,
    )
    client = TestClient(create_app(settings))
    scenes = client.get("/api/source-scenes")
    imported = client.post(f"/api/source-scenes/{scenes.json()[0]['scene_token']}/import", json={})
    response = client.get(f"/api/workspace/scenarios/{imported.json()['scenario_id']}/lidar-sweeps")
    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "nuscenes-lidar-sweeps-v1"
    sweeps = payload["sweeps"]
    # Forward walk must cover the play range, oldest first, from t=0.
    assert len(sweeps) > 1
    assert sweeps[0]["time_s"] == 0.0
    assert all(b["time_s"] > a["time_s"] for a, b in zip(sweeps, sweeps[1:]))
    assert sweeps[-1]["time_s"] > 0
    assert all(sweep["sample_data_token"] and sweep["payload_url"] for sweep in sweeps)
    missing = client.get("/api/workspace/scenarios/does-not-exist/lidar-sweeps")
    assert missing.status_code == 200
    assert missing.json()["status"] == "unavailable"


def test_completed_batch_exposes_domain_aggregate_for_benchmark_aggregation(tmp_path: Path) -> None:
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
    service = BatchService(settings, ArtifactAdapter(settings))

    status = service.create(
        BatchRequest(
            scenario_id="synthetic-variant-001",
            speed_multipliers=[1.0],
            initial_gap_deltas_m=[0.0],
            timing_offsets_s=[0.0, 0.5],
        )
    )
    record = service.get(status.job_id)

    assert status.status == "completed"
    assert record.aggregate is not None
    assert record.aggregate.parent_scenario_id == "synthetic-variant-001"
    assert record.aggregate.generated == record.counts["generated"] == 2
    assert record.aggregate.generated == (
        record.aggregate.valid + record.aggregate.invalid + record.aggregate.simulator_failed
    )
    aggregate = aggregate_benchmark_runs(
        (
            BenchmarkRun(
                run_id=status.job_id,
                scene_id="scene-synthetic",
                evidence_class="synthetic",
                simulator="none",
                report=record.aggregate,
            ),
        )
    )
    assert aggregate.status_counts["generated"] == 2
    assert aggregate.scientific_status == "PROVISIONAL"


def _lane_match_evidence(
    variant_id: str,
    *,
    matched: int = 20,
    total: int = 143,
    **overrides,
) -> dict:
    rate = matched / total
    payload = {
        "evidence_version": "lane-road-match-evidence-v1",
        "scenario_id": variant_id,
        "coordinate_frame": "local_road_aligned",
        "algorithm_version": "lane-road-match-v1",
        "config": {"max_distance_m": 0.5, "max_heading_error_rad": 0.2},
        "selected_actor_ids": ["ego", "lead"],
        "overall": {
            "state_count": total,
            "matched_state_count": matched,
            "raw_match_rate": rate,
            "provisional_95_status": (
                "at_or_above_95_percent" if rate >= 0.95 else "below_95_percent"
            ),
        },
        "diagnostic_status": "diagnostic",
        "scientific_status": "PROVISIONAL",
    }
    payload.update(overrides)
    return payload


def test_batch_evaluates_g3_only_for_candidates_with_declared_road_match_evidence(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    first = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0, 0.5],
        },
    )
    undeclared = client.get(f"/api/batches/{first.json()['job_id']}/results").json()

    assert {gate["gate_id"]: gate["status"] for gate in undeclared["results"][0]["gates"]}["G3"] == (
        "skipped"
    )

    seeded = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "lane_match_evidence": {
                undeclared["results"][0]["variant_id"]: _lane_match_evidence(
                    undeclared["results"][0]["variant_id"]
                )
            },
        },
    )
    payload = client.get(f"/api/batches/{seeded.json()['job_id']}/results").json()
    gates = {gate["gate_id"]: gate for gate in payload["results"][0]["gates"]}

    assert gates["G3"]["status"] == "fail"
    assert gates["G3"]["reasons"] == ["road_match_below_provisional_threshold"]
    assert gates["G3"]["scientific_status"] == "PROVISIONAL"
    assert gates["G3"]["observed"]["matched_state_count"] == 20
    assert payload["gate_funnel"]["evaluated_counts"]["G3"] == 1


def test_batch_rejects_road_match_evidence_for_another_candidate(tmp_path: Path) -> None:
    client = _client(tmp_path)
    baseline = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
        },
    )
    variant_id = client.get(
        f"/api/batches/{baseline.json()['job_id']}/results"
    ).json()["results"][0]["variant_id"]

    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "lane_match_evidence": {
                variant_id: _lane_match_evidence("a-different-candidate")
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "failed"
    assert "lane_match_evidence_scenario_mismatch" in response.json()["error"]


def test_batch_ignores_evidence_that_matches_no_candidate(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "lane_match_evidence": {
                "unknown-variant": _lane_match_evidence("unknown-variant")
            },
        },
    )
    payload = client.get(f"/api/batches/{response.json()['job_id']}/results").json()
    gates = {gate["gate_id"]: gate for gate in payload["results"][0]["gates"]}

    assert response.json()["status"] == "completed"
    assert gates["G3"]["status"] == "skipped"
    assert gates["G3"]["reasons"] == ["road_match_unavailable"]


def test_batch_rejects_malformed_road_match_evidence_at_the_boundary(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "lane_match_evidence": {
                "any-variant": _lane_match_evidence("any-variant", scientific_status="FINAL")
            },
        },
    )

    assert response.status_code == 422


def test_batch_cannot_override_the_provisional_road_match_reference(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "minimum_match_rate": 0.01,
        },
    )

    assert response.status_code == 422


def test_batch_records_a_declared_main_event_for_g5(tmp_path: Path) -> None:
    client = _client(tmp_path)
    baseline = client.get("/api/scenarios/synthetic-variant-001").json()

    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "event_declaration": {
                "main_event_start_s": 0.25,
                "main_event_end_s": 0.75,
                "event_type": "lead_braking",
                "event_target_actor_id": "lead",
            },
        },
    )
    job_id = response.json()["job_id"]
    payload = client.get(f"/api/batches/{job_id}/results").json()
    gates = {gate["gate_id"]: gate for gate in payload["results"][0]["gates"]}
    scenario = json.loads(
        (tmp_path / "reports" / job_id / payload["results"][0]["variant_id"] / "scenario.json").read_text()
    )

    assert gates["G5"]["status"] == "pass"
    assert gates["G5"]["observed"]["event_type"] == "lead_braking"
    assert gates["G5"]["observed"]["event_source"] == "operator_declared"
    assert scenario["scenario"]["provenance"]["main_event_start_s"] == "0.25"
    assert scenario["scenario"]["provenance"]["event_source"] == "operator_declared"
    assert "main_event_start_s" not in baseline["provenance"]


def test_batch_reports_a_malformed_event_declaration_as_a_gate_error(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "event_declaration": {
                "main_event_start_s": 5.0,
                "main_event_end_s": 6.0,
                "event_type": "lead_braking",
                "event_target_actor_id": "lead",
            },
        },
    )
    payload = client.get(f"/api/batches/{response.json()['job_id']}/results").json()
    gates = {gate["gate_id"]: gate for gate in payload["results"][0]["gates"]}

    assert gates["G5"]["status"] == "error"
    assert gates["G5"]["reasons"] == ["event_window_outside_scenario"]


def test_metric_availability_is_explicit_for_preview_and_batch_surfaces(tmp_path: Path) -> None:
    client = _client(tmp_path)
    baseline = client.get("/api/scenarios/synthetic-variant-001").json()

    preview = client.post(
        f"/api/scenarios/{baseline['scenario_id']}/variants/preview",
        json={"actor_edits": [{"actor_id": "lead", "speed_multiplier": 0.9}], "seed": 3},
    ).json()
    batch = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "replay_enabled": False,
        },
    )
    results = client.get(f"/api/batches/{batch.json()['job_id']}/results").json()

    assert preview["metrics"] == {
        "available": False,
        "unavailable_reason": "preview_has_no_simulator_trace",
        "alignment_method": None,
        "source": "none",
        "scientific_status": "PROVISIONAL",
        "provenance": {
            "coordinate_transform_version": "synthetic-transform-v1",
            "dataset_version": "v1",
            "source_scene_token": "synthetic-scene-001",
            "preview_mode": "kinematic-open-loop-v1",
        },
        "per_actor": {},
        "aggregate": None,
    }
    assert results["replay_metrics"]["available"] is False
    assert results["replay_metrics"]["unavailable_reason"] == "no_replay_trace_was_recorded"
    assert results["replay_metrics"]["aggregate"] is None


def test_metric_availability_reports_replay_metrics_when_a_trace_exists(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, simulator_configured=True)

    def fake_run_esmini(scenario_path, trace_path, config):
        return ReplayReport(
            command=("fake-esmini",),
            completed=True,
            timed_out=False,
            exit_code=0,
            stdout="controlled replay",
            stderr="",
            tool_version="fake-esmini-1.0",
            trace_path=Path(trace_path),
            trace=ReplayTrace(
                (
                    ReplayState("ego", State(0.0, 0.0, 0.0, 0.0, 10.0)),
                    ReplayState("ego", State(1.0, 10.0, 0.0, 0.0, 10.0)),
                    ReplayState("lead", State(0.0, 20.0, 0.0, 0.0, 8.0)),
                    ReplayState("lead", State(1.0, 28.0, 0.0, 0.0, 8.0)),
                )
            ),
        )

    monkeypatch.setattr("r2s_web.jobs.run_esmini", fake_run_esmini)
    batch = client.post(
        "/api/batches",
        json={
            "scenario_id": "synthetic-variant-001",
            "speed_multipliers": [1.0],
            "initial_gap_deltas_m": [0.0],
            "timing_offsets_s": [0.0],
            "replay_enabled": True,
        },
    )
    results = client.get(f"/api/batches/{batch.json()['job_id']}/results").json()

    assert results["replay_metrics"]["available"] is True
    assert results["replay_metrics"]["source"] == "replay_trace"
    assert results["replay_metrics"]["alignment_method"] == (
        "recorded_timestamps_linear_interpolation_within_overlap"
    )
    assert results["replay_metrics"]["aggregate"]["actor_count"] == 2


def test_settings_reject_artifact_root_outside_allowed_roots(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """S-2: an absolute path outside every allowed root must be rejected."""
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("classified", encoding="utf-8")
    client = _client(tmp_path)

    response = client.post("/api/settings", json={"artifact_root": str(outside)})

    assert response.status_code == 400
    assert "artifact_root must stay inside an allowed root" in response.json()["detail"]
    assert client.get("/api/artifacts/secret.txt").status_code == 404


def test_settings_reject_dataset_root_outside_allowed_roots(tmp_path: Path) -> None:
    """S-1: dataset_root must not become an arbitrary filesystem probe."""
    client = _client(tmp_path)

    for payload in (
        {"dataset_root": "/etc"},
        {"dataset_root": "/"},
        {"dataset_root": "../../etc"},
        {"output_root": "/etc"},
    ):
        response = client.post("/api/settings", json=payload)
        assert response.status_code == 400, payload
        assert "must stay inside an allowed root" in response.json()["detail"]


def test_settings_reject_symlink_escape_from_project_root(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """S-2: a symlink inside the project must not escape confinement."""
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("classified", encoding="utf-8")
    client = _client(tmp_path)
    link = tmp_path / "scenarios" / "escape"
    link.symlink_to(outside, target_is_directory=True)

    response = client.post("/api/settings", json={"artifact_root": str(link)})

    assert response.status_code == 400
    assert "must stay inside an allowed root" in response.json()["detail"]
    assert client.get("/api/artifacts/escape/secret.txt").status_code == 404


def test_settings_accept_relative_paths_inside_project_root(tmp_path: Path) -> None:
    """S-2: the documented LOCAL PATHS workflow must keep working."""
    client = _client(tmp_path)

    response = client.post(
        "/api/settings", json={"artifact_root": "scenarios", "output_root": "reports"}
    )

    assert response.status_code == 200
    assert response.json()["artifact_root"].endswith("scenarios")


def test_settings_accept_dataset_root_from_extra_allowed_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S-1: an operator-declared external dataset root stays selectable."""
    project = tmp_path / "project"
    (project / "scenarios").mkdir(parents=True)
    mounted = tmp_path / "mounted"
    (mounted / "v1.0-mini").mkdir(parents=True)
    monkeypatch.setenv("PROJECT_N3_EXTRA_DATA_ROOTS", str(mounted))
    settings = WebSettings(
        project_root=project,
        artifact_root=project / "scenarios",
        output_root=project / "reports",
        dataset_root=None,
        esmini_bin=None,
        esmini_dat2csv=None,
    )

    updated = settings.with_paths(dataset_root=str(mounted))

    assert updated.dataset_root == mounted.resolve()


def test_artifact_download_confines_to_configured_roots(tmp_path: Path) -> None:
    """The existing resolve_artifact guard must reject traversal."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("classified", encoding="utf-8")
    client = _client(tmp_path)

    response = client.get("/api/artifacts/../outside/secret.txt")

    assert response.status_code == 404


def test_trajectory_response_exposes_source_timestamps_and_record_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The web trajectory contract must expose nuScenes source provenance.

    Without these fields a consumer cannot map replay time back to nuScenes
    source time, so the UI can render a correct-looking frame while being unable
    to demonstrate the correlation scientifically.
    """
    client = _client(tmp_path)

    response = client.get("/api/scenarios/synthetic-variant-001/trajectory")

    assert response.status_code == 200
    recorded = next(
        path for path in response.json()["paths"] if path["path_kind"] != "replayed"
    )
    state = recorded["states"][0]

    # The contract must expose both fields. Values may be null for scenarios
    # whose canonical states carry no source provenance; population is covered
    # by the coordinate-transform round-trip tests.
    assert "source_timestamp_us" in state
    assert "source_record_token" in state


def test_actor_timeline_survives_present_timestamps_with_no_brake_channel(
    tmp_path: Path,
) -> None:
    """An available brake channel with no samples must degrade, not crash.

    Contract: ``_match_braking`` is called for every actor regardless of whether
    a channel resolved. When canonical states carry ``source_timestamp_us`` but
    no pedal samples exist, matching against an empty channel must yield empty
    samples. Previously the early return on absent timestamps hid this path, so
    restoring source timestamps exposed the crash.
    """
    from r2s_web.actor_timeline import _match_braking

    assert _match_braking([1_000, 2_000, 3_000], ()) == [None, None, None]


def test_top_down_state_map_layers_are_keyed_by_layer_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``map_layers`` must be a mapping, not a list of records.

    ``GroundService.full_layers`` keys its ``layers`` by layer name, but the
    endpoint used to iterate that mapping and subscript each item as if it were
    a record. Iterating a dict yields strings, so ``layer["name"]`` raised
    ``TypeError: string indices must be integers, not 'str'`` and the endpoint
    answered 500 after building the whole map. The frontend consumes
    ``Record<string, unknown>``, so the mapping is the contract.
    """
    from r2s_web.ground import GroundService
    from r2s_web.nuscenes_adapter import NuScenesDatasetAdapter
    from real2scenario import RoadAlignedTransform

    class _FakeRecordedAnnotations:
        def recorded_annotations_window(
            self, first_sample_token: str, last_sample_token: str, requested_time_s: float
        ) -> dict[str, object]:
            return {
                "requested_time_s": requested_time_s,
                "resolved_time_s": requested_time_s,
                "timestamp_us": 0,
                "sample_token": first_sample_token,
                "boxes": [],
            }

    monkeypatch.setattr(
        GroundService,
        "full_layers",
        lambda self, scenario: {
            "contract_version": "ground-full-map-v1",
            "frame": "local_road_aligned",
            "map_name": "singapore-onenorth",
            "layers": {
                "drivable_area": [
                    {"token": "t-1", "geometry": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]]}
                ],
                "lane": [],
            },
            "artifact_visibility": "local_private",
        },
    )
    monkeypatch.setattr(
        NuScenesDatasetAdapter,
        "for_dataset",
        classmethod(lambda cls, root, version: _FakeRecordedAnnotations()),
    )
    # The synthetic fixture records only the transform version, so supply the
    # origin/heading the handler needs to place recorded boxes in local frame.
    monkeypatch.setattr(
        RoadAlignedTransform,
        "from_provenance",
        classmethod(lambda cls, provenance: RoadAlignedTransform(0.0, 0.0, 0.0)),
    )

    response = _client(tmp_path).get(
        "/api/workspace/scenarios/synthetic-variant-001/top-down-state",
        params={"time_s": 0.5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "workspace-top-down-state-v1"
    assert isinstance(payload["map_layers"], dict)
    assert payload["map_layers"] == {
        "drivable_area": [
            {
                "token": "t-1",
                "exterior": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
                "holes": [],
            }
        ],
        "lane": [],
    }


def _stub_ground(monkeypatch: pytest.MonkeyPatch) -> None:
    from r2s_web.ground import GroundService

    monkeypatch.setattr(
        GroundService,
        "full_layers",
        lambda self, scenario: {
            "contract_version": "ground-full-map-v1",
            "frame": "local_road_aligned",
            "map_name": "singapore-onenorth",
            "layers": {"lane": [{"token": "t-1", "geometry": [[[0.0, 0.0], [1.0, 1.0]]]}]},
            "artifact_visibility": "local_private",
        },
    )
    monkeypatch.setattr(
        RoadAlignedTransform,
        "from_provenance",
        classmethod(lambda cls, provenance: RoadAlignedTransform(0.0, 0.0, 0.0)),
    )
    # The fixture carries no dataset, so map-name resolution cannot succeed
    # against nuScenes. The slim response must still name the scenario's map,
    # so stub the resolver the same way the geometry builder is stubbed.
    monkeypatch.setattr(
        "r2s_web.app.resolve_scene_map_name", lambda scene_token, settings: "singapore-onenorth"
    )

    class _FakeRecordedAnnotations:
        def recorded_annotations_window(
            self, first_sample_token: str, last_sample_token: str, requested_time_s: float
        ) -> dict[str, object]:
            return {
                "requested_time_s": requested_time_s,
                "resolved_time_s": requested_time_s,
                "timestamp_us": 0,
                "sample_token": first_sample_token,
                "boxes": [],
            }

    from r2s_web.nuscenes_adapter import NuScenesDatasetAdapter

    monkeypatch.setattr(
        NuScenesDatasetAdapter,
        "for_dataset",
        classmethod(lambda cls, root, version: _FakeRecordedAnnotations()),
    )


def test_top_down_map_is_served_separately_and_revalidates(tmp_path, monkeypatch) -> None:
    """The static geometry must be fetchable on its own and carry a validator.

    Playhead changes used to re-ship the whole map. Serving it once with an
    ETag lets the browser keep it, so only the per-playhead state is refetched.
    """
    _stub_ground(monkeypatch)
    client = _client(tmp_path)

    first = client.get("/api/workspace/scenarios/synthetic-variant-001/top-down-map")
    assert first.status_code == 200
    assert first.json()["layers"] == {
        "lane": [{"token": "t-1", "exterior": [[0.0, 0.0], [1.0, 1.0]], "holes": []}]
    }
    etag = first.headers["ETag"]
    assert first.headers["Cache-Control"] == "private, max-age=3600"

    revalidated = client.get(
        "/api/workspace/scenarios/synthetic-variant-001/top-down-map",
        headers={"If-None-Match": etag},
    )
    assert revalidated.status_code == 304


def test_top_down_state_can_omit_the_static_map(tmp_path, monkeypatch) -> None:
    """``include_map=false`` must drop the geometry but keep the playhead state."""
    _stub_ground(monkeypatch)
    client = _client(tmp_path)

    combined = client.get(
        "/api/workspace/scenarios/synthetic-variant-001/top-down-state",
        params={"time_s": 0.5},
    ).json()
    slim = client.get(
        "/api/workspace/scenarios/synthetic-variant-001/top-down-state",
        params={"time_s": 0.5, "include_map": "false"},
    ).json()

    # full_layers records geometry as a list of rings; the preview draws the
    # outer one, so records must expose `exterior`.
    expected = {"lane": [{"token": "t-1", "exterior": [[0.0, 0.0], [1.0, 1.0]], "holes": []}]}
    assert slim["map_layers"] == {}
    # Dropping the map must not disturb anything time-dependent.
    assert slim["actors"] == combined["actors"]
    assert slim["recorded_annotations"] == combined["recorded_annotations"]
    assert slim["map_name"] == combined["map_name"]


def test_devkit_metadata_is_shared_across_call_sites(tmp_path, monkeypatch) -> None:
    """Only one nuScenes metadata object may exist per dataset per process.

    Measured 2026-10-17: one ``NuScenes(v1.0-trainval)`` load holds ~7.74GB. The
    adapter, the artifact catalog's map-name lookup and the devkit helper each
    built their own, so the api process could hold ~23GB and the kernel
    OOM-killed the worker. All three must share a single cached instance.
    """
    from nuscenes.nuscenes import NuScenes

    from r2s_web import nuscenes_adapter

    created: list[str] = []

    def fake_init(self, version: str, dataroot: str, verbose: bool = False) -> None:
        created.append(dataroot)
        self.version = version
        self.dataroot = dataroot
        self.scene = []
        self.sample = {}

    monkeypatch.setattr(NuScenes, "__init__", fake_init)
    nuscenes_adapter._SHARED_NUSC.clear()

    adapter = nuscenes_adapter.NuScenesDatasetAdapter(tmp_path, "v1.0-trainval")
    # Three independent consumers reach for the metadata.
    adapter.nusc  # noqa: B018 - property access is the point
    nuscenes_adapter.shared_nuscenes(tmp_path, "v1.0-trainval")
    nuscenes_adapter.shared_nuscenes(tmp_path, "v1.0-trainval")

    assert len(created) == 1, f"expected one metadata load, got {len(created)}"
    assert nuscenes_adapter.shared_nuscenes_cache_size() == 1


def test_default_generation_validation_limits_allow_ten_mps2() -> None:
    """The default acceleration ceiling is 10 m/s2, not the original 5.

    Batches that omit ``validation_limits`` inherit this default, which
    ``jobs`` forwards into the feasibility limits used to raise
    ``acceleration_exceeded`` maneuver violations. It is a diagnostic ceiling:
    nothing clamps propagation to it.
    """
    assert ValidationLimitsRequest().max_acceleration_mps2 == 10.0
