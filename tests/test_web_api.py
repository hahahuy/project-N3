import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from r2s_web.app import create_app
from r2s_web.config import WebSettings
from r2s_web.adapter import ArtifactAdapter
from r2s_web.jobs import BatchService
from r2s_web.schemas import BatchRequest
from real2scenario import (
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
        "source_scene_count": 0,
    }


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
    assert any(item["scenario_id"] == imported.json()["scenario_id"] for item in catalog.json())


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
