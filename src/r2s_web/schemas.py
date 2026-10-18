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
    source_timestamp_us: int | None = None
    source_record_token: str | None = None


class TrajectoryPath(BaseModel):
    actor_id: str
    actor_type: str
    path_kind: Literal["recorded", "replayed", "generated"]
    states: list[TrajectoryState]


class CanvasKeyframeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyframe_id: str = Field(min_length=1)
    time_s: float = Field(ge=0)
    x_m: float
    y_m: float
    yaw_rad: float
    speed_mps: float = Field(ge=0)


class CanvasBranchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str = Field(min_length=1)
    keyframes: list[CanvasKeyframeRequest] = Field(min_length=2)
    coordinate_frame: Literal["local_road_aligned"] = "local_road_aligned"
    branch_name: str | None = None
    seed: int = 0
    include_origin_reference: bool = False


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
    surrounding status fields. Provenance and scientific status travel with the
    block so a metric is never shown without them.
    """

    available: bool
    unavailable_reason: str | None = None
    alignment_method: str | None = None
    source: Literal["replay_trace", "none"] = "none"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"
    provenance: dict[str, str] = Field(default_factory=dict)
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


class AvailabilityView(BaseModel):
    available: bool
    unavailable_reason: str | None = None


class SimulatorCapabilityView(AvailabilityView):
    simulator: str
    version: str | None = None
    frame_contract: str | None = None
    modes: list[str] = Field(default_factory=list)
    rendering: str | None = None


class POVFrameView(BaseModel):
    contract_version: str
    frame_id: str
    mode: Literal["third-person", "in-car"]
    status: Literal["rendered", "unavailable", "error"]
    simulator: str
    simulator_version: str | None
    timestamp_s: float
    coordinate_frame: str
    transform_version: str | None
    camera_transform: dict[str, object]
    actors: list[dict[str, object]]
    provenance: dict[str, str]


class LiveSessionCreateRequest(BaseModel):
    scenario_id: str
    xosc_path: str
    xodr_path: str
    timestep_s: float = 0.05


class LiveScenarioPairRequest(BaseModel):
    scenario_id: str
    timestep_s: float = 0.05


class WasmScenarioPairView(BaseModel):
    scenario_id: str
    coordinate_frame: str
    map_warning: str
    openscenario: str
    opendrive: str
    artifact_visibility: str


class LiveSessionCommandRequest(BaseModel):
    command: Literal["pause", "resume", "step", "reset", "control", "camera"]
    payload: dict[str, object] = Field(default_factory=dict)


class POVImageFrameView(BaseModel):
    """A real private esmini image artifact, or an explicit unavailable state."""

    contract_version: Literal["workspace-pov-image-v1"]
    scenario_id: str
    mode: Literal["third-person", "in-car"]
    status: Literal["rendered", "unavailable", "error"]
    frame_id: str | None = None
    timestamp_s: float | None = None
    simulator: str
    simulator_version: str | None = None
    artifact: ArtifactLink | None = None
    unavailable_reason: str | None = None
    provenance: dict[str, str] = Field(default_factory=dict)


class ParentSweepStatusView(BaseModel):
    available: bool
    scenario_id: str | None = None
    sample_data_token: str | None = None
    timestamp_us: int | None = None
    source: str
    unavailable_reason: str | None = None


class VariantSensorStatusView(BaseModel):
    contract_version: Literal["workspace-variant-sensor-v1"]
    scenario_id: str
    artifact_type: Literal["baseline", "variant"]
    status: Literal["available", "unavailable", "unsupported"]
    post_edit_frames: AvailabilityView
    parent_sweep: ParentSweepStatusView
    unavailable_reason: str | None = None
    provenance: dict[str, str] = Field(default_factory=dict)
    artifact_visibility: str = "local_private"


class WorkspaceDocumentView(BaseModel):
    document_name: str
    branch: str
    version: str
    active_scenario_id: str
    connection: AvailabilityView
    dataset: AvailabilityView
    esmini: AvailabilityView
    dataset_version: str | None
    esmini_version: str | None
    coordinate_frame: str
    transform_version: str | None
    provenance: dict[str, str]
    native_map: AvailabilityView
    simulator_frames: SimulatorCapabilityView


class ActorPoseView(BaseModel):
    actor_id: str
    actor_type: str
    role: Literal["ego", "actor"]
    states: list[TrajectoryState]
    dimensions: AvailabilityView
    length_m: float | None
    width_m: float | None
    height_m: float | None = None


class ScenarioLayerView(BaseModel):
    recorded_path: AvailabilityView
    generated_path: AvailabilityView
    map_lanes: AvailabilityView
    actor_dimensions: AvailabilityView
    xodr_geometry: AvailabilityView
    lidar: AvailabilityView
    third_person: SimulatorCapabilityView
    in_car: SimulatorCapabilityView


class NativeMapView(BaseModel):
    version: str
    status: str
    map_name: str
    layers: dict[str, list[dict[str, object]]] = Field(default_factory=dict)
    artifact_visibility: str = "local_private"


class ScenarioViewPayload(BaseModel):
    scenario: ScenarioSummary
    actors: list[ActorPoseView]
    paths: list[TrajectoryPath]
    layers: ScenarioLayerView
    metrics: MetricAvailabilityView
    evidence_layers: "EvidenceLayersView | None" = None
    sensor_status: VariantSensorStatusView | None = None
    gates: list["GateSegmentView"] = Field(default_factory=list)
    native_map: NativeMapView | None = None
    time_s: float = 0.0
    simulator_frames: SimulatorCapabilityView


class LineageNodeView(BaseModel):
    scenario_id: str
    artifact_type: str
    present: bool
    unavailable_reason: str | None = None


class BranchIdentityView(BaseModel):
    branch_id: str
    branch_name: str | None = None
    root_scenario_id: str
    branch_id_source: str
    branch_name_source: str | None = None
    branch_name_unavailable_reason: str | None = None


class VariantLineageView(BaseModel):
    contract_version: Literal["workspace-variant-lineage-v1"]
    scenario_id: str
    artifact_type: str
    artifact_path: str
    coordinate_frame: str
    lineage_path: list[LineageNodeView]
    lineage_depth: int
    branch: BranchIdentityView
    child_scenario_ids: list[str] = Field(default_factory=list)
    fields: dict[str, object]
    unavailable_reasons: dict[str, str | None]
    provenance: dict[str, str] = Field(default_factory=dict)
    artifact_visibility: str


class EvidenceLayerView(BaseModel):
    layer: Literal["recorded", "generated", "replayed", "sensor-evidence"]
    status: Literal["available", "unavailable", "unsupported"]
    unavailable_reason: str | None = None
    source: str
    scientific_status: str
    provenance: dict[str, str] = Field(default_factory=dict)
    coverage: float | None = None
    reference: str = ""
    parent_fallback: dict[str, object] | None = None


class EvidenceLayersView(BaseModel):
    contract_version: Literal["workspace-evidence-layers-v1"]
    scenario_id: str
    coordinate_frame: str
    layers: list[EvidenceLayerView]
    available_count: int
    artifact_visibility: str


class CompareSideView(BaseModel):
    scenario_id: str
    artifact_type: str
    parent_scenario_id: str | None = None
    branch_id: str
    branch_name: str | None = None
    seed: int | None = None
    config_hash: str | None = None
    coordinate_frame: str
    duration_s: float
    layer_kinds: list[str] = Field(default_factory=list)
    evidence_layers: list[EvidenceLayerView]


class CompareActorStateView(BaseModel):
    status: Literal["measured", "unavailable"]
    unavailable_reason: str | None = None
    x_m: float | None = None
    y_m: float | None = None
    yaw_rad: float | None = None
    speed_mps: float | None = None


class CompareActorView(BaseModel):
    actor_id: str
    actor_type: str | None = None
    role: str | None = None
    left: CompareActorStateView
    right: CompareActorStateView
    position_delta_m: float | None = None
    heading_delta_rad: float | None = None
    speed_delta_mps: float | None = None
    delta_unavailable_reason: str | None = None


class CompareMetricRowView(BaseModel):
    metric: str
    left_value: float | None = None
    left_status: str
    left_reason: str | None = None
    right_value: float | None = None
    right_status: str
    right_reason: str | None = None
    delta: float | None = None
    delta_unavailable_reason: str | None = None
    unit: str
    scientific_status: str


class CompareGateView(BaseModel):
    gate_id: str
    left_status: str | None = None
    right_status: str | None = None
    differs: bool
    left_scientific_status: str | None = None
    right_scientific_status: str | None = None
    left_reasons: list[str] = Field(default_factory=list)
    right_reasons: list[str] = Field(default_factory=list)


class CompareView(BaseModel):
    contract_version: Literal["workspace-compare-v1"]
    synchronization: dict[str, object]
    sides: list[CompareSideView]
    actors: list[CompareActorView]
    metrics: list[CompareMetricRowView]
    metric_provenance: dict[str, object]
    gates: list[CompareGateView]
    metric_scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"
    artifact_visibility: str


class SourceScene(BaseModel):
    scene_token: str
    name: str
    description: str
    sample_count: int
    first_sample_token: str
    last_sample_token: str
    vehicle_candidate_count: int
    pedestrian_candidate_count: int = 0


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


class CanvasBranchResponse(BaseModel):
    parent_scenario_id: str
    scenario: ScenarioSummary
    validation: ValidationView
    artifacts: list[ArtifactLink]
    wasm_pair: WasmScenarioPairView | None = None
    sensor_status: dict[str, object]


class TestingPhysicsResponse(BaseModel):
    status: str
    mode: str
    world: str
    server_version: str
    collision_count: int
    collisions: list[dict[str, object]]
    metrics: dict[str, object]
    trace: list[TrajectoryState]
    physics_enabled: bool
    same_xosc: bool
    sensor_output: bool


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
    max_acceleration_mps2: float = 10.0
    max_deceleration_mps2: float = 8.0
    max_jerk_mps3: float = 20.0
    max_yaw_rate_rps: float = 2.5
    max_speed_mps: float = 20.0
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
    steering_angle_rad: float = 0.0
    acceleration_mps2: float | None = None
    braking_mps2: float | None = None
    target_speed_mps: float | None = Field(default=None, ge=0)
    start_time_s: float = Field(default=0.0, ge=0)
    end_time_s: float | None = Field(default=None, ge=0)

    @field_validator("acceleration_mps2", "braking_mps2", "steering_angle_rad")
    @classmethod
    def finite_maneuver_values(cls, value):
        if value is not None and not isinstance(value, (int, float)):
            raise ValueError("maneuver values must be numeric")
        return value


class RecipeStepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str
    name: str = Field(min_length=1)
    kind: Literal["constrained-maneuver"] = "constrained-maneuver"
    actor_edit: ActorMotionEditRequest
    active: bool = True

    @field_validator("step_id")
    @classmethod
    def non_empty_step_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("step_id must not be empty")
        return value


class RecipeStepStateRequest(BaseModel):
    """Activate or deactivate one ordered step without removing it."""

    model_config = ConfigDict(extra="forbid")
    active: bool


class StepMoveRequest(BaseModel):
    """Move one step by exactly one position in the ordered recipe."""

    model_config = ConfigDict(extra="forbid")
    step_id: str
    direction: Literal["up", "down"]


class RollbackMarkerRequest(BaseModel):
    """Name the current ordered step count as a rollback point."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def non_empty_marker_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rollback marker name must not be empty")
        return value.strip()


class RecipeStepViolationView(BaseModel):
    code: str
    actor_id: str
    observed: float
    limit: float
    provenance: str


class RecipeStepView(BaseModel):
    index: int
    step_id: str
    name: str
    kind: Literal["constrained-maneuver"]
    status: Literal["valid", "invalid", "error"]
    active: bool
    inactive_reason: str | None = None
    parameters: ActorMotionEditRequest
    violations: list[RecipeStepViolationView] = Field(default_factory=list)
    error: str | None = None
    artifact: ArtifactLink | None = None
    artifact_unavailable_reason: str | None = None


class RollbackMarkerView(BaseModel):
    marker_id: str
    name: str
    step_count: int
    revision: int


class RecipeHistoryView(BaseModel):
    revision: int
    undo_depth: int
    redo_depth: int
    non_destructive: bool
    undoable: bool
    redoable: bool
    undo_unavailable_reason: str | None
    redo_unavailable_reason: str | None


class RecipeDocumentView(BaseModel):
    contract_version: Literal["workspace-recipe-v1"]
    scenario_id: str
    coordinate_frame: str
    parent_scenario_id: str | None = None
    parent_immutable: bool
    mutation: str
    persistence: AvailabilityView
    limits: dict[str, object] = Field(default_factory=dict)
    steps: list[RecipeStepView] = Field(default_factory=list)
    step_count: int = 0
    active_step_count: int = 0
    rollback_markers: list[RollbackMarkerView] = Field(default_factory=list)
    active_marker_id: str | None = None
    history: RecipeHistoryView
    artifact_visibility: str


class GateResultView(BaseModel):
    gate_id: str
    status: Literal["pass", "fail", "skipped", "error"]
    reasons: list[str] = Field(default_factory=list)
    config_version: str | None = None
    observed: dict[str, object] | None = None
    scientific_status: str = "not-applicable"


class ChannelAvailabilityView(BaseModel):
    """Explicit availability contract for one time-indexed actor channel."""

    available: bool
    unavailable_reason: str | None
    version: str
    coverage: float | None = None


class TimelineSampleView(BaseModel):
    time_s: float
    x_m: float
    y_m: float
    yaw_rad: float
    speed_mps: float
    acceleration_mps2: float | None = None
    acceleration_source: str | None = None
    braking_pressure: float | None = None
    braking_source: str | None = None


class ActorTrackView(BaseModel):
    actor_id: str
    actor_type: str
    role: Literal["ego", "actor"]
    channels: dict[str, ChannelAvailabilityView]
    samples: list[TimelineSampleView]


class ActorTimelineView(BaseModel):
    contract_version: str
    scenario_id: str
    coordinate_frame: str
    time_domain: dict[str, float]
    tracks: list[ActorTrackView]
    artifact_visibility: str


class GateSegmentView(BaseModel):
    gate_id: str
    status: Literal["pass", "fail", "skipped", "error", "unsupported"]
    scientific_status: str
    reasons: list[str] = Field(default_factory=list)
    config_version: str | None = None
    observed: dict[str, object] | None = None
    start_s: float
    end_s: float
    extent_source: str


class GateTimelineView(BaseModel):
    contract_version: str
    scenario_id: str
    coordinate_frame: str
    time_domain: dict[str, float]
    gates: list[GateSegmentView]
    counts: dict[str, int]
    provisional_count: int
    artifact_visibility: str


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_edits: list[ActorMotionEditRequest] = Field(min_length=1)
    recipe_steps: list[RecipeStepRequest] = Field(default_factory=list)
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
    recipe_steps: list[dict[str, object]] = Field(default_factory=list)
    limits: dict[str, object] = Field(default_factory=dict)
    violations: list[dict[str, object]] = Field(default_factory=list)
    rollback_marker: dict[str, object] | None = None
