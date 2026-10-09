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
export type TrajectoryResponse = {
  scenario_id: string;
  coordinate_frame: string;
  duration_s: number;
  map_warning: string;
  paths: TrajectoryPath[];
  replay_metrics: Record<string, { sample_count: number; position_rmse_m: number; final_displacement_m: number; heading_mae_rad: number; speed_mae_mps: number; alignment_method: string }>;
};

export type Validation = { valid: boolean; validation_version: string; reasons: Array<{ code: string; category: string; actor_id: string | null; state_index: number | null; observed: number | null; limit: number | null; message: string }> };
export type Ranking = { rankable: boolean; ranking_version: string; features: { minimum_distance_m: number | null; minimum_ttc_s: number | null; novelty: number; risk_signal: number }; breakdown: { risk_signal: number; novelty: number; replay_quality: number; feasibility_penalty: number; total: number } | null };
export type VariantResult = { variant_id: string; status: "valid" | "invalid" | "simulator-failed"; configuration: Record<string, number>; validation: Validation; ranking: Ranking | null; replay_metrics: TrajectoryResponse["replay_metrics"]; simulator_error: string | null; replay_failure: Record<string, unknown> | null; artifacts: ArtifactLink[] };
export type BatchResults = { job: { job_id: string; status: string; scenario_id: string; generated: number; error: string | null }; manifest: Record<string, unknown>; counts: Record<string, number>; results: VariantResult[] };
export type SettingsView = { project_root: string; artifact_root: string; output_root: string; dataset_root: string | null; dataset_version: string; artifact_root_exists: boolean; dataset_root_exists: boolean; source_scene_count: number };
export type SourceScene = { scene_token: string; name: string; description: string; sample_count: number; first_sample_token: string; last_sample_token: string; vehicle_candidate_count: number };
export type SourceSceneImportResponse = { scene: SourceScene; scenario_id: string; selected_actor_ids: string[]; artifact: ArtifactLink; scenario: ScenarioSummary };

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";
export const apiUrl = (path: string) => `${API}${path}`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) throw new Error((await response.json()).detail ?? `Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export const fetchScenarios = () => request<ScenarioSummary[]>("/scenarios");
export const fetchScenario = (id: string) => request<ScenarioSummary>(`/scenarios/${encodeURIComponent(id)}`);
export const fetchTrajectory = (id: string) => request<TrajectoryResponse>(`/scenarios/${encodeURIComponent(id)}/trajectory`);
export const createBatch = (body: object) => request<{ job_id: string }>("/batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchBatchResults = (id: string) => request<BatchResults>(`/batches/${id}/results`);
export const fetchBatchTrajectory = (jobId: string, variantId: string) => request<TrajectoryResponse>(`/batches/${jobId}/results/${encodeURIComponent(variantId)}/trajectory`);
export const exportBatchResult = (jobId: string, variantId: string) => request<{ variant_id: string; artifacts: ArtifactLink[] }>(`/batches/${jobId}/results/${encodeURIComponent(variantId)}/export`, { method: "POST" });
export const fetchSettings = () => request<SettingsView>("/settings");
export const updateSettings = (body: object) => request<SettingsView>("/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchSourceScenes = () => request<SourceScene[]>("/source-scenes");
export const importSourceScene = (sceneToken: string, body: object = {}) => request<SourceSceneImportResponse>(`/source-scenes/${encodeURIComponent(sceneToken)}/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
