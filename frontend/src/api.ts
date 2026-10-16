export type ActorSummary = {
  actor_id: string;
  actor_type: string;
  sample_count: number;
  length_m: number | null;
  width_m: number | null;
};

export type ArtifactLink = { kind: string; path: string; url: string };
export type WasmScenarioPair = { scenario_id: string; coordinate_frame: string; map_warning: string; openscenario: string; opendrive: string; artifact_visibility: string };
export type ScenarioSummary = {
  scenario_id: string;
  parent_scenario_id: string | null;
  artifact_type: "baseline" | "variant";
  duration_s: number;
  coordinate_frame: string;
  actors: ActorSummary[];
  provenance: Record<string, string>;
  available_artifacts: ArtifactLink[];
};

export type TrajectoryState = { time_s: number; x_m: number; y_m: number; yaw_rad: number; speed_mps: number };
export type TrajectoryPath = { actor_id: string; actor_type: string; path_kind: "recorded" | "replayed" | "generated"; states: TrajectoryState[] };
export type ReplayMetric = { sample_count: number; position_rmse_m: number; final_displacement_m: number; heading_mae_rad: number; speed_mae_mps: number; alignment_method: string; ade_m?: number | null; fde_m?: number | null; coverage_status?: string };
export type MetricDistribution = { mean: number; median: number; p95: number; max: number };
export type ReplayMetricAggregate = { actor_count: number; ade_m: MetricDistribution; fde_m: MetricDistribution | null };
export type Availability = { available: boolean; unavailable_reason: string | null };
export type SimulatorCapability = Availability & { simulator: string; version: string | null; frame_contract: string | null; modes: string[]; rendering: string | null };
export type POVFrame = { contract_version: string; frame_id: string; mode: "third-person" | "in-car"; status: "rendered" | "unavailable" | "error"; simulator: string; simulator_version: string | null; timestamp_s: number; coordinate_frame: string; transform_version: string | null; camera_transform: Record<string, number | string>; actors: Array<{ actor_id: string; actor_type: string; transform: Record<string, number>; speed_mps: number; dimensions: Record<string, number | null> }>; provenance: Record<string, string> };
export type POVImageFrame = { contract_version: "workspace-pov-image-v1"; scenario_id: string; mode: "third-person" | "in-car"; status: "rendered" | "unavailable" | "error"; frame_id: string | null; timestamp_s: number | null; simulator: string; simulator_version: string | null; artifact: ArtifactLink | null; unavailable_reason: string | null; provenance: Record<string, string> };
export type WorkspaceLayer = Availability;
export type LidarTransform = { translation_m: number[]; rotation_wxyz: number[] };
export type EvidenceTransform = LidarTransform & { source_frame: string; target_frame: string; matrix_4x4: number[][]; composition: string[]; transform_version: string; calibrated_sensor_token: string; ego_pose_token: string };
export type LidarDescriptor = Availability & { sample_data_token?: string; payload_url?: string; version?: string; channel?: "LIDAR_TOP"; timestamp_us?: number; offset_us?: number; historical?: boolean; frame?: string; coordinate_frame?: string; calibration_token?: string; calibration_transform?: LidarTransform; ego_pose_transform?: LidarTransform; transforms?: EvidenceTransform; transform_version?: string; source_file?: string; decimation?: number | null; total_count?: number | null; returned_count?: number | null; artifact_visibility?: string };
export type SensorEvidence = { contract_version: "nuscenes-sensor-evidence-v1"; channel: "LIDAR_TOP"; status?: string; unavailable_reason?: string; sample_data_token?: string; sample_token?: string; timestamp_us?: number; nsweeps?: number; requested_nsweeps?: number; reference?: { sample_data_token: string; sample_token: string; timestamp_us: number }; sweeps: LidarDescriptor[]; annotations?: { available: boolean; source: string; boxes: Array<Record<string, unknown>>; unavailable_reason?: string; provenance: Record<string, string> }; map_underlay: { available: boolean; source: string; map_name?: string; patch?: number[]; layers?: Record<string, string[]>; unavailable_reason?: string; provenance?: Record<string, string> }; can_telemetry: { available: boolean; source: string; reference_timestamp_us?: number; aligned_timestamp_us?: number; alignment_delta_us?: number; unavailable_reason?: string; provenance?: Record<string, string> }; synchronization: { status: string; reference_timestamp_us?: number; historical_sweep_smearing: string }; provenance: Record<string, string>; artifact_visibility: string };
export type NativeMap = { version: string; status: string; map_name: string; layers: Record<string, Array<Record<string, unknown>>>; artifact_visibility: string };
export type WorkspaceDocument = { document_name: string; branch: string; version: string; active_scenario_id: string; connection: Availability; dataset: Availability; esmini: Availability; native_map: Availability; simulator_frames: SimulatorCapability; dataset_version: string | null; esmini_version: string | null; coordinate_frame: string; transform_version: string | null; provenance: Record<string, string> };
export type ParentSweepStatus = { available: boolean; scenario_id: string | null; sample_data_token: string | null; timestamp_us: number | null; source: string; unavailable_reason: string | null };
export type VariantSensorStatus = { contract_version: "workspace-variant-sensor-v1"; scenario_id: string; artifact_type: "baseline" | "variant"; status: "available" | "unavailable" | "unsupported"; post_edit_frames: Availability; parent_sweep: ParentSweepStatus; unavailable_reason: string | null; provenance: Record<string, string>; artifact_visibility: string };
export type WorkspaceScenario = { scenario: ScenarioSummary; actors: Array<ActorSummary & { role: "ego" | "actor"; states: TrajectoryState[]; dimensions: Availability }>; paths: TrajectoryPath[]; layers: { recorded_path: WorkspaceLayer; generated_path: WorkspaceLayer; map_lanes: WorkspaceLayer; actor_dimensions: WorkspaceLayer; xodr_geometry: WorkspaceLayer; lidar: WorkspaceLayer; third_person: SimulatorCapability; in_car: SimulatorCapability }; metrics: MetricAvailability; evidence_layers: EvidenceLayers | null; sensor_status: VariantSensorStatus | null; gates: GateSegment[]; native_map: NativeMap | null; time_s: number; simulator_frames: SimulatorCapability };
export type TrajectoryResponse = {
  scenario_id: string;
  coordinate_frame: string;
  duration_s: number;
  map_warning: string;
  paths: TrajectoryPath[];
  replay_metrics: Record<string, ReplayMetric>;
};

export type ActorMotionEdit = {
  actor_id: string;
  speed_multiplier: number;
  heading_offset_rad: number;
  timing_offset_s: number;
  initial_gap_delta_m: number;
  steering_angle_rad?: number;
  acceleration_mps2?: number | null;
  braking_mps2?: number | null;
  target_speed_mps?: number | null;
  start_time_s?: number;
  end_time_s?: number | null;
};
export type RecipeStepRequest = { step_id: string; name: string; kind?: "constrained-maneuver"; actor_edit: ActorMotionEdit; active?: boolean };
export type PreviewRequest = {
  actor_edits: ActorMotionEdit[];
  recipe_steps?: RecipeStepRequest[];
  replay_mode?: "waypoint";
  behavior?: "parameterized" | "behavior";
  seed: number;
};
export type GateResult = {
  gate_id: string;
  status: "pass" | "fail" | "skipped" | "error";
  reasons: string[];
  config_version: string | null;
  observed: Record<string, unknown> | null;
  scientific_status: string;
};
export type GateSegmentStatus = "pass" | "fail" | "skipped" | "error" | "unsupported";
export type GateSegment = {
  gate_id: string;
  status: GateSegmentStatus;
  scientific_status: string;
  reasons: string[];
  config_version: string | null;
  observed: Record<string, unknown> | null;
  start_s: number;
  end_s: number;
  extent_source: string;
};
export type GateTimeline = {
  contract_version: string;
  scenario_id: string;
  coordinate_frame: string;
  time_domain: { start_s: number; end_s: number };
  gates: GateSegment[];
  counts: Record<GateSegmentStatus, number>;
  provisional_count: number;
  artifact_visibility: string;
};
export type ChannelAvailability = { available: boolean; unavailable_reason: string | null; version: string; coverage: number | null };
export type TimelineSample = { time_s: number; x_m: number; y_m: number; yaw_rad: number; speed_mps: number; acceleration_mps2: number | null; acceleration_source: string | null; braking_pressure: number | null; braking_source: string | null };
export type ActorTrack = {
  actor_id: string;
  actor_type: string;
  role: "ego" | "actor";
  channels: { position: ChannelAvailability; heading: ChannelAvailability; speed: ChannelAvailability; acceleration: ChannelAvailability; braking: ChannelAvailability };
  samples: TimelineSample[];
};
export type ActorTimeline = { contract_version: string; scenario_id: string; coordinate_frame: string; time_domain: { start_s: number; end_s: number }; tracks: ActorTrack[]; artifact_visibility: string };
export type PreviewResponse = {
  parent_scenario_id: string;
  variant_id: string | null;
  status: "valid" | "invalid" | "unsupported";
  behavior: Record<string, string>;
  configuration: Record<string, unknown>;
  provenance: Record<string, string>;
  paths: TrajectoryPath[];
  validation: Validation | null;
  gates: GateResult[];
  replay_metrics: Record<string, ReplayMetric>;
  artifacts: ArtifactLink[];
  recipe_steps: RecipeStepRequest[];
  limits: Record<string, unknown>;
  violations: Array<Record<string, unknown>>;
  rollback_marker: { parent_scenario_id: string; variant_id: string; immutable_parent: boolean } | null;
};

export type MetricAvailability = {
  available: boolean;
  unavailable_reason: string | null;
  alignment_method: string | null;
  source: "replay_trace" | "none";
  scientific_status: string;
  provenance: Record<string, string>;
  per_actor: Record<string, ReplayMetric>;
  aggregate: ReplayMetricAggregate | null;
};

export type RecipeStepViolation = { code: string; actor_id: string; observed: number; limit: number; provenance: string };
export type RecipeStep = {
  index: number;
  step_id: string;
  name: string;
  kind: "constrained-maneuver";
  status: "valid" | "invalid" | "error";
  active: boolean;
  inactive_reason: string | null;
  parameters: ActorMotionEdit;
  violations: RecipeStepViolation[];
  error: string | null;
  artifact: ArtifactLink | null;
  artifact_unavailable_reason: string | null;
};
export type RollbackMarker = { marker_id: string; name: string; step_count: number; revision: number };
export type RecipeHistory = {
  revision: number;
  undo_depth: number;
  redo_depth: number;
  non_destructive: boolean;
  undoable: boolean;
  redoable: boolean;
  undo_unavailable_reason: string | null;
  redo_unavailable_reason: string | null;
};
export type RecipeDocument = {
  contract_version: "workspace-recipe-v1";
  scenario_id: string;
  coordinate_frame: string;
  parent_scenario_id: string | null;
  parent_immutable: boolean;
  mutation: string;
  persistence: Availability;
  limits: Record<string, unknown>;
  steps: RecipeStep[];
  step_count: number;
  active_step_count: number;
  rollback_markers: RollbackMarker[];
  active_marker_id: string | null;
  history: RecipeHistory;
  artifact_visibility: string;
};

export type LineageNode = { scenario_id: string; artifact_type: string; present: boolean; unavailable_reason: string | null };
export type BranchIdentity = {
  branch_id: string;
  branch_name: string | null;
  root_scenario_id: string;
  branch_id_source: string;
  branch_name_source: string | null;
  branch_name_unavailable_reason: string | null;
};
export type VariantLineage = {
  contract_version: "workspace-variant-lineage-v1";
  scenario_id: string;
  artifact_type: string;
  artifact_path: string;
  coordinate_frame: string;
  lineage_path: LineageNode[];
  lineage_depth: number;
  branch: BranchIdentity;
  child_scenario_ids: string[];
  fields: Record<string, unknown>;
  unavailable_reasons: Record<string, string | null>;
  provenance: Record<string, string>;
  artifact_visibility: string;
};

export type EvidenceLayer = {
  layer: "recorded" | "generated" | "replayed" | "sensor-evidence";
  status: "available" | "unavailable" | "unsupported";
  unavailable_reason: string | null;
  source: string;
  scientific_status: string;
  provenance: Record<string, string>;
  coverage: number | null;
  reference: string;
  parent_fallback: Record<string, unknown> | null;
};
export type EvidenceLayers = {
  contract_version: "workspace-evidence-layers-v1";
  scenario_id: string;
  coordinate_frame: string;
  layers: EvidenceLayer[];
  available_count: number;
  artifact_visibility: string;
};

export type CompareSide = {
  scenario_id: string;
  artifact_type: string;
  parent_scenario_id: string | null;
  branch_id: string;
  branch_name: string | null;
  seed: number | null;
  config_hash: string | null;
  coordinate_frame: string;
  duration_s: number;
  layer_kinds: string[];
  evidence_layers: EvidenceLayer[];
};
export type CompareActorState = { status: "measured" | "unavailable"; unavailable_reason: string | null; x_m: number | null; y_m: number | null; yaw_rad: number | null; speed_mps: number | null };
export type CompareActor = {
  actor_id: string;
  actor_type: string | null;
  role: string | null;
  left: CompareActorState;
  right: CompareActorState;
  position_delta_m: number | null;
  heading_delta_rad: number | null;
  speed_delta_mps: number | null;
  delta_unavailable_reason: string | null;
};
export type CompareMetricRow = {
  metric: string;
  left_value: number | null;
  left_status: string;
  left_reason: string | null;
  right_value: number | null;
  right_status: string;
  right_reason: string | null;
  delta: number | null;
  delta_unavailable_reason: string | null;
  unit: string;
  scientific_status: string;
};
export type CompareGateRow = {
  gate_id: string;
  left_status: string | null;
  right_status: string | null;
  differs: boolean;
  left_scientific_status: string | null;
  right_scientific_status: string | null;
  left_reasons: string[];
  right_reasons: string[];
};
export type ComparePayload = {
  contract_version: "workspace-compare-v1";
  synchronization: {
    mode: string;
    time_s: number;
    requested_time_s: number;
    time_domain: { start_s: number; end_s: number };
    left_duration_s: number;
    right_duration_s: number;
    durations_differ: boolean;
    duration_unavailable_reason: string | null;
    reference_point: string;
  };
  sides: CompareSide[];
  actors: CompareActor[];
  metrics: CompareMetricRow[];
  metric_provenance: Record<string, Record<string, unknown>>;
  metric_scientific_status: string;
  gates: CompareGateRow[];
  artifact_visibility: string;
};

export type Validation = { valid: boolean; validation_version: string; reasons: Array<{ code: string; category: string; actor_id: string | null; state_index: number | null; observed: number | null; limit: number | null; message: string }> };
export type Ranking = { rankable: boolean; ranking_version: string; features: { minimum_distance_m: number | null; minimum_ttc_s: number | null; novelty: number; risk_signal: number }; breakdown: { risk_signal: number; novelty: number; replay_quality: number; feasibility_penalty: number; total: number } | null };
export type VariantResult = { variant_id: string; status: "valid" | "invalid" | "simulator-failed"; configuration: Record<string, number>; validation: Validation; ranking: Ranking | null; replay_metrics: TrajectoryResponse["replay_metrics"]; replay_metric_aggregate: ReplayMetricAggregate | null; gates: GateResult[]; simulator_error: string | null; replay_failure: Record<string, unknown> | null; artifacts: ArtifactLink[] };
export type BatchResults = { job: { job_id: string; status: string; scenario_id: string; generated: number; error: string | null }; manifest: Record<string, unknown>; counts: Record<string, number>; results: VariantResult[]; replay_metric_aggregate: ReplayMetricAggregate | null };
export type SettingsView = { project_root: string; artifact_root: string; output_root: string; dataset_root: string | null; dataset_version: string; artifact_root_exists: boolean; dataset_root_exists: boolean; source_scene_count: number };
export type EsminiCapability = { configured: boolean; available: boolean; executable: string | null; trace_converter: string | null; version: string | null; diagnostic: string };
export type LiveCapability = { contract_version: "esmini-live-session-v1"; configured: boolean; available: boolean; library: string | null; version: string | null; adapter_version: string; max_sessions: number; active_sessions: number; unavailable_reason: string | null; commands: string[]; command_capabilities: Record<string, { available: boolean; implementation?: string; unavailable_reason?: string }>; browser_renderer: string; screenshot_stream: boolean };
export type LiveState = { contract_version: "esmini-live-session-v1"; message_type: "state" | "command_result"; session_id: string; scenario_id: string; status: string; unavailable_reason: string | null; simulator_version: string | null; xosc_sha256: string; xodr_sha256: string; timestep_s: number; simulation_time_s: number; coordinate_frame: string; transform_version: string; objects: Array<{ id: string; x_m: number; y_m: number; yaw_rad: number; length_m?: number; width_m?: number }>; events: Array<Record<string, unknown>>; camera: Record<string, unknown> };
export type ReplayJob = { job_id: string; scenario_id: string; status: "queued" | "running" | "completed" | "failed" | "timed-out"; error: string | null; failure_code: string | null; failure_message: string | null; tool_version: string | null; exit_code: number | null; timed_out: boolean; stdout: string; stderr: string; artifacts: Record<string, string>; metrics: Record<string, unknown>; started_at: string | null; finished_at: string | null };
export type SourceScene = { scene_token: string; name: string; description: string; sample_count: number; first_sample_token: string; last_sample_token: string; vehicle_candidate_count: number };
export type SourceSceneImportResponse = { scene: SourceScene; scenario_id: string; selected_actor_ids: string[]; artifact: ArtifactLink; scenario: ScenarioSummary };
export type CP1ReviewItem = { item_id: string; category: string; title: string; status: "blocked" | "ready" | "deferred" | "informational"; blocking: boolean; what_to_verify: string; owner_action: string; evidence: string[]; related_api: string[] };
export type CP1Review = { review_version: string; diagnostic_status: "diagnostic"; scientific_status: "PROVISIONAL"; scene: string; corridor_baseline: { states: number; matched_states: number; raw_match_rate: number; display: string; all_vehicle_rate: string; must_remain_unchanged: boolean }; scope_note: string; items: CP1ReviewItem[] };

const API = import.meta.env.VITE_API_URL ?? "/api";
export const apiUrl = (path: string) => `${API}${path}`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  const raw = await response.text();
  let body: unknown = null;
  if (raw.trim().length > 0) {
    try { body = JSON.parse(raw); } catch { body = null; }
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    throw new Error(typeof detail === "string" && detail ? detail : `Request failed: ${response.status} ${response.statusText}`.trim());
  }
  if (body === null) throw new Error(`Empty or non-JSON response from ${path} (HTTP ${response.status})`);
  return body as T;
}

export const fetchScenarios = () => request<ScenarioSummary[]>("/scenarios");
export const fetchScenario = (id: string) => request<ScenarioSummary>(`/scenarios/${encodeURIComponent(id)}`);
export const fetchWorkspaceDocument = (id: string) => request<WorkspaceDocument>(`/workspace/documents/${encodeURIComponent(id)}`);
export const fetchWorkspaceScenario = (id: string) => request<WorkspaceScenario>(`/workspace/scenarios/${encodeURIComponent(id)}`);
export const fetchActorTimeline = (id: string) => request<ActorTimeline>(`/workspace/scenarios/${encodeURIComponent(id)}/timeline`);
export const fetchGateTimeline = (id: string) => request<GateTimeline>(`/workspace/scenarios/${encodeURIComponent(id)}/gate-timeline`);
export const fetchPOVFrame = (id: string, mode: "third-person" | "in-car", timeS: number) => request<POVFrame>(`/workspace/scenarios/${encodeURIComponent(id)}/frames/${mode}?time_s=${encodeURIComponent(timeS)}`);
export const fetchPOVImageFrame = (id: string, mode: "third-person" | "in-car", timeS: number) => request<POVImageFrame>(`/workspace/scenarios/${encodeURIComponent(id)}/image-frames/${mode}?time_s=${encodeURIComponent(timeS)}`);
export const fetchVariantSensorStatus = (id: string) => request<VariantSensorStatus>(`/workspace/scenarios/${encodeURIComponent(id)}/sensor-status`);
export const fetchScenarioArtifacts = (id: string) => request<{ scenario_id: string; artifacts: ArtifactLink[] }>(`/scenarios/${encodeURIComponent(id)}/artifacts`);
export const createWasmScenarioPair = (id: string) => request<WasmScenarioPair>(`/workspace/scenarios/${encodeURIComponent(id)}/wasm-pair`, { method: "POST" });
export const fetchTrajectory = (id: string) => request<TrajectoryResponse>(`/scenarios/${encodeURIComponent(id)}/trajectory`);
export const previewVariant = (scenarioId: string, body: PreviewRequest) => request<PreviewResponse>(`/scenarios/${encodeURIComponent(scenarioId)}/variants/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const createBatch = (body: object) => request<{ job_id: string }>("/batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchBatchResults = (id: string) => request<BatchResults>(`/batches/${id}/results`);
export const fetchBatchTrajectory = (jobId: string, variantId: string) => request<TrajectoryResponse>(`/batches/${jobId}/results/${encodeURIComponent(variantId)}/trajectory`);
export const exportBatchResult = (jobId: string, variantId: string) => request<{ variant_id: string; artifacts: ArtifactLink[] }>(`/batches/${jobId}/results/${encodeURIComponent(variantId)}/export`, { method: "POST" });
export const fetchSettings = () => request<SettingsView>("/settings");
export const fetchEsminiCapability = () => request<EsminiCapability>("/esmini");
export const fetchLiveCapability = () => request<LiveCapability>("/esmini/live/capability");
export const createLiveScenarioPair = (scenarioId: string, timestepS = 0.05) => request<LiveState & { artifacts: { openscenario: string; opendrive: string } }>("/esmini/live/scenario-pairs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario_id: scenarioId, timestep_s: timestepS }) });
export const fetchLiveState = (sessionId: string) => request<LiveState>(`/esmini/live/sessions/${encodeURIComponent(sessionId)}`);
export const sendLiveCommand = (sessionId: string, command: LiveState["message_type"] | string, payload: Record<string, unknown> = {}) => request<LiveState>(`/esmini/live/sessions/${encodeURIComponent(sessionId)}/commands`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command, payload }) });
export const createReplay = (scenarioId: string) => request<ReplayJob>("/replays", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario_id: scenarioId }) });
export const fetchReplay = (jobId: string) => request<ReplayJob>(`/replays/${encodeURIComponent(jobId)}`);
export const updateSettings = (body: object) => request<SettingsView>("/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchSourceScenes = () => request<SourceScene[]>("/source-scenes");
export const importSourceScene = (sceneToken: string, body: object = {}) => request<SourceSceneImportResponse>(`/source-scenes/${encodeURIComponent(sceneToken)}/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchCP1Review = () => request<CP1Review>("/cp1/review");
export const fetchNativeMapCapability = (mapName: string) => request<Availability & { map_name: string }>(`/workspace/maps/${encodeURIComponent(mapName)}/capability`);
export const fetchLidarCapability = () => request<Availability & { channel?: string }>("/workspace/lidar/capability");
export const lidarPayloadUrl = (token: string, decimation = 8) => apiUrl(`/workspace/lidar/${encodeURIComponent(token)}?decimation=${decimation}`);
export const fetchLidarDescriptor = (id: string) => request<LidarDescriptor>(`/workspace/scenarios/${encodeURIComponent(id)}/lidar`);
export const fetchSensorEvidence = (id: string, nsweeps = 5) => request<SensorEvidence>(`/workspace/scenarios/${encodeURIComponent(id)}/sensor-evidence?nsweeps=${nsweeps}`);
export const topDownImageUrl = (id: string, source: "lidar" | "radar", nsweeps = 5) => apiUrl(`/workspace/scenarios/${encodeURIComponent(id)}/top-down?source=${source}&nsweeps=${nsweeps}`);

export const fetchRecipe = (id: string) => request<RecipeDocument>(`/workspace/scenarios/${encodeURIComponent(id)}/recipe`);
const recipeUrl = (id: string, suffix = "") => `/workspace/scenarios/${encodeURIComponent(id)}/recipe${suffix}`;
const postJson = (path: string, body: unknown) => request<RecipeDocument>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const addRecipeStep = (id: string, step: RecipeStepRequest) => postJson(recipeUrl(id, "/steps"), step);
export const setRecipeStepActive = (id: string, stepId: string, active: boolean) => postJson(recipeUrl(id, `/steps/${encodeURIComponent(stepId)}/active`), { active });
export const removeRecipeStep = (id: string, stepId: string) => postJson(recipeUrl(id, `/steps/${encodeURIComponent(stepId)}/remove`), {});
export const moveRecipeStep = (id: string, stepId: string, direction: "up" | "down") => postJson(recipeUrl(id, "/steps/move"), { step_id: stepId, direction });
export const addRollbackMarker = (id: string, name: string) => postJson(recipeUrl(id, "/markers"), { name });
export const restoreRollbackMarker = (id: string, markerId: string) => postJson(recipeUrl(id, `/markers/${encodeURIComponent(markerId)}/restore`), {});
export const undoRecipe = (id: string) => postJson(recipeUrl(id, "/undo"), {});
export const redoRecipe = (id: string) => postJson(recipeUrl(id, "/redo"), {});
export const fetchVariantLineage = (id: string) => request<VariantLineage>(`/workspace/scenarios/${encodeURIComponent(id)}/lineage`);
export const fetchEvidenceLayers = (id: string) => request<EvidenceLayers>(`/workspace/scenarios/${encodeURIComponent(id)}/evidence-layers`);
export const fetchCompare = (id: string, against: string, timeS: number) =>
  request<ComparePayload>(`/workspace/scenarios/${encodeURIComponent(id)}/compare?against=${encodeURIComponent(against)}&time_s=${encodeURIComponent(String(timeS))}`);
