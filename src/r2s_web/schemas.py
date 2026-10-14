"""Pydantic response and request models for the local demo API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from real2scenario import lane_road_match_evidence_from_dict


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
    ade_m: float | None = None
    fde_m: float | None = None
    coverage_status: str = "unknown"


class MetricAvailabilityView(BaseModel):
    """Explicit availability contract for replay metrics.

    Metrics are never fabricated and never defaulted to zero. A consumer can
    always tell whether a number is missing, and why, without inspecting the
    surrounding status fields.
    """

    available: bool
    unavailable_reason: str | None = None
    alignment_method: str | None = None
    source: Literal["replay_trace", "none"] = "none"
    per_actor: dict[str, ReplayMetricView] = Field(default_factory=dict)
    aggregate: "ReplayMetricAggregateView | None" = None


class MetricDistributionView(BaseModel):
    mean: float
    median: float
    p95: float
    max: float


class ReplayMetricAggregateView(BaseModel):
    actor_count: int
    ade_m: MetricDistributionView
    fde_m: MetricDistributionView | None


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


class CP1ReviewItem(BaseModel):
    item_id: str
    category: str
    title: str
    status: Literal["blocked", "ready", "deferred", "informational"]
    blocking: bool
    what_to_verify: str
    owner_action: str
    evidence: list[str]
    related_api: list[str] = Field(default_factory=list)


class CP1ReviewView(BaseModel):
    review_version: str
    diagnostic_status: Literal["diagnostic"]
    scientific_status: Literal["PROVISIONAL"]
    scene: str
    corridor_baseline: dict[str, object]
    scope_note: str
    items: list[CP1ReviewItem]


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


class EventDeclarationRequest(BaseModel):
    """Explicitly declared main-event window used by the G5 footprint gate."""

    model_config = ConfigDict(extra="forbid")
    main_event_start_s: float
    main_event_end_s: float
    event_type: str = Field(min_length=1)
    event_target_actor_id: str = Field(min_length=1)
    event_source: str = Field(default="operator_declared", min_length=1)

    def to_declaration(self) -> dict[str, object]:
        return {
            "main_event_start_s": self.main_event_start_s,
            "main_event_end_s": self.main_event_end_s,
            "event_type": self.event_type,
            "event_target_actor_id": self.event_target_actor_id,
            "event_source": self.event_source,
        }


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
    lane_match_evidence: dict[str, dict[str, object]] = Field(default_factory=dict)
    event_declaration: EventDeclarationRequest | None = None

    @field_validator("lane_match_evidence")
    @classmethod
    def validate_lane_match_evidence(cls, value: dict[str, dict[str, object]]):
        """Reject evidence the domain reader cannot validate, before any run."""
        for variant_id, payload in value.items():
            try:
                lane_road_match_evidence_from_dict(payload)
            except ValueError as error:
                raise ValueError(f"{variant_id}: {error}") from error
        return value


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    scenario_id: str
    generated: int = 0
    finished_at: str | None = None
    error: str | None = None


class ReplayRequest(BaseModel):
    scenario_id: str


class ReplayJobView(BaseModel):
    job_id: str
    scenario_id: str
    status: Literal["queued", "running", "completed", "failed", "timed-out"]
    error: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    tool_version: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, object] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None


class VariantResult(BaseModel):
    variant_id: str
    status: Literal["valid", "invalid", "simulator-failed"]
    configuration: dict[str, float | int]
    validation: ValidationView
    ranking: RankingView | None
    replay_metrics: dict[str, ReplayMetricView] = Field(default_factory=dict)
    replay_metric_aggregate: ReplayMetricAggregateView | None = None
    gates: list["GateResultView"] = Field(default_factory=list)
    simulator_error: str | None = None
    replay_failure: dict[str, object] | None = None
    artifacts: list[ArtifactLink]


class BatchResults(BaseModel):
    job: JobStatus
    manifest: dict[str, object]
    counts: dict[str, int]
    results: list[VariantResult]
    replay_metric_aggregate: ReplayMetricAggregateView | None = None
    replay_metrics: MetricAvailabilityView | None = None
    gate_funnel: dict[str, object] | None = None


class ExportResponse(BaseModel):
    variant_id: str
    artifacts: list[ArtifactLink]


class ActorMotionEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str
    speed_multiplier: float = Field(default=1.0, gt=0)
    heading_offset_rad: float = 0.0
    timing_offset_s: float = 0.0
    initial_gap_delta_m: float = 0.0


class GateResultView(BaseModel):
    gate_id: str
    status: Literal["pass", "fail", "skipped", "error"]
    reasons: list[str] = Field(default_factory=list)
    config_version: str | None = None
    observed: dict[str, object] | None = None
    scientific_status: str = "not-applicable"


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_edits: list[ActorMotionEditRequest] = Field(min_length=1)
    replay_mode: Literal["waypoint"] = "waypoint"
    behavior: Literal["parameterized", "behavior"] = "parameterized"
    seed: int = 0


class PreviewResponse(BaseModel):
    parent_scenario_id: str
    variant_id: str | None
    status: Literal["valid", "invalid", "unsupported"]
    behavior: dict[str, str]
    configuration: dict[str, object]
    provenance: dict[str, str]
    paths: list[TrajectoryPath] = Field(default_factory=list)
    validation: ValidationView | None = None
    gates: list[GateResultView] = Field(default_factory=list)
    replay_metrics: dict[str, ReplayMetricView] = Field(default_factory=dict)
    metrics: MetricAvailabilityView = Field(
        default_factory=lambda: MetricAvailabilityView(
            available=False, unavailable_reason="preview_has_no_simulator_trace"
        )
    )
    artifacts: list[ArtifactLink] = Field(default_factory=list)
