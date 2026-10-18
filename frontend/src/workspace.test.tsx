// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const SCENARIO_ID = "scene-timeline-001";
const DURATION_S = 2;

const scenarioSummary = {
  scenario_id: SCENARIO_ID,
  parent_scenario_id: null,
  artifact_type: "baseline",
  duration_s: DURATION_S,
  coordinate_frame: "local_road_aligned",
  actors: [{ actor_id: "ego", actor_type: "vehicle.ego", sample_count: 3, length_m: null, width_m: null }],
  provenance: { dataset_name: "synthetic-fixture" },
  available_artifacts: [],
};

const trajectories = [
  { time_s: 0, x_m: 0, y_m: 0, yaw_rad: 0, speed_mps: 4 },
  { time_s: 1, x_m: 5, y_m: 0, yaw_rad: 0.1, speed_mps: 6 },
  { time_s: 2, x_m: 10, y_m: 2, yaw_rad: 0.4, speed_mps: 7 },
];

const actorTimeline = {
  contract_version: "workspace-actor-timeline-v1",
  scenario_id: SCENARIO_ID,
  coordinate_frame: "local_road_aligned",
  time_domain: { start_s: 0, end_s: DURATION_S },
  artifact_visibility: "local_private",
  tracks: [
    {
      actor_id: "ego",
      actor_type: "vehicle.ego",
      role: "ego",
      channels: {
        position: { available: true, unavailable_reason: null, version: "canonical-state-v1", coverage: null },
        heading: { available: true, unavailable_reason: null, version: "canonical-state-v1", coverage: null },
        speed: { available: true, unavailable_reason: null, version: "canonical-state-v1", coverage: null },
        acceleration: { available: true, unavailable_reason: null, version: "workspace-finite-difference-acceleration-v1", coverage: 1 },
        braking: { available: false, unavailable_reason: "recorded_brake_channel_records_ego_only", version: "nuscenes-can-vehicle-monitor-v1", coverage: 0 },
      },
      samples: [
        { ...trajectories[0], acceleration_mps2: 1.5, acceleration_source: "finite_difference", braking_pressure: null, braking_source: null },
        { ...trajectories[1], acceleration_mps2: null, acceleration_source: null, braking_pressure: null, braking_source: null },
        { ...trajectories[2], acceleration_mps2: -2.25, acceleration_source: "finite_difference", braking_pressure: null, braking_source: null },
      ],
    },
    {
      actor_id: "lead",
      actor_type: "vehicle",
      role: "actor",
      channels: {
        position: { available: true, unavailable_reason: null, version: "canonical-state-v1", coverage: null },
        heading: { available: true, unavailable_reason: null, version: "canonical-state-v1", coverage: null },
        speed: { available: true, unavailable_reason: null, version: "canonical-state-v1", coverage: null },
        acceleration: { available: false, unavailable_reason: "insufficient_states_for_finite_difference", version: "workspace-finite-difference-acceleration-v1", coverage: 0 },
        braking: { available: false, unavailable_reason: "recorded_brake_channel_records_ego_only", version: "nuscenes-can-vehicle-monitor-v1", coverage: 0 },
      },
      samples: [
        { ...trajectories[0], x_m: 20, y_m: 0, acceleration_mps2: null, acceleration_source: null, braking_pressure: null, braking_source: null },
        { ...trajectories[1], x_m: 25, y_m: 1, acceleration_mps2: null, acceleration_source: null, braking_pressure: null, braking_source: null },
        { ...trajectories[2], x_m: 30, y_m: 3, acceleration_mps2: null, acceleration_source: null, braking_pressure: null, braking_source: null },
      ],
    },
  ],
};

const gateTimeline = {
  contract_version: "workspace-gate-timeline-v1",
  scenario_id: SCENARIO_ID,
  coordinate_frame: "local_road_aligned",
  time_domain: { start_s: 0, end_s: DURATION_S },
  artifact_visibility: "local_private",
  provisional_count: 2,
  counts: { pass: 2, fail: 1, skipped: 2, error: 1, unsupported: 1 },
  gates: [
    { gate_id: "G1", status: "unsupported", scientific_status: "not-applicable", reasons: ["xosc_subset_not_evaluated_in_workspace_surface"], config_version: "xosc-schema-v1", observed: null, start_s: 0, end_s: 2, extent_source: "scenario_time_domain" },
    { gate_id: "G2", status: "skipped", scientific_status: "not-applicable", reasons: ["simulator_replay_not_recorded_for_this_scenario"], config_version: "simulator-completion-v1", observed: null, start_s: 0, end_s: 2, extent_source: "scenario_time_domain" },
    { gate_id: "G3", status: "skipped", scientific_status: "PROVISIONAL", reasons: ["lane_road_match_evidence_not_supplied_for_this_scenario"], config_version: "lane-road-match-v1", observed: null, start_s: 0, end_s: 2, extent_source: "scenario_time_domain" },
    { gate_id: "G4", status: "pass", scientific_status: "not-applicable", reasons: [], config_version: "feasibility-v0", observed: { reason_count: 0 }, start_s: 0, end_s: 2, extent_source: "scenario_time_domain" },
    { gate_id: "G5", status: "error", scientific_status: "not-applicable", reasons: ["invalid_event_window"], config_version: null, observed: null, start_s: 0, end_s: 2, extent_source: "scenario_time_domain" },
    { gate_id: "G6", status: "fail", scientific_status: "PROVISIONAL", reasons: ["rare_threshold_not_reached"], config_version: "rare-event-v0-provisional", observed: { minimum_ttc_s: 3.2 }, start_s: 0, end_s: 2, extent_source: "scenario_time_domain" },
    { gate_id: "G7", status: "pass", scientific_status: "PROVISIONAL", reasons: [], config_version: "diversity-v0-provisional", observed: { distance: null }, start_s: 0, end_s: 2, extent_source: "scenario_time_domain" },
  ],
};

const povFrame = {
  contract_version: "simulator-frame-v1",
  frame_id: "frame-t0000",
  mode: "third-person",
  status: "rendered",
  simulator: "internal-kinematic-preview",
  simulator_version: "kinematic-open-loop-v1",
  timestamp_s: 0,
  coordinate_frame: "local_road_aligned",
  transform_version: "local-road-aligned-v1",
  camera_transform: { x_m: "0", y_m: "0" },
  actors: [{ actor_id: "ego", actor_type: "vehicle.ego", transform: { x_m: 0, y_m: 0 }, speed_mps: 4, dimensions: { length_m: null, width_m: null } }],
  provenance: { artifact_visibility: "local_private" },
};


const secondScenarioId = "scene-timeline-002";

const secondScenarioSummary = { ...scenarioSummary, scenario_id: secondScenarioId, parent_scenario_id: SCENARIO_ID, artifact_type: "variant", provenance: { dataset_name: "synthetic-fixture", branch_name: "slow-leads" } };

const recipeDocument = {
  contract_version: "workspace-recipe-v1",
  scenario_id: SCENARIO_ID,
  coordinate_frame: "local_road_aligned",
  parent_scenario_id: secondScenarioId,
  parent_immutable: true,
  mutation: "workspace-recipe-store",
  persistence: { available: false, unavailable_reason: "recipe_document_is_held_in_process_and_is_not_persisted_to_disk" },
  limits: { version: "kinematic-limits-v1", simulator: "kinematic-open-loop-v1", max_acceleration_mps2: 5, max_deceleration_mps2: 8, max_yaw_rate_radps: 1.5, silent_clamps: "forbidden" },
  step_count: 2,
  active_step_count: 1,
  rollback_markers: [{ marker_id: "marker-1", name: "before the cut-in", step_count: 1, revision: 2 }],
  active_marker_id: "marker-1",
  history: { revision: 4, undo_depth: 4, redo_depth: 0, non_destructive: true, undoable: true, redoable: false, undo_unavailable_reason: null, redo_unavailable_reason: "no_redo_history_for_this_document" },
  steps: [
    {
      index: 0,
      step_id: "step-1",
      name: "Ease off the lead",
      kind: "constrained-maneuver",
      status: "valid",
      active: true,
      inactive_reason: null,
      parameters: { actor_id: "lead", speed_multiplier: 0.9, heading_offset_rad: 0, timing_offset_s: 0, initial_gap_delta_m: -1, steering_angle_rad: 0, acceleration_mps2: null, braking_mps2: 2, target_speed_mps: null, start_time_s: 0, end_time_s: 1 },
      violations: [],
      error: null,
    },
    {
      index: 1,
      step_id: "step-2",
      name: "Impossible braking",
      kind: "constrained-maneuver",
      status: "invalid",
      active: false,
      inactive_reason: "after_active_rollback_marker",
      parameters: { actor_id: "ego", speed_multiplier: 1, heading_offset_rad: 0, timing_offset_s: 0, initial_gap_delta_m: 0, steering_angle_rad: 0, acceleration_mps2: null, braking_mps2: 12, target_speed_mps: null, start_time_s: 0, end_time_s: null },
      violations: [{ code: "deceleration_exceeded", actor_id: "ego", observed: 12, limit: 8, provenance: "kinematic-open-loop-v1" }],
      error: null,
    },
  ],
};

const lineage = {
  contract_version: "workspace-variant-lineage-v1",
  scenario_id: SCENARIO_ID,
  artifact_type: "baseline",
  artifact_path: "scenarios/baseline.json",
  coordinate_frame: "local_road_aligned",
  lineage_path: [
    { scenario_id: "synthetic-root", artifact_type: "baseline", present: true, unavailable_reason: null },
    { scenario_id: SCENARIO_ID, artifact_type: "baseline", present: true, unavailable_reason: null },
  ],
  lineage_depth: 1,
  branch: { branch_id: "branch-synthetic-root", branch_name: null, root_scenario_id: "synthetic-root", branch_id_source: "lineage_root_scenario_id", branch_name_source: null, branch_name_unavailable_reason: "scenario_provenance_declares_no_branch_name" },
  child_scenario_ids: [SCENARIO_ID],
  fields: {
    parent_scenario_id: "synthetic-root",
    branch_id: "branch-synthetic-root",
    branch_name: null,
    seed: 7,
    config_hash: "sha256:0123456789abcdef",
    run_id: null,
    variant_configuration: { speed_multiplier: 1.1, initial_gap_delta_m: -2, timing_offset_s: 0.25, seed: 7 },
    dataset_version: "v1",
    generator_version: "real2scenario-test-v1",
    transform_version: "local-road-aligned-v1",
    source_scene_token: "synthetic-scene-001",
  },
  unavailable_reasons: {
    parent_scenario_id: null,
    branch_id: null,
    branch_name: "scenario_provenance_declares_no_branch_name",
    seed: null,
    config_hash: null,
    run_id: "scenario_provenance_declares_no_run_id",
    variant_configuration: null,
    dataset_version: null,
    generator_version: null,
    transform_version: null,
    source_scene_token: null,
  },
  provenance: { dataset_name: "synthetic-fixture" },
  artifact_visibility: "local_private",
};

const evidenceLayers = {
  contract_version: "workspace-evidence-layers-v1",
  scenario_id: SCENARIO_ID,
  coordinate_frame: "local_road_aligned",
  available_count: 2,
  artifact_visibility: "local_private",
  layers: [
    { layer: "recorded", status: "available", unavailable_reason: null, source: "canonical-scenario-trajectory-v1", scientific_status: "PROVISIONAL", provenance: { dataset_version: "v1" }, coverage: 1, reference: "/api/scenarios/x/trajectory", parent_fallback: null },
    { layer: "generated", status: "unavailable", unavailable_reason: "generated_trajectory_requires_a_variant_artifact", source: "variant-artifact-trajectory-v1", scientific_status: "PROVISIONAL", provenance: {}, coverage: null, reference: "/api/scenarios/x/trajectory", parent_fallback: null },
    { layer: "replayed", status: "unavailable", unavailable_reason: "replay_trace_artifact_absent_for_this_scenario", source: "simulator-replay-trace-v1", scientific_status: "PROVISIONAL", provenance: {}, coverage: null, reference: "/api/scenarios/x/trajectory", parent_fallback: null },
    { layer: "sensor-evidence", status: "unavailable", unavailable_reason: "dataset_not_configured", source: "recorded-lidar-top-sweep-v1", scientific_status: "PROVISIONAL", provenance: {}, coverage: null, reference: "/api/workspace/scenarios/x/lidar", parent_fallback: null },
  ],
};

const comparePayload = {
  contract_version: "workspace-compare-v1",
  synchronization: {
    mode: "scenario_time",
    time_s: 1,
    requested_time_s: 1,
    time_domain: { start_s: 0, end_s: 2 },
    left_duration_s: 2,
    right_duration_s: 2,
    durations_differ: false,
    duration_unavailable_reason: null,
    reference_point: "scenario_time_origin",
  },
  sides: [
    { scenario_id: SCENARIO_ID, artifact_type: "baseline", parent_scenario_id: null, branch_id: "branch-synthetic-root", branch_name: null, seed: 7, config_hash: "sha256:0123456789abcdef", coordinate_frame: "local_road_aligned", duration_s: 2, layer_kinds: ["recorded"], evidence_layers: evidenceLayers.layers },
    { scenario_id: secondScenarioId, artifact_type: "variant", parent_scenario_id: SCENARIO_ID, branch_id: "branch-synthetic-root", branch_name: "slow-leads", seed: 11, config_hash: null, coordinate_frame: "local_road_aligned", duration_s: 2, layer_kinds: ["recorded", "generated"], evidence_layers: evidenceLayers.layers },
  ],
  actors: [
    { actor_id: "ego", actor_type: "vehicle.ego", role: "ego", left: { status: "measured", unavailable_reason: null, x_m: 5, y_m: 0, yaw_rad: 0.1, speed_mps: 6 }, right: { status: "measured", unavailable_reason: null, x_m: 6, y_m: 0, yaw_rad: 0.1, speed_mps: 6.4 }, position_delta_m: 1, heading_delta_rad: 0, speed_delta_mps: 0.4, delta_unavailable_reason: null },
    { actor_id: "lead", actor_type: "vehicle", role: "actor", left: { status: "measured", unavailable_reason: null, x_m: 25, y_m: 1, yaw_rad: 0.2, speed_mps: 5 }, right: { status: "unavailable", unavailable_reason: "actor_is_absent_from_this_side", x_m: null, y_m: null, yaw_rad: null, speed_mps: null }, position_delta_m: null, heading_delta_rad: null, speed_delta_mps: null, delta_unavailable_reason: "actor_is_absent_from_this_side" },
  ],
  metrics: [
    { metric: "ade_m.mean", left_value: null, left_status: "unavailable", left_reason: "replay_trace_not_available", right_value: null, right_status: "unavailable", right_reason: "replay_trace_not_available", delta: null, delta_unavailable_reason: "replay_trace_not_available", unit: "m", scientific_status: "PROVISIONAL" },
    { metric: "fde_m.mean", left_value: null, left_status: "unavailable", left_reason: "replay_trace_not_available", right_value: null, right_status: "unavailable", right_reason: "replay_trace_not_available", delta: null, delta_unavailable_reason: "replay_trace_not_available", unit: "m", scientific_status: "PROVISIONAL" },
    { metric: "ade_m.p95", left_value: null, left_status: "unavailable", left_reason: "replay_trace_not_available", right_value: null, right_status: "unavailable", right_reason: "replay_trace_not_available", delta: null, delta_unavailable_reason: "replay_trace_not_available", unit: "m", scientific_status: "PROVISIONAL" },
  ],
  metric_provenance: {
    left: { available: false, unavailable_reason: "replay_trace_not_available", source: "none", scientific_status: "PROVISIONAL", alignment_method: null, dataset_version: "v1", source_scene_token: "synthetic-scene-001", transform_version: "local-road-aligned-v1", generator_version: "real2scenario-test-v1" },
    right: { available: false, unavailable_reason: "replay_trace_not_available", source: "none", scientific_status: "PROVISIONAL", alignment_method: null, dataset_version: "v1", source_scene_token: "synthetic-scene-001", transform_version: "local-road-aligned-v1", generator_version: "real2scenario-test-v1" },
  },
  metric_scientific_status: "PROVISIONAL",
  gates: [
    { gate_id: "G4", left_status: "pass", right_status: "fail", differs: true, left_scientific_status: "not-applicable", right_scientific_status: "not-applicable", left_reasons: [], right_reasons: ["deceleration_exceeded"] },
    { gate_id: "G3", left_status: "skipped", right_status: "skipped", differs: false, left_scientific_status: "PROVISIONAL", right_scientific_status: "PROVISIONAL", left_reasons: ["lane_road_match_evidence_not_supplied_for_this_scenario"], right_reasons: ["lane_road_match_evidence_not_supplied_for_this_scenario"] },
  ],
  artifact_visibility: "local_private",
};

let recipePosts: Array<{ url: string; body: unknown }> = [];

const css = readFileSync(path.resolve(process.cwd(), "src/styles.css"), "utf8");

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function workspacePayload(summary: { scenario_id: string; artifact_type: string }) {
  return {
    scenario: summary,
    actors: [{ actor_id: "ego", actor_type: "vehicle.ego", role: "ego", states: trajectories, dimensions: { available: false, unavailable_reason: "actor_dimensions_unavailable" }, length_m: null, width_m: null }],
    paths: [{ actor_id: "ego", actor_type: "vehicle.ego", path_kind: "recorded", states: trajectories }],
    layers: {
      recorded_path: { available: true, unavailable_reason: null },
      generated_path: { available: false, unavailable_reason: "generated_path_not_available" },
      map_lanes: { available: false, unavailable_reason: "map_lane_geometry_not_available_in_current_artifact" },
      actor_dimensions: { available: false, unavailable_reason: "one_or_more_actor_dimensions_unavailable" },
      xodr_geometry: { available: false, unavailable_reason: "xodr_viewer_geometry_not_available" },
      lidar: { available: false, unavailable_reason: "dataset_not_configured" },
      third_person: { ...povFrame, available: true },
      in_car: { ...povFrame, available: true, mode: "in-car" },
    },
    metrics: { available: false, unavailable_reason: "replay_trace_not_available", alignment_method: null, source: "none", scientific_status: "PROVISIONAL", provenance: { dataset_version: "v1", source_scene_token: "synthetic-scene-001" }, per_actor: {}, aggregate: null },
    evidence_layers: evidenceLayers,
    gates: gateTimeline.gates,
    native_map: null,
    time_s: 0,
    simulator_frames: { ...povFrame, available: true },
  };
}

function route(url: string): Response {
  if (url.endsWith("/api/scenarios")) return json([scenarioSummary, secondScenarioSummary]);
  if (url.includes("/recipe")) {
    if (/\/recipe$/.test(url)) return json(recipeDocument);
    recipePosts.push({ url, body: null });
    return json(recipeDocument);
  }
  if (url.includes("/evidence-layers")) return json(evidenceLayers);
  if (url.includes("/lineage")) return json(lineage);
  if (url.includes("/compare")) return json(comparePayload);
  if (url.endsWith(`/api/scenarios/${SCENARIO_ID}/artifacts`)) return json({ scenario_id: SCENARIO_ID, artifacts: [] });
  if (url.endsWith(`/api/scenarios/${SCENARIO_ID}/trajectory`)) return json({ scenario_id: SCENARIO_ID, coordinate_frame: "local_road_aligned", duration_s: DURATION_S, map_warning: "", paths: [{ actor_id: "ego", actor_type: "vehicle.ego", path_kind: "recorded", states: trajectories }], replay_metrics: {} });
  if (url.includes(`/api/workspace/scenarios/${SCENARIO_ID}/frames/`)) return json({ ...povFrame, timestamp_s: Number(new URL(url, "http://local").searchParams.get("time_s") ?? 0) });
  if (url.includes(`/api/workspace/scenarios/${SCENARIO_ID}/image-frames/`)) return json({ contract_version: "workspace-pov-image-v1", scenario_id: SCENARIO_ID, mode: "third-person", status: "unavailable", frame_id: null, timestamp_s: null, simulator: "esmini", simulator_version: null, artifact: null, unavailable_reason: "esmini_image_capture_artifact_unavailable", provenance: { artifact_visibility: "local_private" } });
  if (url.endsWith(`/api/workspace/scenarios/${SCENARIO_ID}/sensor-status`)) return json({ contract_version: "workspace-variant-sensor-v1", scenario_id: SCENARIO_ID, artifact_type: "baseline", status: "unsupported", post_edit_frames: { available: false, unavailable_reason: "post_edit_sensor_frames_apply_to_variants_only" }, parent_sweep: { available: false, scenario_id: SCENARIO_ID, sample_data_token: null, timestamp_us: null, source: "recorded_parent_sweep", unavailable_reason: "dataset_not_configured" }, unavailable_reason: "post_edit_sensor_frames_apply_to_variants_only", provenance: {}, artifact_visibility: "local_private" });
  if (url.endsWith(`/api/workspace/scenarios/${SCENARIO_ID}/timeline`)) return json(actorTimeline);
  if (url.endsWith(`/api/workspace/scenarios/${SCENARIO_ID}/gate-timeline`)) return json(gateTimeline);
  if (url.endsWith(`/api/workspace/scenarios/${SCENARIO_ID}/lidar`)) return json({ available: true, sample_data_token: "sd-1", channel: "LIDAR_TOP", timestamp_us: 1_000_000, frame: "sensor", coordinate_frame: "local_road_aligned", transform_version: "local-road-aligned-v1", decimation: 8, total_count: 100, returned_count: 50, artifact_visibility: "local_private" });
  if (url.includes(`/api/workspace/scenarios/${SCENARIO_ID}/sensor-evidence`)) return json({ contract_version: "nuscenes-sensor-evidence-v1", channel: "LIDAR_TOP", status: "recorded", requested_nsweeps: 5, nsweeps: 2, timestamp_us: 1_000_000, reference: { sample_data_token: "sd-1", sample_token: "sample-1", timestamp_us: 1_000_000 }, sweeps: [{ sample_data_token: "sd-1", sample_token: "sample-1", timestamp_us: 1_000_000, channel: "LIDAR_TOP", artifact_visibility: "local_private" }, { sample_data_token: "sd-0", sample_token: "sample-0", timestamp_us: 900_000, channel: "LIDAR_TOP", historical: true, artifact_visibility: "local_private" }], annotations: { available: false, source: "NuScenes.get_boxes", boxes: [], unavailable_reason: "annotation_fixture_unavailable", provenance: {} }, map_underlay: { available: false, source: "NuScenesMap", unavailable_reason: "map_fixture_unavailable" }, can_telemetry: { available: false, source: "NuScenesCanBus", unavailable_reason: "can_fixture_unavailable" }, synchronization: { status: "recorded_history", historical_sweep_smearing: "expected_motion_smear_across_historical_sweeps" }, provenance: { render_equivalent: "render_sample_data:LIDAR_TOP:nsweeps" }, artifact_visibility: "local_private" });
  if (url.includes("/api/esmini/live/capability")) return json({ contract_version: "esmini-live-session-v1", configured: true, available: true, library: "/opt/esmini/libesminiLib.so", version: "3.10.0", adapter_version: "esmini-live-adapter-v1", max_sessions: 2, active_sessions: 0, unavailable_reason: null, commands: ["pause", "resume", "step", "reset", "control", "camera"], command_capabilities: { reset: { available: true }, control: { available: false, unavailable_reason: "esminiLib_control_abi_unavailable" }, camera: { available: true } }, browser_renderer: "browser-native-state-renderer", screenshot_stream: false });
  if (url.includes("/api/esmini/live/scenario-pairs")) return json({ contract_version: "esmini-live-session-v1", session_id: "live-fixture", scenario_id: SCENARIO_ID, status: "paused", unavailable_reason: null, simulator_version: "3.10.0", xosc_sha256: "x", xodr_sha256: "y", timestep_s: 0.05, simulation_time_s: 0, coordinate_frame: "esmini_local", transform_version: "esmini-state-v1", objects: [{ id: "ego", x_m: 0, y_m: 0, yaw_rad: 0 }], events: [], camera: {}, artifacts: { openscenario: "/api/artifacts/reports/live-pairs/scenario.xosc", opendrive: "/api/artifacts/reports/live-pairs/road.xodr" } });
  if (url.includes("/api/esmini/live/sessions/live-fixture")) return json({ contract_version: "esmini-live-session-v1", message_type: "state", session_id: "live-fixture", scenario_id: SCENARIO_ID, status: "paused", unavailable_reason: null, simulator_version: "3.10.0", xosc_sha256: "x", xodr_sha256: "y", timestep_s: 0.05, simulation_time_s: 0, coordinate_frame: "esmini_local", transform_version: "esmini-state-v1", objects: [{ id: "ego", x_m: 0, y_m: 0, yaw_rad: 0 }], events: [], camera: {} });
  if (url.endsWith(`/api/workspace/scenarios/${SCENARIO_ID}`)) return json(workspacePayload(scenarioSummary));
  if (url.endsWith(`/api/workspace/scenarios/${secondScenarioId}`)) return json(workspacePayload(secondScenarioSummary));
  if (url.endsWith(`/api/scenarios/${SCENARIO_ID}`)) return json(scenarioSummary);
  if (url.endsWith(`/api/scenarios/${secondScenarioId}`)) return json(secondScenarioSummary);
  if (url.endsWith(`/api/scenarios/${secondScenarioId}/artifacts`)) return json({ scenario_id: secondScenarioId, artifacts: [] });
  if (url.endsWith(`/api/scenarios/${secondScenarioId}/trajectory`)) return json({ scenario_id: secondScenarioId, coordinate_frame: "local_road_aligned", duration_s: DURATION_S, map_warning: "", paths: [{ actor_id: "ego", actor_type: "vehicle.ego", path_kind: "generated", states: trajectories }], replay_metrics: {} });
  if (url.endsWith(`/api/workspace/scenarios/${secondScenarioId}/timeline`)) return json(actorTimeline);
  if (url.endsWith(`/api/workspace/scenarios/${secondScenarioId}/lidar`)) return json({ available: false, unavailable_reason: "dataset_not_configured" });
  if (url.endsWith("/api/settings"))

  if (url.endsWith("/api/settings")) return json({ project_root: "/local", artifact_root: "/local/scenarios", output_root: "/local/reports", dataset_root: null, dataset_version: "v1.0-trainval", artifact_root_exists: true, dataset_root_exists: false, source_scene_count: 0 });
  if (url.endsWith("/api/esmini")) return json({ configured: false, available: false, executable: null, trace_converter: null, version: null, diagnostic: "esmini_not_configured" });
  return json({ detail: "unhandled test route" }, 404);
}

async function renderWorkspace() {
  render(<App />);
  await screen.findByRole("button", { name: /scene-timeline-001/ });
  fireEvent.click(screen.getByRole("button", { name: /scene-timeline-001/ }));
  await screen.findByRole("region", { name: /Time-indexed actor timeline and gate lane/ });
  return screen.getByRole("region", { name: /Time-indexed actor timeline and gate lane/ });
}

beforeEach(() => {
  window.localStorage.clear();
  recipePosts = [];
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  window.matchMedia = ((query: string) => ({ matches: false, media: query, onchange: null, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false })) as typeof window.matchMedia;
  vi.spyOn(globalThis, "fetch").mockImplementation(((input: RequestInfo | URL) => Promise.resolve(route(String(input)))) as typeof fetch);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("actor timeline and gate lane", () => {
  it("renders time-indexed actor tracks with channel values or n/a", async () => {
    const surface = await renderWorkspace();

    expect(within(surface).getAllByText("Position")).toHaveLength(2);
    expect(within(surface).getAllByText("Heading")).toHaveLength(2);
    expect(within(surface).getAllByText("Speed")).toHaveLength(2);
    expect(within(surface).getAllByText("Acceleration")).toHaveLength(2);
    expect(within(surface).getAllByText("Braking")).toHaveLength(2);
    expect(within(surface).getAllByText("n/a").length).toBeGreaterThan(0);
    expect(within(surface).getByText("1.500 m/s2")).toBeTruthy();
    expect(screen.queryByText("G1-G7 gate lane")).toBeNull();
  });

  it("keeps the timeline free of gate overlays and removes the Gates flyout", async () => {
    const surface = await renderWorkspace();

    expect(within(surface).queryByRole("list", { name: "Gate lane" })).toBeNull();
    expect(within(surface).queryByRole("list", { name: "Gate status list" })).toBeNull();
    expect(within(surface).queryAllByRole("listitem", { name: /G\d/ })).toHaveLength(0);

    // The gate detail flyout was removed, so its rail entry must be gone too.
    expect(screen.queryByRole("button", { name: "Gates" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "G1-G7 gates" })).toBeNull();
  });

  it("keeps the three-view grid limit without showing a counter", async () => {
    await renderWorkspace();
    const addView = () => screen.getByRole("button", { name: "Add view" });

    expect(addView().querySelector(".tool-badge")).toBeNull();
    expect((addView() as HTMLButtonElement).disabled).toBe(false);
    expect(addView().getAttribute("title")).toBe("Add view (Shift+V)");

    fireEvent.click(addView());
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /Top-down/ }));
    expect(addView().querySelector(".tool-badge")).toBeNull();

    fireEvent.click(addView());
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /3rd-person POV/ }));
    expect(addView().querySelector(".tool-badge")).toBeNull();
    expect((addView() as HTMLButtonElement).disabled).toBe(true);
    expect(addView().getAttribute("title")).toBe("Add view (Shift+V) - unavailable in this build");

    fireEvent.click(screen.getByRole("button", { name: "Close view: Top-down" }));
    expect(addView().querySelector(".tool-badge")).toBeNull();
    expect((addView() as HTMLButtonElement).disabled).toBe(false);
  });

  it("derives add-view slots from the next insertion position", async () => {
    await renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    const menu = screen.getByRole("menu");
    expect(menu.className).toContain("add-view-menu");
    expect(menu.closest(".add-view-control")).toBeTruthy();
    expect(within(menu).getByRole("button", { name: /Top-down/ }).textContent).toContain("nuScenes devkit map and point cloud");
    expect(within(menu).getByRole("button", { name: /Sensor Evidence/ }).textContent).toContain("nuScenes LIDAR_TOP recorded sweeps");
    expect(within(menu).getByRole("button", { name: /3rd-person POV/ }).textContent).toContain("internal transform POV");
    expect(within(menu).queryByRole("button", { name: /In-car POV/ })).toBeNull();
    expect(within(menu).queryByRole("button", { name: /LiDAR 3D/ })).toBeNull();
    expect(within(menu).getByRole("button", { name: /Real Camera/ }).textContent).toContain("recorded camera channel view");
  });

  it("shows camera POV options in a Real Camera view", async () => {
    await renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /Real Camera/ }));

    expect(screen.getByText("CAM_FRONT")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "camera pov" }));
    for (const pov of ["CAM_FRONT_RIGHT", "CAM_FRONT", "CAM_FRONT_LEFT", "CAM_BACK_RIGHT", "CAM_BACK_LEFT", "CAM_BACK"]) {
      expect(screen.getByRole("menuitemradio", { name: pov })).toBeTruthy();
    }
    fireEvent.click(screen.getByRole("menuitemradio", { name: "CAM_BACK" }));
    expect(screen.getByText("CAM_BACK")).toBeTruthy();
  });

  it("synchronizes the playhead across the main POV, top-down and replay-only sensor panes", async () => {
    await renderWorkspace();

    const playhead = screen.getByLabelText("Playhead") as HTMLInputElement;
    fireEvent.change(playhead, { target: { value: "1" } });

    await waitFor(() => expect(screen.getByText("playhead 1.00 s")).toBeTruthy());
    expect(screen.getByRole("img", { name: /playhead 1.00 seconds/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /Top-down/ }));
    expect(screen.getByRole("img", { name: /Top-down trajectory view at 1.00 seconds/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /Sensor Evidence/ }));
    expect(await screen.findByRole("img", { name: /nuScenes Sensor Evidence view with 2 LIDAR_TOP sweeps/ })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Add view" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("swaps view positions when one pane is dragged onto another", async () => {
    await renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /Top-down/ }));
    const panes = () => Array.from(document.querySelectorAll<HTMLElement>(".view-pane"));
    expect(panes()[0].textContent).toContain("3rd-person POV");
    expect(panes()[1].textContent).toContain("Top-down");

    const source = panes()[1].querySelector("header") as HTMLElement;
    const target = panes()[0];
    fireEvent.dragStart(source, { dataTransfer: { effectAllowed: "", setData: vi.fn() } });
    expect(source.getAttribute("aria-label")).toContain("drag handle");
    fireEvent.dragOver(target, { dataTransfer: { dropEffect: "none" }, preventDefault: vi.fn() });
    expect(target.className).toContain("drop-target");
    fireEvent.drop(target, { dataTransfer: { getData: () => "2" }, preventDefault: vi.fn() });

    expect(panes()[0].textContent).toContain("Top-down");
    expect(panes()[1].textContent).toContain("3rd-person POV");
    expect(panes()[0].className).not.toContain("drop-target");
  });
});

describe("measure mode", () => {
  it("measures against the active timestamp and follows the playhead", async () => {
    const surface = await renderWorkspace();

    fireEvent.keyDown(window, { key: "m" });
    expect(within(surface).getByText(/Measure at 0.00 s: 20.00 m ego -> lead/)).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Playhead"), { target: { value: "2" } });
    await waitFor(() => expect(within(surface).getByText(/Measure at 2.00 s: \d+\.\d+ m ego -> lead/)).toBeTruthy());
    expect(within(surface).getByText(/heading delta/)).toBeTruthy();
  });

  it("measures from the selected actor", async () => {
    const surface = await renderWorkspace();
    fireEvent.keyDown(window, { key: "m" });
    fireEvent.click(within(surface).getByRole("button", { name: "lead" }));

    expect(within(surface).getByText(/Measure at 0.00 s: 20.00 m lead -> ego/)).toBeTruthy();
  });
});

describe("keyboard operation", () => {
  it("switches modes from the keyboard and clears selection with Escape", async () => {
    const surface = await renderWorkspace();

    // "e" only opens the Variant studio editor when an actor is handed off;
    // the legacy canvas-branch dock is gone and no editor surface may appear.
    fireEvent.keyDown(window, { key: "e" });
    expect(screen.queryByRole("region", { name: "Canvas motion editor" })).toBeNull();
    expect(document.querySelector(".document-tabs button.active")?.textContent).toBe("Scenario studio");
    fireEvent.keyDown(window, { key: "m" });
    expect(screen.queryByRole("region", { name: "Constrained maneuver editor" })).toBeNull();
    fireEvent.keyDown(window, { key: "s" });

    fireEvent.click(within(surface).getByRole("button", { name: /^ego/ }));
    expect(within(surface).getByText("selection: ego")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(within(surface).getByText("selection: none")).toBeTruthy();
  });

  it("steps the playhead with the keyboard-operable controls", async () => {
    const surface = await renderWorkspace();

    fireEvent.click(within(surface).getByRole("button", { name: "Step playhead forward" }));
    fireEvent.click(within(surface).getByRole("button", { name: "Step playhead forward" }));
    expect(within(surface).getByText("playhead 0.10 s")).toBeTruthy();
    fireEvent.click(within(surface).getByRole("button", { name: "Step playhead back" }));
    expect(within(surface).getByText("playhead 0.05 s")).toBeTruthy();
  });

  it("opens the command palette with the documented shortcuts", async () => {
    await renderWorkspace();

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(await screen.findByRole("dialog", { name: "Search commands" })).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Search commands" })).toBeNull());
  });
});

describe("timeline sizing", () => {
  it("resizes the timeline by dragging its top edge", async () => {
    await renderWorkspace();
    const handle = screen.getByRole("separator", { name: "Resize timeline" });

    expect(handle.getAttribute("aria-valuenow")).toBe("236");
    fireEvent.pointerDown(handle, { clientY: 900 });
    fireEvent.pointerMove(window, { clientY: 700 });
    expect(handle.getAttribute("aria-valuenow")).toBe("436");

    fireEvent.pointerUp(window);
    fireEvent.pointerDown(handle, { clientY: 700 });
    fireEvent.pointerMove(window, { clientY: 400 });
    expect(handle.getAttribute("aria-valuenow")).toBe("520");
    expect(handle.getAttribute("aria-valuemax")).toBe("520");
  });

  it("collapses the timeline when dragged below its minimum and restores it", async () => {
    await renderWorkspace();
    const handle = screen.getByRole("separator", { name: "Resize timeline" });

    fireEvent.pointerDown(handle, { clientY: 700 });
    fireEvent.pointerMove(window, { clientY: 2000 });
    expect(document.querySelector(".workspace-body")?.className).toContain("timeline-collapsed");
    expect(handle.getAttribute("aria-valuenow")).toBe("0");

    fireEvent.pointerUp(window);
    fireEvent.pointerDown(handle, { clientY: 2000 });
    fireEvent.pointerMove(window, { clientY: 1800 });
    expect(document.querySelector(".workspace-body")?.className).not.toContain("timeline-collapsed");
    expect(handle.getAttribute("aria-valuenow")).toBe("320");
  });

  it("collapses and restores the timeline from the keyboard", async () => {
    await renderWorkspace();
    const handle = screen.getByRole("separator", { name: "Resize timeline" });

    fireEvent.keyDown(handle, { key: "ArrowDown" });
    for (let step = 0; step < 10; step += 1) fireEvent.keyDown(handle, { key: "ArrowDown" });
    expect(document.querySelector(".workspace-body")?.className).toContain("timeline-collapsed");

    fireEvent.keyDown(handle, { key: "ArrowUp" });
    expect(document.querySelector(".workspace-body")?.className).not.toContain("timeline-collapsed");
    expect(handle.getAttribute("aria-valuenow")).toBe("140");
  });
});

describe("accessibility", () => {
  it("gives every timeline control an accessible name and a keyboard role", async () => {
    const surface = await renderWorkspace();

    expect(screen.getByLabelText("Playhead").tagName).toBe("INPUT");
    for (const name of ["Step playhead back", "Step playhead forward"]) {
      expect(within(surface).getByRole("button", { name })).toBeTruthy();
    }
    expect(within(surface).getByRole("button", { name: /^ego/ }).getAttribute("aria-pressed")).toBe("false");
    expect(within(surface).getByRole("list", { name: "Actor state tracks" })).toBeTruthy();
  });

  it("states every status as text rather than colour only", async () => {
    const surface = await renderWorkspace();

    expect(within(surface).getAllByText("Braking")[0].closest(".track-channel")?.textContent).toContain("n/a");

    // The metrics table spells every unavailable cell out rather than leaving
    // it blank, so the value is readable without relying on colour.
    fireEvent.click(screen.getByRole("button", { name: "Metrics" }));
    const heading = await screen.findByRole("heading", { name: "ADE / FDE per actor" });
    const text = heading.parentElement?.textContent ?? "";
    expect(text).toContain("no parent trajectory to measure ADE/FDE against");
    // A root scenario has nothing to compare against, so the panel explains
    // that instead of rendering an empty numeric grid.
    expect(screen.queryByRole("table", { name: "ADE and FDE per actor" })).toBeNull();
    expect(text).toContain("Parent scenario is the reference");
  });

  it("exposes a text equivalent for every timeline visualization", async () => {
    const surface = await renderWorkspace();

    for (const spark of within(surface).getAllByRole("img")) {
      expect(spark.getAttribute("aria-label")).toBeTruthy();
    }
  });

  it("keeps the timeline reachable when reduced motion is requested", () => {
    const styles = css;
    expect(styles).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
  });
});

describe("mobile layout", () => {
  it("keeps the actor tracks and playhead usable at a narrow viewport", async () => {
    window.innerWidth = 390;
    const surface = await renderWorkspace();

    expect(within(surface).getByRole("list", { name: "Actor state tracks" })).toBeTruthy();
    expect(within(surface).queryByRole("list", { name: "Gate lane" })).toBeNull();
    expect(screen.getByLabelText("Playhead")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Catalog" })).toBeTruthy();
  });

  it("defines a narrow-viewport layout that stacks the actor tracks", () => {
    const styles = css;
    const mobile = styles.slice(styles.indexOf("@media (max-width: 560px)"));
    expect(mobile).toContain(".actor-track { grid-template-columns: 1fr; }");
  });
});
describe("version tree and lineage surfaces", () => {
  it("shows branch identity, seed and config hash in the status bar and variant studio", async () => {
    await renderWorkspace();

    expect(screen.getByText("branch: branch-synthetic-root")).toBeTruthy();
    expect(screen.getByText("config hash: sha256:01234")).toBeTruthy();
  });

  it("keeps the footer free of full scenario ids", async () => {
    await renderWorkspace();
    const footer = document.querySelector(".status-bar") as HTMLElement;

    expect(footer.textContent).not.toContain(SCENARIO_ID);
    expect(document.querySelector(".status-bar span[title]")).toBeNull();
    const pov = await screen.findByRole("img", { name: /simulator frame/ });
    expect(pov.textContent).not.toContain("frame-t0000");
  });

  it("shows only the selected scenario as the branch-tree root", async () => {
    await renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "Versions" }));
    const tree = await screen.findByRole("tree", { name: "Committed scenario versions" });

    // The tree is scoped to the scenario open in Scenario studio, not the whole
    // catalog: one root, plus scene-timeline-002 which declares it as parent.
    expect(within(tree).getByRole("button", { name: "scene-timeline-001" })).toBeTruthy();
    expect(within(tree).getByRole("button", { name: "scene-timeline-002" })).toBeTruthy();
    // The unrelated second root must not appear.
    expect(within(tree).queryByRole("button", { name: "unrelated-scenario" })).toBeNull();
    expect(within(tree).getAllByRole("treeitem")).toHaveLength(2);
    expect(within(tree).getByText(/1 version$/)).toBeTruthy();

    // Selecting the child moves the selection marker.
    fireEvent.click(within(tree).getByRole("button", { name: "scene-timeline-002" }));
    await waitFor(() => expect(within(tree).getByRole("treeitem", { selected: true }).textContent).toContain("scene-timeline-002"));
  });

  it("routes the Select actors tool to Scenario studio and disables it there", async () => {
    await renderWorkspace();

    const tool = () => screen.getByRole("button", { name: /^Select actors/ });
    // Start on Variant studio by opening the motion editor.
    (document.querySelectorAll(".actor-track .track-label")[1] as HTMLElement | undefined)?.click();
    await waitFor(() => screen.getByText("selection: lead"));
    fireEvent.click(screen.getByRole("button", { name: "Variant studio" }));
    await screen.findByRole("region", { name: "Variant studio" });

    expect(tool().hasAttribute("disabled")).toBe(false);
    fireEvent.click(tool());
    // Activating it returns to Scenario studio.
    expect(document.querySelector(".document-tabs button.active")?.textContent).toBe("Scenario studio");
    // Already there: the tool reports itself and stops accepting clicks.
    await waitFor(() => expect(tool().hasAttribute("disabled")).toBe(true));
    expect(tool().getAttribute("title")).toContain("You have selected this buttons");
  });

  it("scopes the variant studio to the selected actor instead of dumping raw metadata", async () => {
    await renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "Variant studio" }));
    const studio = await screen.findByRole("region", { name: "Variant studio" });

    // The raw lineage/metadata dump was removed from this surface, so the
    // Variant studio now answers with the editing contract instead: one
    // editable actor, its own timeline, and the guardrails it must satisfy.
    // The guardrail table moved out of this surface into the right-rail
    // Guardrails flyout, so the editor keeps only the editing actions.
    expect(within(studio).queryByText("Guardrails")).toBeNull();
    // "Add keyframe" is now the "+" pinned to the canvas corner, not a panel
    // button, and deletion moved to the Delete/Backspace keys.
    expect(within(studio).getByRole("button", { name: "Add keyframe" }).className).toBe("motion-add-keyframe");
    expect(within(studio).queryByRole("button", { name: "Delete selected keyframe" })).toBeNull();
    expect(within(studio).queryByRole("button", { name: "Commit branch" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Guardrails" })).toBeTruthy();
    expect(within(studio).queryByRole("list", { name: "Variant lineage path" })).toBeNull();
    // The selected-actor timeline strip was removed from this surface.
    expect(within(studio).queryByLabelText("Selected actor playhead")).toBeNull();
  });
});

describe("evidence layers", () => {
  it("no longer exposes a Map layers panel", async () => {
    await renderWorkspace();

    // The Map layers rail button and its evidence-layer panel were removed, so
    // neither the entry point nor the panel it opened may remain reachable.
    expect(screen.queryByRole("button", { name: "Map layers" })).toBeNull();
    expect(screen.queryByRole("list", { name: "Evidence layers" })).toBeNull();
    expect(screen.queryByText("Metric provenance")).toBeNull();
    // The surviving rail entries are untouched.
    expect(screen.getByRole("button", { name: "Versions" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Catalog" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Comments" })).toBeTruthy();
  });

  it("renders the top-down trajectory view without a legend", async () => {
    await renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /Top-down/ }));

    expect(screen.getByRole("img", { name: /Top-down trajectory view/ }).parentElement?.querySelector(".view-legend")).toBeNull();
  });
});

describe("recorded sensor evidence", () => {
  it("keeps Sensor Evidence separate without a native session action", async () => {
    await renderWorkspace();
     fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    fireEvent.click(within(screen.getByRole("menu")).getByRole("button", { name: /Sensor Evidence/ }));
    expect(await screen.findByRole("img", { name: /nuScenes Sensor Evidence view with 2 LIDAR_TOP sweeps/ })).toBeTruthy();
    expect(screen.getByText("historical sweep smearing expected")).toBeTruthy();

    expect(screen.queryByRole("button", { name: "Start native session" })).toBeNull();
  });

  it("keeps Sensor Evidence in Scenario studio when added", async () => {
    await renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Add view" }));
    const entry = within(screen.getByRole("menu")).getByRole("button", { name: /Sensor Evidence/ });

    expect(entry).toHaveProperty("disabled", false);
    fireEvent.click(entry);

    expect(await screen.findByRole("img", { name: /nuScenes Sensor Evidence view/ })).toBeTruthy();
    expect(document.querySelector(".document-tabs button.active")?.textContent).toBe("Scenario studio");
  });
});

describe("fixed working space", () => {
  it("pins the app to the viewport and keeps the view grid scroll-free", () => {
    const styles = css;

    // The app is exactly the viewport tall, so nothing can push a page scrollbar.
    expect(styles).toMatch(/\.workspace-app \{[^}]*height: 100dvh/);
    expect(styles).toMatch(/html, body, #root \{ height: 100%; \}/);
    expect(styles).toMatch(/body \{[^}]*overflow: hidden/);
    expect(styles).toMatch(/\.workspace-app \{[^}]*grid-template-rows: 48px 52px minmax\(0, 1fr\) 34px/);

    // Every stage from the body down to a pane clips instead of scrolling.
    for (const selector of [".workspace-body", ".view-manager", ".view-grid", ".view-pane", ".timeline-surface"]) {
      const rule = styles.match(new RegExp("\\" + selector + "\\s*\\{[^}]*\\}"));
      expect(rule?.[0]).toMatch(/overflow: hidden/);
    }

    // Panes may shrink with the grid rather than enforcing a floor.
    expect(styles).toMatch(/\.view-pane \{ min-width: 0; min-height: 0;/);
  });
});
