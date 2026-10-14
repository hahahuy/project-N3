export type ActorSummary = {
  actor_id: string;
  actor_type: string;
  sample_count: number;
  length_m: number | null;
  width_m: number | null;
};

export type ArtifactLink = { kind: string; path: string; url: string };
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
export type WorkspaceDocument = { document_name: string; branch: string; version: string; active_scenario_id: string; connection: Availability; dataset: Availability; esmini: Availability; dataset_version: string | null; esmini_version: string | null; coordinate_frame: string; transform_version: string | null; provenance: Record<string, string> };
export type WorkspaceLayer = { available: boolean; unavailable_reason: string | null };
export type WorkspaceScenario = { scenario: ScenarioSummary; actors: Array<ActorSummary & { role: "ego" | "actor"; states: TrajectoryState[]; dimensions: Availability }>; paths: TrajectoryPath[]; layers: { recorded_path: WorkspaceLayer; generated_path: WorkspaceLayer; map_lanes: WorkspaceLayer; actor_dimensions: WorkspaceLayer; xodr_geometry: WorkspaceLayer; lidar: WorkspaceLayer }; metrics: { available: boolean; unavailable_reason: string | null; source: "replay_trace" | "none"; per_actor: Record<string, ReplayMetric> }; gates: GateResult[] };
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
};
export type PreviewRequest = {
  actor_edits: ActorMotionEdit[];
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
};

export type Validation = { valid: boolean; validation_version: string; reasons: Array<{ code: string; category: string; actor_id: string | null; state_index: number | null; observed: number | null; limit: number | null; message: string }> };
export type Ranking = { rankable: boolean; ranking_version: string; features: { minimum_distance_m: number | null; minimum_ttc_s: number | null; novelty: number; risk_signal: number }; breakdown: { risk_signal: number; novelty: number; replay_quality: number; feasibility_penalty: number; total: number } | null };
export type VariantResult = { variant_id: string; status: "valid" | "invalid" | "simulator-failed"; configuration: Record<string, number>; validation: Validation; ranking: Ranking | null; replay_metrics: TrajectoryResponse["replay_metrics"]; replay_metric_aggregate: ReplayMetricAggregate | null; gates: GateResult[]; simulator_error: string | null; replay_failure: Record<string, unknown> | null; artifacts: ArtifactLink[] };
export type BatchResults = { job: { job_id: string; status: string; scenario_id: string; generated: number; error: string | null }; manifest: Record<string, unknown>; counts: Record<string, number>; results: VariantResult[]; replay_metric_aggregate: ReplayMetricAggregate | null };
export type SettingsView = { project_root: string; artifact_root: string; output_root: string; dataset_root: string | null; dataset_version: string; artifact_root_exists: boolean; dataset_root_exists: boolean; source_scene_count: number };
export type EsminiCapability = { configured: boolean; available: boolean; executable: string | null; trace_converter: string | null; version: string | null; diagnostic: string };
export type ReplayJob = { job_id: string; scenario_id: string; status: "queued" | "running" | "completed" | "failed" | "timed-out"; error: string | null; failure_code: string | null; failure_message: string | null; tool_version: string | null; exit_code: number | null; timed_out: boolean; stdout: string; stderr: string; artifacts: Record<string, string>; metrics: Record<string, unknown>; started_at: string | null; finished_at: string | null };
export type SourceScene = { scene_token: string; name: string; description: string; sample_count: number; first_sample_token: string; last_sample_token: string; vehicle_candidate_count: number };
export type SourceSceneImportResponse = { scene: SourceScene; scenario_id: string; selected_actor_ids: string[]; artifact: ArtifactLink; scenario: ScenarioSummary };
export type CP1ReviewItem = { item_id: string; category: string; title: string; status: "blocked" | "ready" | "deferred" | "informational"; blocking: boolean; what_to_verify: string; owner_action: string; evidence: string[]; related_api: string[] };
export type CP1Review = { review_version: string; diagnostic_status: "diagnostic"; scientific_status: "PROVISIONAL"; scene: string; corridor_baseline: { states: number; matched_states: number; raw_match_rate: number; display: string; all_vehicle_rate: string; must_remain_unchanged: boolean }; scope_note: string; items: CP1ReviewItem[] };

const API = import.meta.env.VITE_API_URL ?? "/api";
export const apiUrl = (path: string) => `${API}${path}`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) throw new Error((await response.json()).detail ?? `Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export const fetchScenarios = () => request<ScenarioSummary[]>("/scenarios");
export const fetchScenario = (id: string) => request<ScenarioSummary>(`/scenarios/${encodeURIComponent(id)}`);
export const fetchWorkspaceDocument = (id: string) => request<WorkspaceDocument>(`/workspace/documents/${encodeURIComponent(id)}`);
export const fetchWorkspaceScenario = (id: string) => request<WorkspaceScenario>(`/workspace/scenarios/${encodeURIComponent(id)}`);
export const fetchTrajectory = (id: string) => request<TrajectoryResponse>(`/scenarios/${encodeURIComponent(id)}/trajectory`);
export const previewVariant = (scenarioId: string, body: PreviewRequest) => request<PreviewResponse>(`/scenarios/${encodeURIComponent(scenarioId)}/variants/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const createBatch = (body: object) => request<{ job_id: string }>("/batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchBatchResults = (id: string) => request<BatchResults>(`/batches/${id}/results`);
export const fetchBatchTrajectory = (jobId: string, variantId: string) => request<TrajectoryResponse>(`/batches/${jobId}/results/${encodeURIComponent(variantId)}/trajectory`);
export const exportBatchResult = (jobId: string, variantId: string) => request<{ variant_id: string; artifacts: ArtifactLink[] }>(`/batches/${jobId}/results/${encodeURIComponent(variantId)}/export`, { method: "POST" });
export const fetchSettings = () => request<SettingsView>("/settings");
export const fetchEsminiCapability = () => request<EsminiCapability>("/esmini");
export const createReplay = (scenarioId: string) => request<ReplayJob>("/replays", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario_id: scenarioId }) });
export const fetchReplay = (jobId: string) => request<ReplayJob>(`/replays/${encodeURIComponent(jobId)}`);
export const updateSettings = (body: object) => request<SettingsView>("/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchSourceScenes = () => request<SourceScene[]>("/source-scenes");
export const importSourceScene = (sceneToken: string, body: object = {}) => request<SourceSceneImportResponse>(`/source-scenes/${encodeURIComponent(sceneToken)}/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchCP1Review = () => request<CP1Review>("/cp1/review");
