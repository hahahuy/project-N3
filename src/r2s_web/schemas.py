"""Pydantic response and request models for the local demo API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ActorSummary(BaseModel):
    actor_id: str
    actor_type: str
    sample_count: int
    length_m: float | None
    width_m: float | None


class ArtifactLink(BaseModel):
    kind: str
    path: str
    url: str


class ScenarioSummary(BaseModel):
    scenario_id: str
    parent_scenario_id: str | None
    artifact_type: Literal["baseline", "variant"]
    duration_s: float
    coordinate_frame: str
    actors: list[ActorSummary]
    provenance: dict[str, str]
    available_artifacts: list[ArtifactLink]


class TrajectoryState(BaseModel):
    time_s: float
    x_m: float
    y_m: float
    yaw_rad: float
    speed_mps: float


class TrajectoryPath(BaseModel):
    actor_id: str
    actor_type: str
    path_kind: Literal["recorded", "replayed", "generated"]
    states: list[TrajectoryState]


class ReplayMetricView(BaseModel):
    sample_count: int
    alignment_method: str
    position_rmse_m: float
    final_displacement_m: float
    heading_mae_rad: float
    speed_mae_mps: float


class TrajectoryResponse(BaseModel):
    scenario_id: str
    coordinate_frame: str
    duration_s: float
    map_warning: str
    paths: list[TrajectoryPath]
    replay_metrics: dict[str, ReplayMetricView] = Field(default_factory=dict)


class ScenarioDetail(ScenarioSummary):
    variant_config: dict[str, float | int] | None = None


class SourceScene(BaseModel):
    scene_token: str
    name: str
    description: str
    sample_count: int
    first_sample_token: str
    last_sample_token: str
    vehicle_candidate_count: int


class SourceSceneImportRequest(BaseModel):
    start_sample_token: str | None = None
    end_sample_token: str | None = None
    max_distance_m: float = Field(default=30.0, ge=0.0)
    max_ttc_s: float = Field(default=5.0, ge=0.0)
    max_actors: int = Field(default=3, ge=1, le=3)


class SourceSceneImportResponse(BaseModel):
    scene: SourceScene
    scenario_id: str
    selected_actor_ids: list[str]
    artifact: ArtifactLink
    scenario: ScenarioSummary


class SettingsUpdateRequest(BaseModel):
    artifact_root: str | None = None
    output_root: str | None = None
    dataset_root: str | None = None
    dataset_version: str | None = None


class SettingsView(BaseModel):
    project_root: str
    artifact_root: str
    output_root: str
    dataset_root: str | None
    dataset_version: str
    artifact_root_exists: bool
    dataset_root_exists: bool
    source_scene_count: int


class ValidationReasonView(BaseModel):
    code: str
    category: str
    actor_id: str | None
    state_index: int | None
    observed: float | None
    limit: float | None
    message: str


class ValidationView(BaseModel):
    valid: bool
    validation_version: str
    reasons: list[ValidationReasonView]


class RankingFeatureView(BaseModel):
    minimum_distance_m: float | None
    minimum_ttc_s: float | None
    novelty: float
    risk_signal: float


class ScoreBreakdownView(BaseModel):
    risk_signal: float
    novelty: float
    replay_quality: float
    feasibility_penalty: float
    total: float


class RankingView(BaseModel):
    rankable: bool
    ranking_version: str
    features: RankingFeatureView
    breakdown: ScoreBreakdownView | None


class RoadBoundaryRequest(BaseModel):
    min_x_m: float
    max_x_m: float
    min_y_m: float
    max_y_m: float


class ValidationLimitsRequest(BaseModel):
    max_acceleration_mps2: float = 5.0
    max_deceleration_mps2: float = 8.0
    max_jerk_mps3: float = 20.0
    max_yaw_rate_rps: float = 1.5
    road_boundary: RoadBoundaryRequest | None = None


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    generation_mode: Literal["grid", "random"] = "grid"
    speed_multipliers: list[float] = Field(default_factory=lambda: [0.9, 1.0])
    initial_gap_deltas_m: list[float] = Field(default_factory=lambda: [-2.0, 0.0])
    timing_offsets_s: list[float] = Field(default_factory=lambda: [0.0, 0.25, 0.5, 0.75, 1.0])
    count: int = Field(default=20, ge=1, le=200)
    speed_multiplier_range: tuple[float, float] = (0.8, 1.2)
    initial_gap_delta_range_m: tuple[float, float] = (-5.0, 2.0)
    timing_offset_range_s: tuple[float, float] = (0.0, 0.5)
    seed: int = 7
    validation_limits: ValidationLimitsRequest = Field(default_factory=ValidationLimitsRequest)
    replay_enabled: bool = False


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    scenario_id: str
    generated: int = 0
    finished_at: str | None = None
    error: str | None = None


class VariantResult(BaseModel):
    variant_id: str
    status: Literal["valid", "invalid", "simulator-failed"]
    configuration: dict[str, float | int]
    validation: ValidationView
    ranking: RankingView | None
    replay_metrics: dict[str, ReplayMetricView] = Field(default_factory=dict)
    simulator_error: str | None = None
    replay_failure: dict[str, object] | None = None
    artifacts: list[ArtifactLink]


class BatchResults(BaseModel):
    job: JobStatus
    manifest: dict[str, object]
    counts: dict[str, int]
    results: list[VariantResult]


class ExportResponse(BaseModel):
    variant_id: str
    artifacts: list[ArtifactLink]
