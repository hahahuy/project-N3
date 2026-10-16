"""Workspace authoring contracts: recipe, rollback, lineage, compare, layers.

These tests exercise the API only.  Every value they assert is either read from
the canonical fixture artifact or computed by the backend from declared artifact
content; nothing here is a browser-side expectation.
"""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from r2s_web.app import create_app
from r2s_web.config import WebSettings


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic-variant-artifact.json"
VARIANT_ID = "synthetic-variant-001"
BASELINE_ID = "synthetic-baseline-001"


def _client(tmp_path: Path) -> TestClient:
    """Two committed artifacts: one variant with a parent, one root baseline."""
    artifact_root = tmp_path / "scenarios"
    artifact_root.mkdir()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    (artifact_root / "variant.json").write_text(
        json.dumps(fixture, sort_keys=True), encoding="utf-8"
    )
    baseline = json.loads(FIXTURE.read_text(encoding="utf-8"))
    baseline["artifact_type"] = "baseline"
    baseline.pop("variant_config")
    baseline.pop("parent_scenario_id")
    baseline["scenario"]["scenario_id"] = BASELINE_ID
    baseline["scenario"]["provenance"]["branch_name"] = "slow-leads"
    (artifact_root / "baseline.json").write_text(
        json.dumps(baseline, sort_keys=True), encoding="utf-8"
    )
    settings = WebSettings(
        project_root=tmp_path,
        artifact_root=artifact_root,
        output_root=tmp_path / "reports",
        dataset_root=None,
        esmini_bin=None,
        esmini_dat2csv=None,
    )
    return TestClient(create_app(settings))


def _step(client: TestClient, scenario_id: str, **overrides) -> dict:
    body = {
        "step_id": "step-1",
        "name": "Ease off the lead",
        "actor_edit": {
            "actor_id": "lead",
            "speed_multiplier": 0.9,
            "heading_offset_rad": 0.0,
            "timing_offset_s": 0.0,
            "initial_gap_delta_m": -1.0,
            "steering_angle_rad": 0.0,
            "start_time_s": 0.0,
            "end_time_s": 0.5,
        },
    }
    body.update(overrides)
    response = client.post(
        f"/api/workspace/scenarios/{scenario_id}/recipe/steps", json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def _step_ids(document: dict) -> list[str]:
    return [step["step_id"] for step in document["steps"]]


def _step_view(document: dict, step_id: str) -> dict:
    return next(step for step in document["steps"] if step["step_id"] == step_id)


# -- recipe ----------------------------------------------------------------


def test_recipe_document_reports_ordered_steps_and_explicit_persistence(tmp_path: Path) -> None:
    client = _client(tmp_path)

    empty = client.get(f"/api/workspace/scenarios/{VARIANT_ID}/recipe").json()

    assert empty["contract_version"] == "workspace-recipe-v1"
    assert empty["parent_immutable"] is True
    assert empty["steps"] == []
    assert empty["persistence"] == {
        "available": False,
        "unavailable_reason": "recipe_document_is_held_in_process_and_is_not_persisted_to_disk",
    }
    assert empty["history"]["undoable"] is False
    assert empty["history"]["undo_unavailable_reason"] == "no_undo_history_for_this_document"
    assert empty["limits"]["silent_clamps"] == "forbidden"
    assert empty["limits"]["max_acceleration_mps2"] == 5.0

    document = _step(client, VARIANT_ID)
    step = document["steps"][0]

    assert step["index"] == 0
    assert step["kind"] == "constrained-maneuver"
    assert step["status"] == "valid"
    assert step["active"] is True
    assert step["parameters"]["actor_id"] == "lead"
    assert step["parameters"]["end_time_s"] == 0.5
    assert step["parameters"]["speed_multiplier"] == 0.9
    assert step["violations"] == []
    assert document["active_step_count"] == 1
    assert document["history"]["revision"] == 1


def test_recipe_step_order_is_explicit_state_and_is_preserved_under_move(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    _step(client, VARIANT_ID)
    _step(client, VARIANT_ID, step_id="step-2", name="Brake for the cut-in")

    moved = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/move",
        json={"step_id": "step-2", "direction": "up"},
    ).json()
    assert _step_ids(moved) == ["step-2", "step-1"]
    assert [step["index"] for step in moved["steps"]] == [0, 1]

    back = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/move",
        json={"step_id": "step-2", "direction": "down"},
    ).json()
    assert _step_ids(back) == ["step-1", "step-2"]

    edge = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/move",
        json={"step_id": "step-1", "direction": "up"},
    )
    assert edge.status_code == 409
    assert "recipe edge" in edge.json()["detail"]


def test_recipe_step_status_names_limits_and_rejected_edits(tmp_path: Path) -> None:
    client = _client(tmp_path)

    over_limit = _step(
        client,
        VARIANT_ID,
        step_id="step-fast",
        name="Impossible braking",
        actor_edit={
            "actor_id": "lead",
            "speed_multiplier": 1.0,
            "heading_offset_rad": 0.0,
            "timing_offset_s": 0.0,
            "initial_gap_delta_m": 0.0,
            "braking_mps2": 12.0,
        },
    )
    step = over_limit["steps"][0]
    assert step["status"] == "invalid"
    assert step["active"] is False
    assert step["inactive_reason"] == "parameter_limit_exceeded"
    assert step["violations"] == [
        {
            "code": "deceleration_exceeded",
            "actor_id": "lead",
            "observed": 12.0,
            "limit": 8.0,
            "provenance": "kinematic-open-loop-v1",
        }
    ]

    unknown_actor = _step(
        client,
        VARIANT_ID,
        step_id="step-ghost",
        name="Move an absent actor",
        actor_edit={
            "actor_id": "not-in-this-scenario",
            "speed_multiplier": 1.0,
            "heading_offset_rad": 0.0,
            "timing_offset_s": 0.0,
            "initial_gap_delta_m": 0.0,
        },
    )
    ghost = _step_view(unknown_actor, "step-ghost")
    assert ghost["status"] == "error"
    assert ghost["error"] == "actor_is_not_present_in_this_scenario:not-in-this-scenario"
    assert ghost["active"] is False

    reversed_window = _step(
        client,
        VARIANT_ID,
        step_id="step-window",
        name="End before start",
        actor_edit={
            "actor_id": "ego",
            "speed_multiplier": 1.0,
            "heading_offset_rad": 0.0,
            "timing_offset_s": 0.0,
            "initial_gap_delta_m": 0.0,
            "start_time_s": 0.8,
            "end_time_s": 0.2,
        },
    )
    window_step = _step_view(reversed_window, "step-window")
    assert window_step["status"] == "error"
    assert window_step["error"] == "end_time_s_must_not_precede_start_time_s"


def test_duplicate_and_unknown_recipe_steps_are_reported_not_overwritten(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    _step(client, VARIANT_ID)

    duplicate = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps",
        json={
            "step_id": "step-1",
            "name": "Duplicate",
            "actor_edit": {
                "actor_id": "ego",
                "speed_multiplier": 1.0,
                "heading_offset_rad": 0.0,
                "timing_offset_s": 0.0,
                "initial_gap_delta_m": 0.0,
            },
        },
    )
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]

    missing = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/absent/remove"
    )
    assert missing.status_code == 404
    assert "was not found" in missing.json()["detail"]


def test_deactivated_steps_stay_in_the_recipe_with_their_parameters(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _step(client, VARIANT_ID)

    response = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/step-1/active",
        json={"active": False},
    )

    assert response.status_code == 200
    document = response.json()
    assert document["step_count"] == 1
    assert document["active_step_count"] == 0
    step = document["steps"][0]
    assert step["active"] is False
    assert step["inactive_reason"] == "operator_deactivated_this_step"
    assert step["parameters"]["speed_multiplier"] == 0.9

    reactivated = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/step-1/active",
        json={"active": True},
    ).json()
    assert reactivated["steps"][0]["active"] is True
    assert reactivated["steps"][0]["inactive_reason"] is None


def test_rollback_marker_truncates_and_marks_later_steps_inactive(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _step(client, VARIANT_ID)
    marked = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/markers",
        json={"name": "before the cut-in"},
    ).json()
    marker_id = marked["rollback_markers"][0]["marker_id"]
    assert marked["rollback_markers"][0]["step_count"] == 1
    assert marked["active_marker_id"] == marker_id

    _step(client, VARIANT_ID, step_id="step-2", name="Second pass")
    assert _step_ids(client.get(f"/api/workspace/scenarios/{VARIANT_ID}/recipe").json()) == [
        "step-1",
        "step-2",
    ]

    restored = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/markers/{marker_id}/restore"
    ).json()
    assert _step_ids(restored) == ["step-1", "step-2"]
    trailing = restored["steps"][1]
    assert trailing["active"] is False
    assert trailing["inactive_reason"] == "after_active_rollback_marker"
    assert restored["active_step_count"] == 1
    assert restored["active_marker_id"] == marker_id

    blocked = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/step-2/active",
        json={"active": True},
    )
    assert blocked.status_code == 409
    assert "after the active rollback marker" in blocked.json()["detail"]


def test_undo_and_redo_are_non_destructive_and_leave_the_artifact_untouched(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    artifact = tmp_path / "scenarios" / "variant.json"
    before = artifact.read_bytes()
    _step(client, VARIANT_ID)
    _step(client, VARIANT_ID, step_id="step-2", name="Second pass")

    removed = client.post(
        f"/api/workspace/scenarios/{VARIANT_ID}/recipe/steps/step-1/remove"
    ).json()
    assert _step_ids(removed) == ["step-2"]

    undone = client.post(f"/api/workspace/scenarios/{VARIANT_ID}/recipe/undo").json()
    assert _step_ids(undone) == ["step-1", "step-2"]
    assert undone["steps"][0]["parameters"]["speed_multiplier"] == 0.9
    assert undone["history"]["redoable"] is True

    redone = client.post(f"/api/workspace/scenarios/{VARIANT_ID}/recipe/redo").json()
    assert _step_ids(redone) == ["step-2"]
    assert redone["history"]["redo_unavailable_reason"] == "no_redo_history_for_this_document"

    assert artifact.read_bytes() == before
    scenario = client.get(f"/api/workspace/scenarios/{VARIANT_ID}").json()
    assert scenario["scenario"]["scenario_id"] == VARIANT_ID
    assert scenario["scenario"]["provenance"]["source_scene_token"] == "synthetic-scene-001"
    assert list((tmp_path / "scenarios").glob("*")) == [
        tmp_path / "scenarios" / "baseline.json",
        tmp_path / "scenarios" / "variant.json",
    ]
    assert redone["parent_immutable"] is True
    assert redone["history"]["non_destructive"] is True

    exhausted = client.post(f"/api/workspace/scenarios/{VARIANT_ID}/recipe/redo")
    assert exhausted.status_code == 409
    assert exhausted.json()["detail"] == "no_redo_history_for_this_document"


def test_recipe_documents_are_per_scenario_and_unknown_scenarios_fail(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _step(client, VARIANT_ID)

    other = client.get(f"/api/workspace/scenarios/{BASELINE_ID}/recipe").json()
    assert other["steps"] == []
    assert other["parent_scenario_id"] is None

    missing = client.get("/api/workspace/scenarios/absent/recipe")
    assert missing.status_code == 404
    assert "was not found" in missing.json()["detail"]


# -- lineage ---------------------------------------------------------------


def test_variant_lineage_reports_branch_identity_seed_and_config_hash(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    variant = client.get(f"/api/workspace/scenarios/{VARIANT_ID}/lineage").json()
    baseline = client.get(f"/api/workspace/scenarios/{BASELINE_ID}/lineage").json()

    assert variant["contract_version"] == "workspace-variant-lineage-v1"
    assert variant["fields"]["parent_scenario_id"] == BASELINE_ID
    assert variant["fields"]["seed"] == 7
    assert variant["fields"]["variant_configuration"] == {
        "speed_multiplier": 1.1,
        "initial_gap_delta_m": -2.0,
        "timing_offset_s": 0.25,
        "seed": 7,
    }
    assert variant["fields"]["config_hash"].startswith("sha256:")
    assert variant["unavailable_reasons"]["config_hash"] is None
    assert variant["unavailable_reasons"]["seed"] is None
    assert variant["branch"] == {
        "branch_id": "branch-synthetic-baseline-001",
        "branch_name": None,
        "root_scenario_id": BASELINE_ID,
        "branch_id_source": "lineage_root_scenario_id",
        "branch_name_source": None,
        "branch_name_unavailable_reason": "scenario_provenance_declares_no_branch_name",
    }
    assert variant["child_scenario_ids"] == []
    assert baseline["child_scenario_ids"] == [VARIANT_ID]
    assert [node["present"] for node in variant["lineage_path"]] == [True, True]

    assert baseline["artifact_type"] == "baseline"
    assert baseline["fields"]["parent_scenario_id"] is None
    assert baseline["unavailable_reasons"]["parent_scenario_id"] == (
        "artifact_is_a_root_baseline_document"
    )
    assert baseline["fields"]["seed"] is None
    assert baseline["fields"]["config_hash"] is None
    assert baseline["unavailable_reasons"]["config_hash"] == (
        "artifact_declares_no_variant_configuration"
    )
    assert baseline["branch"]["branch_name"] == "slow-leads"
    assert baseline["branch"]["branch_name_source"] == "scenario_provenance"
    assert baseline["lineage_depth"] == 0

    assert (
        client.get("/api/workspace/scenarios/absent/lineage").status_code == 404
    )


def test_lineage_flags_a_declared_parent_that_is_not_present(tmp_path: Path) -> None:
    client = _client(tmp_path)

    lineage = client.get(f"/api/workspace/scenarios/{VARIANT_ID}/lineage").json()
    (tmp_path / "scenarios" / "baseline.json").unlink()

    orphaned = client.get(f"/api/workspace/scenarios/{VARIANT_ID}/lineage").json()
    assert orphaned["lineage_path"][0] == {
        "scenario_id": BASELINE_ID,
        "artifact_type": "unknown",
        "present": False,
        "unavailable_reason": "parent_artifact_is_not_present_in_the_artifact_root",
    }
    assert lineage["lineage_path"][0]["present"] is True


# -- evidence layers -------------------------------------------------------


def test_evidence_layers_separate_recorded_generated_replayed_and_sensor(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    variant = client.get(f"/api/workspace/scenarios/{VARIANT_ID}/evidence-layers").json()
    baseline = client.get(f"/api/workspace/scenarios/{BASELINE_ID}/evidence-layers").json()

    assert variant["contract_version"] == "workspace-evidence-layers-v1"
    assert [layer["layer"] for layer in variant["layers"]] == [
        "recorded",
        "generated",
        "replayed",
        "sensor-evidence",
    ]
    by_layer = {layer["layer"]: layer for layer in variant["layers"]}
    assert by_layer["recorded"]["status"] == "available"
    assert by_layer["recorded"]["source"] == "canonical-scenario-trajectory-v1"
    assert by_layer["generated"]["status"] == "available"
    assert by_layer["generated"]["source"] == "variant-artifact-trajectory-v1"
    assert by_layer["replayed"]["status"] == "unavailable"
    assert by_layer["replayed"]["unavailable_reason"] == (
        "replay_trace_artifact_absent_for_this_scenario"
    )
    assert by_layer["sensor-evidence"]["status"] == "unsupported"
    assert by_layer["sensor-evidence"]["unavailable_reason"] == (
        "post_edit_sensor_frames_are_not_generated_for_a_variant"
    )
    assert by_layer["sensor-evidence"]["parent_fallback"]["parent_scenario_id"] == BASELINE_ID
    assert by_layer["sensor-evidence"]["parent_fallback"]["available"] is False
    assert by_layer["sensor-evidence"]["parent_fallback"]["unavailable_reason"] == (
        "dataset_not_configured"
    )
    assert variant["available_count"] == 2

    baseline_layers = {layer["layer"]: layer for layer in baseline["layers"]}
    assert baseline_layers["generated"]["status"] == "unavailable"
    assert baseline_layers["generated"]["unavailable_reason"] == (
        "generated_trajectory_requires_a_variant_artifact"
    )
    assert baseline_layers["sensor-evidence"]["status"] == "unavailable"
    assert baseline_layers["sensor-evidence"]["unavailable_reason"] == "dataset_not_configured"
    assert baseline_layers["sensor-evidence"]["parent_fallback"] is None
    assert baseline["available_count"] == 1


def test_replay_trace_artifact_makes_the_replayed_layer_available(tmp_path: Path) -> None:
    client = _client(tmp_path)
    trace = {
        "scenario_id": VARIANT_ID,
        "states": [
            {
                "actor_id": "ego",
                "state": {
                    "time_s": 0.0,
                    "x_m": 0.0,
                    "y_m": 0.0,
                    "yaw_rad": 0.0,
                    "speed_mps": 10.0,
                },
            }
        ],
    }
    (tmp_path / "scenarios" / "variant.replay.json").write_text(
        json.dumps(trace), encoding="utf-8"
    )

    payload = client.get(f"/api/workspace/scenarios/{VARIANT_ID}/evidence-layers").json()
    replayed = next(layer for layer in payload["layers"] if layer["layer"] == "replayed")

    assert replayed["status"] == "available"
    assert replayed["provenance"]["replay_artifact"] == "scenarios/variant.replay.json"
    assert replayed["provenance"]["metric_status"] == (
        "replay_alignment_metrics_are_provisional"
    )
    assert payload["available_count"] == 3


def test_workspace_scenario_payload_carries_metric_provenance_and_layers(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    payload = client.get(f"/api/workspace/scenarios/{VARIANT_ID}").json()

    assert payload["metrics"] == {
        "available": False,
        "unavailable_reason": "replay_trace_not_available",
        "alignment_method": None,
        "source": "none",
        "scientific_status": "PROVISIONAL",
        "provenance": {
            "dataset_version": "v1",
            "source_scene_token": "synthetic-scene-001",
            "coordinate_transform_version": "synthetic-transform-v1",
        },
        "per_actor": {},
        "aggregate": None,
    }
    assert payload["evidence_layers"]["contract_version"] == "workspace-evidence-layers-v1"


# -- compare ---------------------------------------------------------------


def test_compare_synchronizes_scenario_time_and_reports_both_sides(tmp_path: Path) -> None:
    client = _client(tmp_path)

    payload = client.get(
        f"/api/workspace/scenarios/{VARIANT_ID}/compare",
        params={"against": BASELINE_ID, "time_s": 0.5},
    ).json()

    assert payload["contract_version"] == "workspace-compare-v1"
    assert payload["synchronization"] == {
        "mode": "scenario_time",
        "time_s": 0.5,
        "requested_time_s": 0.5,
        "time_domain": {"start_s": 0.0, "end_s": 1.0},
        "left_duration_s": 1.0,
        "right_duration_s": 1.0,
        "durations_differ": False,
        "duration_unavailable_reason": None,
        "reference_point": "scenario_time_origin",
    }
    left, right = payload["sides"]
    assert left["scenario_id"] == VARIANT_ID
    assert left["seed"] == 7
    assert left["config_hash"].startswith("sha256:")
    assert right["seed"] is None
    assert right["config_hash"] is None
    assert left["layer_kinds"] == ["recorded", "generated"]
    assert right["layer_kinds"] == ["recorded"]

    actors = {row["actor_id"]: row for row in payload["actors"]}
    assert set(actors) == {"ego", "lead"}
    ego = actors["ego"]
    assert ego["left"]["status"] == "measured"
    assert ego["left"]["x_m"] == 0.0
    assert ego["right"]["status"] == "measured"
    assert ego["position_delta_m"] == 0.0
    assert ego["speed_delta_mps"] == 0.0
    assert actors["lead"]["role"] == "actor"

    for row in payload["metrics"]:
        assert row["left_status"] == "unavailable"
        assert row["left_value"] is None
        assert row["delta"] is None
        assert row["delta_unavailable_reason"] == "replay_trace_not_available"
        assert row["scientific_status"] == "PROVISIONAL"
    assert payload["metric_scientific_status"] == "PROVISIONAL"
    assert payload["metric_provenance"]["left"]["source_scene_token"] == (
        "synthetic-scene-001"
    )
    assert payload["metric_provenance"]["right"]["unavailable_reason"] == (
        "replay_trace_not_available"
    )

    gates = {row["gate_id"]: row for row in payload["gates"]}
    assert set(gates) == {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    assert all(row["differs"] is False for row in gates.values())
    assert gates["G3"]["left_scientific_status"] == "PROVISIONAL"


def test_compare_reports_actors_and_state_it_cannot_resolve(tmp_path: Path) -> None:
    client = _client(tmp_path)
    baseline = json.loads(FIXTURE.read_text(encoding="utf-8"))
    baseline["artifact_type"] = "baseline"
    baseline.pop("variant_config")
    baseline.pop("parent_scenario_id")
    baseline["scenario"]["scenario_id"] = BASELINE_ID
    baseline["scenario"]["actors"] = [
        actor for actor in baseline["scenario"]["actors"] if actor["actor_id"] == "ego"
    ]
    baseline["scenario"]["ego_actor_id"] = "ego"
    (tmp_path / "scenarios" / "baseline.json").write_text(
        json.dumps(baseline, sort_keys=True), encoding="utf-8"
    )

    payload = client.get(
        f"/api/workspace/scenarios/{VARIANT_ID}/compare",
        params={"against": BASELINE_ID, "time_s": 5.0},
    ).json()

    assert payload["synchronization"]["time_s"] == 1.0
    actors = {row["actor_id"]: row for row in payload["actors"]}
    assert actors["lead"]["right"]["status"] == "unavailable"
    assert actors["lead"]["right"]["unavailable_reason"] == (
        "actor_is_absent_from_this_side"
    )
    assert actors["lead"]["position_delta_m"] is None
    assert actors["lead"]["delta_unavailable_reason"] == "actor_is_absent_from_this_side"


def test_compare_rejects_one_sided_or_unknown_documents(tmp_path: Path) -> None:
    client = _client(tmp_path)

    same = client.get(
        f"/api/workspace/scenarios/{VARIANT_ID}/compare",
        params={"against": VARIANT_ID},
    )
    unknown = client.get(
        f"/api/workspace/scenarios/{VARIANT_ID}/compare",
        params={"against": "absent"},
    )

    assert same.status_code == 422
    assert same.json()["detail"] == "compare_requires_two_different_scenarios"
    assert unknown.status_code == 404
    assert "was not found" in unknown.json()["detail"]


@pytest.mark.parametrize(
    "route",
    [
        "/api/workspace/scenarios/{id}/lineage",
        "/api/workspace/scenarios/{id}/evidence-layers",
        "/api/workspace/scenarios/{id}/recipe",
    ],
)
def test_workspace_authoring_routes_fail_closed_for_unknown_scenarios(
    tmp_path: Path, route: str
) -> None:
    client = _client(tmp_path)

    response = client.get(route.format(id="absent"))

    assert response.status_code == 404
    assert "absent" in response.json()["detail"]