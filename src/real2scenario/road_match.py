"""Diagnostic lane-centerline road matching for CP1."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from math import atan2, cos, hypot, isfinite, sin
from statistics import quantiles
from typing import Literal, Mapping
from xml.etree import ElementTree as ET

from .models import Actor, Scenario, State

ROAD_MATCH_VERSION = "lane-road-match-v1"
CANDIDATE_DIAGNOSTIC_VERSION = "lane-road-candidates-v1"
FOOTPRINT_OCCUPANCY_VERSION = "lane-footprint-occupancy-v1"
LANE_SEQUENCE_MATCH_VERSION = "lane-sequence-match-v1"
LANE_GRAPH_VERSION = "lane-graph-v1"
ACTOR_REFERENCE_SENSITIVITY_VERSION = "actor-reference-sensitivity-v1"
DIRECTION_COUNTERFACTUAL_VERSION = "direction-counterfactual-v1"


@dataclass(frozen=True, slots=True)
class LaneCenterlinePose:
    x_m: float
    y_m: float
    yaw_rad: float

    def __post_init__(self) -> None:
        if not all(isfinite(value) for value in (self.x_m, self.y_m, self.yaw_rad)):
            raise ValueError("LaneCenterlinePose values must be finite.")


@dataclass(frozen=True, slots=True)
class LaneCenterlineRecord:
    lane_id: str
    poses: tuple[LaneCenterlinePose, ...]
    source_id: str | None = None
    predecessor_ids: tuple[str, ...] = ()
    successor_ids: tuple[str, ...] = ()
    legal_lane_change_ids: tuple[str, ...] = ()
    junction_id: str | None = None
    is_connector: bool = False
    travel_direction: Literal["forward", "reverse"] = "forward"
    polygon: tuple[tuple[float, float], ...] | None = None
    width_m: float | None = None
    width_source: str = "unspecified"

    def __post_init__(self) -> None:
        if not self.lane_id:
            raise ValueError("LaneCenterlineRecord lane_id must not be empty.")
        if len(self.poses) < 2:
            raise ValueError("LaneCenterlineRecord poses must contain at least two poses.")
        if self.travel_direction not in ("forward", "reverse"):
            raise ValueError("travel_direction must be 'forward' or 'reverse'.")
        if self.width_m is not None and (not isfinite(self.width_m) or self.width_m <= 0):
            raise ValueError("LaneCenterlineRecord width_m must be finite and positive.")
        if self.polygon is not None and len(self.polygon) < 3:
            raise ValueError("LaneCenterlineRecord polygon must contain at least three points.")


@dataclass(frozen=True, slots=True)
class LaneWidthRecord:
    lane_id: str
    width_m: float
    source: str = "unspecified"

    def __post_init__(self) -> None:
        if not self.lane_id or not self.source:
            raise ValueError("LaneWidthRecord identifiers must not be empty.")
        if not isfinite(self.width_m) or self.width_m <= 0:
            raise ValueError("LaneWidthRecord width_m must be finite and positive.")


@dataclass(frozen=True, slots=True)
class LaneRoadMatchConfig:
    max_distance_m: float = 0.5
    max_heading_error_rad: float = 0.2

    def __post_init__(self) -> None:
        if not isfinite(self.max_distance_m) or self.max_distance_m < 0:
            raise ValueError("max_distance_m must be finite and non-negative.")
        if not isfinite(self.max_heading_error_rad) or self.max_heading_error_rad < 0:
            raise ValueError("max_heading_error_rad must be finite and non-negative.")


@dataclass(frozen=True, slots=True)
class LaneRoadMatchState:
    actor_id: str
    state_index: int
    state: State
    lane_id: str
    segment_index: int
    projection_t: float
    distance_m: float
    heading_error_rad: float
    matched: bool
    reason: str


@dataclass(frozen=True, slots=True)
class LaneRoadMatchSummary:
    state_count: int
    matched_state_count: int
    raw_match_rate: float
    provisional_95_status: Literal["at_or_above_95_percent", "below_95_percent"]

    def __post_init__(self) -> None:
        if self.state_count <= 0 or not 0 <= self.matched_state_count <= self.state_count:
            raise ValueError("LaneRoadMatchSummary counts are invalid.")
        expected = self.matched_state_count / self.state_count
        if abs(self.raw_match_rate - expected) > 1e-12:
            raise ValueError("raw_match_rate does not match state counts.")
        expected_status = "at_or_above_95_percent" if expected >= 0.95 else "below_95_percent"
        if self.provisional_95_status != expected_status:
            raise ValueError("provisional_95_status does not match raw_match_rate.")


@dataclass(frozen=True, slots=True)
class LaneRoadMatchActor:
    actor_id: str
    summary: LaneRoadMatchSummary


@dataclass(frozen=True, slots=True)
class LaneRoadMatchReport:
    algorithm_version: str
    scenario_id: str
    coordinate_frame: str
    config: LaneRoadMatchConfig
    selected_actor_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    state_matches: tuple[LaneRoadMatchState, ...]
    per_actor: tuple[LaneRoadMatchActor, ...]
    overall: LaneRoadMatchSummary
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class LaneCandidateEvidence:
    rank: int
    lane_id: str
    segment_index: int
    projection_t: float
    distance_m: float
    signed_lateral_offset_m: float
    heading_error_rad: float
    distance_ok: bool
    heading_ok: bool
    passes_centerline_tolerances: bool
    reason: str


@dataclass(frozen=True, slots=True)
class LaneCandidateStateDiagnostic:
    actor_id: str
    state_index: int
    state: State
    candidate_count: int
    candidates: tuple[LaneCandidateEvidence, ...]


@dataclass(frozen=True, slots=True)
class LaneCandidateReport:
    algorithm_version: str
    scenario_id: str
    coordinate_frame: str
    selected_actor_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    states: tuple[LaneCandidateStateDiagnostic, ...]
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class LaneGraphLane:
    """Direction-normalized lane geometry used only by semantic diagnostics."""

    lane_id: str
    source_id: str
    poses: tuple[LaneCenterlinePose, ...]
    cumulative_s_m: tuple[float, ...]
    predecessor_ids: tuple[str, ...] = ()
    successor_ids: tuple[str, ...] = ()
    legal_lane_change_ids: tuple[str, ...] = ()
    junction_id: str | None = None
    is_connector: bool = False
    travel_direction: Literal["forward", "reverse"] = "forward"
    polygon: tuple[tuple[float, float], ...] | None = None
    width_m: float | None = None
    width_source: str = "unspecified"

    @property
    def length_m(self) -> float:
        return self.cumulative_s_m[-1]

    @property
    def successor_set(self) -> frozenset[str]:
        return frozenset(self.successor_ids)


@dataclass(frozen=True, slots=True)
class LaneGraphValidation:
    lane_id: str
    valid: bool
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LaneGraph:
    lanes: tuple[LaneGraphLane, ...]
    validation: tuple[LaneGraphValidation, ...]
    algorithm_version: str = LANE_GRAPH_VERSION

    @property
    def by_id(self) -> dict[str, LaneGraphLane]:
        return {lane.lane_id: lane for lane in self.lanes}


@dataclass(frozen=True, slots=True)
class LaneSequenceMatchConfig:
    candidate_radius_m: float = 8.0
    max_candidates: int = 5
    position_sigma_m: float = 1.0
    heading_sigma_rad: float = 0.35
    position_weight: float = 1.0
    annotation_heading_weight: float = 1.0
    motion_heading_weight: float = 1.0
    outside_polygon_penalty: float = 4.0
    boundary_penalty: float = 1.0
    lane_change_penalty: float = 2.0
    reverse_direction_penalty: float = 8.0
    topology_gap_penalty: float = 12.0
    speed_sigma_mps: float = 3.0
    confidence_margin: float = 2.0
    persistent_lateral_error_m: float = 2.0
    allow_topology_gaps: bool = True

    def __post_init__(self) -> None:
        positive = ("candidate_radius_m", "position_sigma_m", "heading_sigma_rad", "speed_sigma_mps")
        nonnegative = ("position_weight", "annotation_heading_weight", "motion_heading_weight",
                       "outside_polygon_penalty", "boundary_penalty", "lane_change_penalty",
                       "reverse_direction_penalty", "topology_gap_penalty", "confidence_margin",
                       "persistent_lateral_error_m")
        for name in positive:
            value = getattr(self, name)
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive.")
        for name in nonnegative:
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative.")
        if isinstance(self.max_candidates, bool) or not isinstance(self.max_candidates, int) or self.max_candidates <= 0:
            raise ValueError("max_candidates must be a positive integer.")


@dataclass(frozen=True, slots=True)
class LaneSequenceCandidate:
    lane_id: str | None
    segment_index: int
    projected_s_m: float
    lateral_distance_m: float
    signed_lateral_offset_m: float
    annotation_heading_error_rad: float
    motion_heading_error_rad: float | None
    inside_polygon: bool | None
    distance_to_polygon_boundary_m: float | None
    lane_direction: Literal["forward", "reverse"]
    reverse_direction: bool
    rank: int
    rejection_reason: str
    emission_cost: float


@dataclass(frozen=True, slots=True)
class LaneSequenceStateMatch:
    actor_id: str
    state_index: int
    source_timestamp_us: int | None
    source_record_token: str | None
    best_lane_id: str | None
    best_candidate_rank: int | None
    projected_s: float | None
    signed_lateral_offset_m: float | None
    annotation_heading_error_rad: float | None
    motion_heading_error_rad: float | None
    inside_polygon: bool | None
    best_score: float
    second_best_score: float | None
    score_margin: float | None
    confidence: float
    status: str
    direction_classification: str
    alternatives: tuple[LaneSequenceCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class LaneSequenceReviewInterval:
    actor_id: str
    start_state_index: int
    end_state_index: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LaneSequenceTrackSummary:
    actor_id: str
    matched_state_count: int
    high_confidence_state_count: int
    low_confidence_state_count: int
    ambiguous_state_count: int
    unmatched_state_count: int
    mean_lateral_error_m: float | None
    p95_lateral_error_m: float | None
    max_heading_error_rad: float | None
    topology_violation_count: int
    lane_switch_count: int
    unsupported_occupancy_count: int
    ambiguous_intervals: tuple[LaneSequenceReviewInterval, ...]
    total_score: float


@dataclass(frozen=True, slots=True)
class LaneSequenceMatchReport:
    algorithm_version: str
    scenario_id: str
    coordinate_frame: str
    config: LaneSequenceMatchConfig
    lane_graph: LaneGraph
    selected_actor_ids: tuple[str, ...]
    states: tuple[LaneSequenceStateMatch, ...]
    per_actor: tuple[LaneSequenceTrackSummary, ...]
    geometry_validation_failures: tuple[str, ...]
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class LaneAlignmentHypothesis:
    name: str
    translation_x_m: float
    translation_y_m: float
    yaw_offset_rad: float
    mean_lateral_error_m: float | None
    matched_state_count: int
    actor_count: int


@dataclass(frozen=True, slots=True)
class LaneSequenceTriageReport:
    algorithm_version: str
    sequence_report: LaneSequenceMatchReport
    alignment_hypotheses: tuple[LaneAlignmentHypothesis, ...]
    nearest_lane_changes: tuple[tuple[str, int, str, str | None], ...]
    rank_gt_one_states: tuple[tuple[str, int, int], ...]
    direction_counts: tuple[tuple[str, int], ...]
    manual_review_intervals: tuple[LaneSequenceReviewInterval, ...]
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class LaneReferenceStateDiagnostic:
    reference_name: str
    actor_id: str
    state_index: int
    lane_id: str | None
    source_id: str | None
    lateral_distance_m: float | None
    signed_lateral_offset_m: float | None
    inside_polygon: bool | None
    distance_to_boundary_m: float | None
    annotation_heading_error_rad: float | None
    motion_heading_error_rad: float | None
    topology_valid: bool | None
    status: str
    lane_heading_rad: float | None = None
    motion_heading_rad: float | None = None


@dataclass(frozen=True, slots=True)
class LaneReferenceSummary:
    reference_name: str
    state_count: int
    lane_semantically_valid_count: int
    lane_centerline_offset_high_count: int
    lane_polygon_outside_count: int
    footprint_unsupported_count: int
    heading_conflict_count: int
    topology_invalid_count: int
    unmatched_count: int
    mean_lateral_error_m: float | None
    p95_lateral_error_m: float | None
    max_heading_error_rad: float | None


@dataclass(frozen=True, slots=True)
class LaneReferenceComparisonReport:
    algorithm_version: str
    scenario_id: str
    coordinate_frame: str
    reference_names: tuple[str, ...]
    state_diagnostics: tuple[LaneReferenceStateDiagnostic, ...]
    summaries: tuple[LaneReferenceSummary, ...]
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class ActorReferenceHypothesis:
    """A globally declared, diagnostic-only actor reference convention."""

    name: Literal["annotation_center", "rear_axle", "front_axle", "fixed_heading_offset"]
    offset_m: float

    def __post_init__(self) -> None:
        if not isfinite(self.offset_m):
            raise ValueError("Actor reference offset must be finite.")


@dataclass(frozen=True, slots=True)
class ActorReferenceSensitivityRow:
    hypothesis: str
    reference_name: str
    actor_id: str
    state_count: int
    supported_state_count: int
    unsupported_state_count: int
    mean_lateral_error_m: float | None
    p95_lateral_error_m: float | None
    polygon_inside_count: int
    heading_conflict_count: int


@dataclass(frozen=True, slots=True)
class ActorReferenceSensitivityReport:
    algorithm_version: str
    scenario_id: str
    coordinate_frame: str
    hypotheses: tuple[ActorReferenceHypothesis, ...]
    rows: tuple[ActorReferenceSensitivityRow, ...]
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class DirectionCounterfactualState:
    reference_name: str
    actor_id: str
    state_index: int
    annotation_yaw_rad: float
    motion_heading_rad: float | None
    lane_heading_rad: float | None
    annotation_heading_error_rad: float | None
    motion_heading_error_rad: float | None
    classification: str


@dataclass(frozen=True, slots=True)
class DirectionCounterfactualReport:
    algorithm_version: str
    scenario_id: str
    coordinate_frame: str
    states: tuple[DirectionCounterfactualState, ...]
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


@dataclass(frozen=True, slots=True)
class LaneFootprintOccupancyState:
    actor_id: str
    state_index: int
    state: State
    lane_id: str
    segment_index: int
    candidate_rank: int
    lane_width_m: float | None
    lane_width_source: str | None
    signed_lateral_offset_m: float | None
    footprint_lateral_extent_m: float | None
    occupied: bool | None
    reason: str


@dataclass(frozen=True, slots=True)
class LaneFootprintOccupancyReport:
    algorithm_version: str
    scenario_id: str
    coordinate_frame: str
    selected_actor_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    states: tuple[LaneFootprintOccupancyState, ...]
    config: LaneRoadMatchConfig
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"


def diagnose_lane_road_match(
    scenario: Scenario,
    lane_centerlines: tuple[LaneCenterlineRecord, ...],
    *,
    lane_coordinate_frame: str,
    config: LaneRoadMatchConfig = LaneRoadMatchConfig(),
    actor_ids: tuple[str, ...] | None = None,
) -> LaneRoadMatchReport:
    if lane_coordinate_frame != scenario.coordinate_frame:
        raise ValueError("lane_coordinate_frame must match scenario.coordinate_frame.")
    if not lane_centerlines:
        raise ValueError("At least one lane centerline is required.")
    if len({lane.lane_id for lane in lane_centerlines}) != len(lane_centerlines):
        raise ValueError("Lane centerline IDs must be unique.")
    selected = (scenario.ego_actor_id,) if actor_ids is None else actor_ids
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Selected actor IDs must be non-empty and unique.")
    actors = {actor.actor_id: actor for actor in scenario.actors}
    if any(actor_id not in actors for actor_id in selected):
        raise ValueError("Selected actor IDs must identify scenario actors.")
    lanes = tuple(sorted(lane_centerlines, key=lambda lane: lane.lane_id))
    segments = _segments(lanes)
    if not segments:
        raise ValueError("Lane centerlines must contain a non-zero segment.")
    matches: list[LaneRoadMatchState] = []
    per_actor: list[LaneRoadMatchActor] = []
    for actor_id in (actor.actor_id for actor in scenario.actors if actor.actor_id in selected):
        actor_matches = tuple(_match_state(actor_id, index, state, segments, config) for index, state in enumerate(actors[actor_id].trajectory))
        matches.extend(actor_matches)
        per_actor.append(LaneRoadMatchActor(actor_id, _summary(actor_matches)))
    overall = _summary(matches)
    return LaneRoadMatchReport(ROAD_MATCH_VERSION, scenario.scenario_id, scenario.coordinate_frame, config,
                               tuple(actor.actor_id for actor in scenario.actors if actor.actor_id in selected),
                               tuple(lane.lane_id for lane in lanes), tuple(matches), tuple(per_actor), overall)


def diagnose_nearest_lane_candidates(
    scenario: Scenario,
    lane_centerlines: tuple[LaneCenterlineRecord, ...],
    *,
    lane_coordinate_frame: str,
    config: LaneRoadMatchConfig = LaneRoadMatchConfig(),
    actor_ids: tuple[str, ...] | None = None,
    max_candidates: int = 3,
) -> LaneCandidateReport:
    selected, lanes, segments = _validated_inputs(scenario, lane_centerlines, lane_coordinate_frame, actor_ids)
    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive.")
    states = []
    actors = {actor.actor_id: actor for actor in scenario.actors}
    for actor_id in selected:
        for state_index, state in enumerate(actors[actor_id].trajectory):
            candidates = _candidate_evidence(state, segments, config)
            states.append(LaneCandidateStateDiagnostic(actor_id, state_index, state, len(candidates), tuple(candidates[:max_candidates])))
    return LaneCandidateReport(CANDIDATE_DIAGNOSTIC_VERSION, scenario.scenario_id, scenario.coordinate_frame,
                               selected, tuple(lane.lane_id for lane in lanes), tuple(states))


def diagnose_lane_footprint_occupancy(
    scenario: Scenario,
    lane_centerlines: tuple[LaneCenterlineRecord, ...],
    lane_widths: tuple[LaneWidthRecord, ...],
    *,
    lane_coordinate_frame: str,
    actor_ids: tuple[str, ...] | None = None,
    config: LaneRoadMatchConfig = LaneRoadMatchConfig(),
) -> LaneFootprintOccupancyReport:
    selected, lanes, segments = _validated_inputs(scenario, lane_centerlines, lane_coordinate_frame, actor_ids)
    widths = {width.lane_id: width for width in lane_widths}
    if len(widths) != len(lane_widths):
        raise ValueError("Lane width IDs must be unique.")
    unknown_widths = set(widths) - {lane.lane_id for lane in lanes}
    if unknown_widths:
        raise ValueError("Lane widths must identify known lanes.")
    actors = {actor.actor_id: actor for actor in scenario.actors}
    states = []
    for actor_id in selected:
        actor = actors[actor_id]
        for state_index, state in enumerate(actor.trajectory):
            candidate = _candidate_evidence(state, segments, config)[0]
            width = widths.get(candidate.lane_id)
            if width is None:
                states.append(LaneFootprintOccupancyState(actor_id, state_index, state, candidate.lane_id, candidate.segment_index,
                    candidate.rank, None, None, candidate.signed_lateral_offset_m, None, None, "lane_width_unavailable"))
                continue
            if actor.width_m is None or actor.length_m is None:
                states.append(LaneFootprintOccupancyState(actor_id, state_index, state, candidate.lane_id, candidate.segment_index,
                    candidate.rank, width.width_m, width.source, candidate.signed_lateral_offset_m, None, None, "vehicle_dimensions_unavailable"))
                continue
            heading = _candidate_heading(state, segments, candidate.lane_id, candidate.segment_index, candidate.projection_t)
            delta = abs(_wrap_angle(state.yaw_rad - heading))
            extent = actor.width_m / 2 * abs(cos(delta)) + actor.length_m / 2 * abs(sin(delta))
            occupied = abs(candidate.signed_lateral_offset_m) + extent <= width.width_m / 2
            states.append(LaneFootprintOccupancyState(actor_id, state_index, state, candidate.lane_id, candidate.segment_index,
                candidate.rank, width.width_m, width.source, candidate.signed_lateral_offset_m, extent, occupied,
                "occupied" if occupied else "footprint_exceeds_lane_width"))
    return LaneFootprintOccupancyReport(FOOTPRINT_OCCUPANCY_VERSION, scenario.scenario_id, scenario.coordinate_frame,
                                        selected, tuple(lane.lane_id for lane in lanes), tuple(states), config)


def build_lane_graph(lane_centerlines: tuple[LaneCenterlineRecord, ...]) -> LaneGraph:
    """Normalize lane records into a directed, validated diagnostic graph.

    Topology is copied from the map builder's explicit links. Records without
    links remain isolated; the matcher may report a declared topology gap but
    never invents an intersection edge from geometric proximity.
    """
    if not lane_centerlines:
        raise ValueError("At least one lane centerline is required.")
    if len({lane.lane_id for lane in lane_centerlines}) != len(lane_centerlines):
        raise ValueError("Lane centerline IDs must be unique.")
    records = {lane.lane_id: lane for lane in lane_centerlines}
    lanes: list[LaneGraphLane] = []
    validations: list[LaneGraphValidation] = []
    for lane_id in sorted(records):
        record = records[lane_id]
        poses = record.poses
        if record.travel_direction == "reverse":
            poses = tuple(
                LaneCenterlinePose(pose.x_m, pose.y_m, _wrap_angle(pose.yaw_rad + math.pi))
                for pose in reversed(poses)
            )
        cumulative = [0.0]
        failures: list[str] = []
        for start, end in zip(poses, poses[1:]):
            segment_length = hypot(end.x_m - start.x_m, end.y_m - start.y_m)
            if not isfinite(segment_length) or segment_length <= 0:
                failures.append("non_positive_segment")
            cumulative.append(cumulative[-1] + segment_length)
        if cumulative[-1] <= 0:
            failures.append("non_positive_centerline_length")
        if any((cumulative[index + 1] - cumulative[index]) > 100.0 for index in range(len(cumulative) - 1)):
            failures.append("sample_spacing_exceeds_100m")
        unknown_links = (set(record.predecessor_ids) | set(record.successor_ids) |
                         set(record.legal_lane_change_ids)) - records.keys()
        if unknown_links:
            failures.append("unknown_topology_reference:" + ",".join(sorted(unknown_links)))
        if record.polygon is not None and _polygon_area(record.polygon) <= 0:
            failures.append("polygon_non_positive_area")
        if record.width_m is not None and not 1.0 <= record.width_m <= 10.0:
            failures.append("lane_width_out_of_declared_bounds")
        lane = LaneGraphLane(
            lane_id=lane_id,
            source_id=record.source_id or lane_id,
            poses=poses,
            cumulative_s_m=tuple(cumulative),
            predecessor_ids=tuple(sorted(record.predecessor_ids)),
            successor_ids=tuple(sorted(record.successor_ids)),
            legal_lane_change_ids=tuple(sorted(record.legal_lane_change_ids)),
            junction_id=record.junction_id,
            is_connector=record.is_connector,
            travel_direction=record.travel_direction,
            polygon=record.polygon,
            width_m=record.width_m,
            width_source=record.width_source,
        )
        lanes.append(lane)
        validations.append(LaneGraphValidation(lane_id, not failures, tuple(failures)))
    by_id = {lane.lane_id: lane for lane in lanes}
    checked_validations = []
    for validation in validations:
        lane = by_id[validation.lane_id]
        failures = list(validation.failures)
        for linked_id in lane.predecessor_ids:
            if linked_id not in by_id:
                continue
            linked = by_id[linked_id]
            endpoint_gap = hypot(linked.poses[-1].x_m - lane.poses[0].x_m,
                                 linked.poses[-1].y_m - lane.poses[0].y_m)
            heading_gap = abs(_wrap_angle(linked.poses[-1].yaw_rad - lane.poses[0].yaw_rad))
            if endpoint_gap > 20.0:
                failures.append(f"predecessor_endpoint_gap:{endpoint_gap:.3f}m")
            if heading_gap > math.pi / 2:
                failures.append(f"predecessor_heading_gap:{heading_gap:.3f}rad")
        checked_validations.append(LaneGraphValidation(validation.lane_id, not failures, tuple(failures)))
    return LaneGraph(tuple(lanes), tuple(checked_validations))


def diagnose_lane_sequence_match(
    scenario: Scenario,
    lane_centerlines: tuple[LaneCenterlineRecord, ...],
    *,
    lane_coordinate_frame: str,
    config: LaneSequenceMatchConfig = LaneSequenceMatchConfig(),
    actor_ids: tuple[str, ...] | None = None,
    lane_graph: LaneGraph | None = None,
) -> LaneSequenceMatchReport:
    """Decode each selected actor as a topology-constrained lane sequence.

    This is an additive diagnostic. It does not call or alter the legacy
    nearest-lane matcher and never changes production lane direction policy.
    """
    selected, lanes, _ = _validated_inputs(
        scenario, lane_centerlines, lane_coordinate_frame, actor_ids
    )
    graph = build_lane_graph(lanes) if lane_graph is None else lane_graph
    if tuple(lane.lane_id for lane in graph.lanes) != tuple(lane.lane_id for lane in lanes):
        raise ValueError("lane_graph must contain the same lane IDs as lane_centerlines.")
    actors = {actor.actor_id: actor for actor in scenario.actors}
    all_states: list[LaneSequenceStateMatch] = []
    summaries: list[LaneSequenceTrackSummary] = []
    for actor_id in selected:
        actor_states, summary = _decode_actor_sequence(actor_id, actors[actor_id], graph, config)
        all_states.extend(actor_states)
        summaries.append(summary)
    geometry_failures = tuple(
        f"{item.lane_id}:{failure}"
        for item in graph.validation
        for failure in item.failures
    )
    return LaneSequenceMatchReport(
        LANE_SEQUENCE_MATCH_VERSION,
        scenario.scenario_id,
        scenario.coordinate_frame,
        config,
        graph,
        selected,
        tuple(all_states),
        tuple(summaries),
        geometry_failures,
    )


def diagnose_lane_sequence_triage(
    scenario: Scenario,
    lane_centerlines: tuple[LaneCenterlineRecord, ...],
    *,
    lane_coordinate_frame: str,
    config: LaneSequenceMatchConfig = LaneSequenceMatchConfig(),
    actor_ids: tuple[str, ...] | None = None,
    alignment_hypotheses: tuple[tuple[str, float, float, float], ...] = (("identity", 0.0, 0.0, 0.0),),
) -> LaneSequenceTriageReport:
    """Additive automated triage around the sequence report.

    Hypotheses are scored without mutating the scenario or selecting a new
    production transform. The default identity hypothesis keeps private runs
    auditable when no map-anchor-supported alternatives were declared.
    """
    sequence_report = diagnose_lane_sequence_match(
        scenario, lane_centerlines, lane_coordinate_frame=lane_coordinate_frame,
        config=config, actor_ids=actor_ids,
    )
    selected = sequence_report.selected_actor_ids
    hypotheses = []
    for name, dx, dy, yaw in alignment_hypotheses:
        transformed = _translated_scenario(scenario, dx, dy, yaw)
        candidate = diagnose_lane_sequence_match(
            transformed, lane_centerlines, lane_coordinate_frame=lane_coordinate_frame,
            config=config, actor_ids=selected,
        )
        residuals = [
            state.signed_lateral_offset_m
            for state in candidate.states
            if state.signed_lateral_offset_m is not None
        ]
        hypotheses.append(LaneAlignmentHypothesis(
            name, dx, dy, yaw,
            sum(abs(value) for value in residuals) / len(residuals) if residuals else None,
            sum(state.best_lane_id is not None for state in candidate.states),
            len(selected),
        ))
    nearest = diagnose_nearest_lane_candidates(
        scenario, lane_centerlines, lane_coordinate_frame=lane_coordinate_frame,
        actor_ids=selected, max_candidates=1,
    )
    nearest_by_key = {(state.actor_id, state.state_index): state.candidates[0].lane_id
                      for state in nearest.states if state.candidates}
    changes = []
    rank_gt_one = []
    directions: dict[str, int] = {}
    for state in sequence_report.states:
        nearest_lane = nearest_by_key.get((state.actor_id, state.state_index))
        if nearest_lane != state.best_lane_id:
            changes.append((state.actor_id, state.state_index, nearest_lane, state.best_lane_id))
        if state.best_candidate_rank is not None and state.best_candidate_rank > 1:
            rank_gt_one.append((state.actor_id, state.state_index, state.best_candidate_rank))
        directions[state.direction_classification] = directions.get(state.direction_classification, 0) + 1
    intervals = tuple(interval for summary in sequence_report.per_actor for interval in summary.ambiguous_intervals)
    return LaneSequenceTriageReport(
        LANE_SEQUENCE_MATCH_VERSION, sequence_report, tuple(hypotheses), tuple(changes),
        tuple(rank_gt_one), tuple(sorted(directions.items())), intervals,
    )


def compare_lane_references(
    scenario: Scenario,
    references: tuple[tuple[str, LaneGraph], ...],
    *,
    actor_ids: tuple[str, ...] | None = None,
    candidate_radius_m: float = 8.0,
    high_lateral_error_m: float = 2.0,
) -> LaneReferenceComparisonReport:
    """Compare native, canonical and export lane references consistently.

    References are explicit graph inputs. This keeps source-map truth separate
    from generated OpenDRIVE and makes the comparison dependency-free.
    """
    if not references or len({name for name, _ in references}) != len(references):
        raise ValueError("references must contain unique named lane graphs")
    if not isfinite(candidate_radius_m) or candidate_radius_m <= 0:
        raise ValueError("candidate_radius_m must be finite and positive")
    if not isfinite(high_lateral_error_m) or high_lateral_error_m < 0:
        raise ValueError("high_lateral_error_m must be finite and non-negative")
    selected = (scenario.ego_actor_id,) if actor_ids is None else actor_ids
    actors = {actor.actor_id: actor for actor in scenario.actors}
    if any(actor_id not in actors for actor_id in selected):
        raise ValueError("actor_ids must identify scenario actors")
    diagnostics: list[LaneReferenceStateDiagnostic] = []
    summaries = []
    for reference_name, graph in references:
        reference_states = []
        for actor_id in selected:
            actor = actors[actor_id]
            for index, state in enumerate(actor.trajectory):
                candidates = _sequence_candidates(
                    state, actor.trajectory, index, graph,
                    LaneSequenceMatchConfig(candidate_radius_m=candidate_radius_m),
                )
                candidate = candidates[0] if candidates else None
                if candidate is None or candidate.lane_id is None:
                    diagnostic = LaneReferenceStateDiagnostic(reference_name, actor_id, index, None, None, None, None, None, None, None, None, None, "unmatched_geometry")
                else:
                    lane = graph.by_id[candidate.lane_id]
                    lane_heading = _candidate_lane_heading(lane, candidate.segment_index, candidate.projected_s_m)
                    motion_heading = _motion_heading(actor.trajectory, index)
                    topology_valid = not any(
                        reason.startswith("unknown_topology_reference")
                        for validation in graph.validation if validation.lane_id == candidate.lane_id
                        for reason in validation.failures
                    )
                    if candidate.inside_polygon is False:
                        status = "lane_polygon_outside"
                    elif candidate.motion_heading_error_rad is not None and candidate.motion_heading_error_rad > math.pi / 2:
                        status = "heading_conflict"
                    elif not topology_valid:
                        status = "topology_invalid"
                    else:
                        status = "lane_semantically_valid"
                    diagnostic = LaneReferenceStateDiagnostic(
                        reference_name, actor_id, index, candidate.lane_id, lane.source_id,
                        candidate.lateral_distance_m, candidate.signed_lateral_offset_m, candidate.inside_polygon,
                        candidate.distance_to_polygon_boundary_m, candidate.annotation_heading_error_rad,
                        candidate.motion_heading_error_rad, topology_valid, status, lane_heading, motion_heading,
                    )
                diagnostics.append(diagnostic)
                reference_states.append(diagnostic)
        lateral = [abs(item.signed_lateral_offset_m) for item in reference_states if item.signed_lateral_offset_m is not None]
        heading = [item.annotation_heading_error_rad for item in reference_states if item.annotation_heading_error_rad is not None]
        summaries.append(LaneReferenceSummary(
            reference_name, len(reference_states),
            sum(item.status == "lane_semantically_valid" for item in reference_states),
            sum(item.lateral_distance_m is not None and item.lateral_distance_m > high_lateral_error_m for item in reference_states),
            sum(item.status == "lane_polygon_outside" for item in reference_states),
            sum(actors[item.actor_id].width_m is None or actors[item.actor_id].length_m is None for item in reference_states),
            sum(item.status == "heading_conflict" for item in reference_states),
            sum(item.status == "topology_invalid" for item in reference_states),
            sum(item.status == "unmatched_geometry" for item in reference_states),
            sum(lateral) / len(lateral) if lateral else None, _p95(lateral), max(heading) if heading else None,
        ))
    return LaneReferenceComparisonReport(
        "lane-reference-comparison-v1", scenario.scenario_id, scenario.coordinate_frame,
        tuple(name for name, _ in references), tuple(diagnostics), tuple(summaries),
    )


def analyze_actor_reference_sensitivity(
    scenario: Scenario,
    references: tuple[tuple[str, LaneGraph], ...],
    *,
    actor_ids: tuple[str, ...] | None = None,
    fixed_heading_offset_m: float = 1.0,
    candidate_radius_m: float = 8.0,
    high_lateral_error_m: float = 2.0,
) -> ActorReferenceSensitivityReport:
    """Compare globally declared actor reference conventions counterfactually.

    This intentionally shifts every actor with known dimensions using the same
    convention. It is a diagnostic and never changes the canonical scenario.
    Actors without dimensions remain at the annotation center and are marked
    unsupported in the resulting rows.
    """
    if not isfinite(fixed_heading_offset_m) or fixed_heading_offset_m < 0:
        raise ValueError("fixed_heading_offset_m must be finite and non-negative")
    hypotheses = (
        ActorReferenceHypothesis("annotation_center", 0.0),
        ActorReferenceHypothesis("rear_axle", -0.5),
        ActorReferenceHypothesis("front_axle", 0.5),
        ActorReferenceHypothesis("fixed_heading_offset", fixed_heading_offset_m),
    )
    selected = (scenario.ego_actor_id,) if actor_ids is None else actor_ids
    actors = {actor.actor_id: actor for actor in scenario.actors}
    if not selected or len(set(selected)) != len(selected) or any(actor_id not in actors for actor_id in selected):
        raise ValueError("actor_ids must identify unique scenario actors")
    rows: list[ActorReferenceSensitivityRow] = []
    for hypothesis in hypotheses:
        shifted = _shifted_reference_scenario(scenario, hypothesis)
        comparison = compare_lane_references(
            shifted, references, actor_ids=selected,
            candidate_radius_m=candidate_radius_m,
            high_lateral_error_m=high_lateral_error_m,
        )
        for reference_name in comparison.reference_names:
            states = [
                item for item in comparison.state_diagnostics
                if item.reference_name == reference_name and item.actor_id in selected
            ]
            for actor_id in selected:
                actor_states = [item for item in states if item.actor_id == actor_id]
                residuals = [abs(item.signed_lateral_offset_m) for item in actor_states if item.signed_lateral_offset_m is not None]
                actor = actors[actor_id]
                supported = len(actor_states) if hypothesis.name in {"annotation_center", "fixed_heading_offset"} or actor.length_m is not None else 0
                rows.append(ActorReferenceSensitivityRow(
                    hypothesis.name, reference_name, actor_id, len(actor_states), supported,
                    len(actor_states) - supported,
                    sum(residuals) / len(residuals) if residuals else None,
                    _p95(residuals), sum(item.inside_polygon is True for item in actor_states),
                    sum(item.status == "heading_conflict" for item in actor_states),
                ))
    return ActorReferenceSensitivityReport(
        ACTOR_REFERENCE_SENSITIVITY_VERSION, scenario.scenario_id, scenario.coordinate_frame,
        hypotheses, tuple(rows),
    )


def classify_direction_counterfactuals(
    scenario: Scenario,
    references: tuple[tuple[str, LaneGraph], ...],
    *,
    actor_ids: tuple[str, ...] | None = None,
    candidate_radius_m: float = 8.0,
) -> DirectionCounterfactualReport:
    """Report heading evidence without reversing any production lane direction."""
    if not references:
        raise ValueError("references must not be empty")
    selected = (scenario.ego_actor_id,) if actor_ids is None else actor_ids
    actors = {actor.actor_id: actor for actor in scenario.actors}
    if not selected or len(set(selected)) != len(selected) or any(actor_id not in actors for actor_id in selected):
        raise ValueError("actor_ids must identify unique scenario actors")
    rows: list[DirectionCounterfactualState] = []
    config = LaneSequenceMatchConfig(candidate_radius_m=candidate_radius_m)
    for reference_name, graph in references:
        for actor_id in selected:
            actor = actors[actor_id]
            for index, state in enumerate(actor.trajectory):
                candidates = _sequence_candidates(state, actor.trajectory, index, graph, config)
                candidate = candidates[0] if candidates else None
                motion = _motion_heading(actor.trajectory, index)
                if candidate is None or candidate.lane_id is None:
                    rows.append(DirectionCounterfactualState(reference_name, actor_id, index, state.yaw_rad, motion, None, None, None, "uncertain"))
                    continue
                lane = graph.by_id[candidate.lane_id]
                lane_heading = _candidate_lane_heading(lane, candidate.segment_index, candidate.projected_s_m)
                annotation_error = abs(_wrap_angle(state.yaw_rad - lane_heading))
                motion_error = None if motion is None else abs(_wrap_angle(motion - lane_heading))
                classification = _classify_direction(annotation_error, motion_error)
                rows.append(DirectionCounterfactualState(
                    reference_name, actor_id, index, state.yaw_rad, motion, lane_heading,
                    annotation_error, motion_error, classification,
                ))
    return DirectionCounterfactualReport(
        DIRECTION_COUNTERFACTUAL_VERSION, scenario.scenario_id, scenario.coordinate_frame,
        tuple(rows),
    )


def lane_graph_from_opendrive(xml_text: str) -> LaneGraph:
    """Create a lightweight diagnostic graph from emitted line-only XODR."""
    return build_lane_graph(lane_centerlines_from_opendrive(xml_text))


def lane_centerlines_from_opendrive(xml_text: str) -> tuple[LaneCenterlineRecord, ...]:
    """Return corridor centerline records in emitted order, without normalization.

    The records preserve the generated direction of each road so a corridor
    road-match can be compared with the immutable CP1 corridor baseline. Lane
    direction normalization stays a graph-level concern.
    """
    root = ET.fromstring(xml_text)
    records = []
    for road in root.findall("road"):
        poses = []
        lane_width = None
        width_element = road.find("./lanes/laneSection/right/lane[@id='-1']/width")
        if width_element is not None:
            lane_width = float(width_element.attrib.get("a", "0"))
        for geometry in road.findall("./planView/geometry"):
            x, y, hdg, length = (float(geometry.attrib[key]) for key in ("x", "y", "hdg", "length"))
            offset = (lane_width or 0.0) / 2.0
            poses.append(LaneCenterlinePose(x + offset * sin(hdg), y - offset * cos(hdg), hdg))
            if geometry.find("line") is not None:
                poses.append(LaneCenterlinePose(x + length * cos(hdg) + offset * sin(hdg), y + length * sin(hdg) - offset * cos(hdg), hdg))
        if len(poses) < 2:
            continue
        link = road.find("link")
        predecessor = () if link is None or link.find("predecessor") is None else (link.find("predecessor").attrib["elementId"],)
        successor = () if link is None or link.find("successor") is None else (link.find("successor").attrib["elementId"],)
        records.append(LaneCenterlineRecord(road.attrib["id"], tuple(poses), source_id=road.attrib["name"], predecessor_ids=predecessor, successor_ids=successor))
    return tuple(records)


def lane_graph_from_nuscenes(
    dataset_root: str,
    *,
    map_name: str = "singapore-onenorth",
    selected_tokens: tuple[str, ...] | None = None,
    resolution_m: float = 5.0,
):
    """Build an explicit native nuScenes lane graph for private diagnostics."""
    centerlines, repair_report, topology_report = _nuscenes_centerlines(
        dataset_root,
        map_name=map_name,
        selected_tokens=selected_tokens,
        resolution_m=resolution_m,
    )
    return build_lane_graph(centerlines), repair_report, topology_report


def lane_centerlines_from_nuscenes(
    dataset_root: str,
    *,
    map_name: str = "singapore-onenorth",
    selected_tokens: tuple[str, ...] | None = None,
    resolution_m: float = 5.0,
) -> tuple[LaneCenterlineRecord, ...]:
    """Return native nuScenes centerline records without direction normalization.

    Lane direction normalization stays a graph-level concern so a source map can
    be compared in emitted order against generated OpenDRIVE.
    """
    centerlines, _repair_report, _topology_report = _nuscenes_centerlines(
        dataset_root,
        map_name=map_name,
        selected_tokens=selected_tokens,
        resolution_m=resolution_m,
    )
    return centerlines


def _nuscenes_centerlines(
    dataset_root: str,
    *,
    map_name: str,
    selected_tokens: tuple[str, ...] | None,
    resolution_m: float,
) -> tuple[tuple[LaneCenterlineRecord, ...], object, object]:
    from .mapbuilder import _load_nuscenes_map, repair_centerline_paths, validate_lane_topology

    map_api = _load_nuscenes_map(dataset_root, map_name)
    records = {record["token"]: record for record in list(map_api.lane) + list(map_api.lane_connector)}
    tokens = set(records) if selected_tokens is None else set(selected_tokens)
    paths, repair_report = repair_centerline_paths(map_api.discretize_lanes(sorted(tokens), resolution_m))
    connectivity = getattr(map_api, "connectivity", {})
    topology_report = validate_lane_topology(connectivity, paths, tokens)
    connector_tokens = {record["token"] for record in map_api.lane_connector}
    centerlines = []
    for token in sorted(paths):
        relation = connectivity.get(token) or {}
        polygon = None
        polygon_token = records[token].get("polygon_token")
        if polygon_token:
            try:
                shape = map_api.extract_polygon(polygon_token)
                if hasattr(shape, "exterior"):
                    polygon = tuple((float(x), float(y)) for x, y in shape.exterior.coords[:-1])
            except (AttributeError, TypeError, ValueError):
                polygon = None
        centerlines.append(
            LaneCenterlineRecord(
                token,
                tuple(LaneCenterlinePose(float(x), float(y), float(h)) for x, y, h in paths[token]),
                source_id=token,
                predecessor_ids=tuple(item for item in relation.get("incoming", []) if item in tokens),
                successor_ids=tuple(item for item in relation.get("outgoing", []) if item in tokens),
                junction_id="connector" if token in connector_tokens else None,
                is_connector=token in connector_tokens,
                polygon=polygon,
                width_source="polygon" if polygon is not None else "fallback",
                width_m=None if polygon is not None else 3.5,
            )
        )
    return tuple(centerlines), repair_report, topology_report


def _decode_actor_sequence(actor_id, actor, graph, config):
    candidates_by_state = [
        _sequence_candidates(state, actor.trajectory, index, graph, config)
        for index, state in enumerate(actor.trajectory)
    ]
    scores: list[list[float]] = []
    backpointers: list[list[int | None]] = []
    transition_flags: list[list[str]] = []
    for state_index, candidates in enumerate(candidates_by_state):
        if not candidates:
            candidates = (_unmatched_candidate(),)
            candidates_by_state[state_index] = candidates
        current = [candidate.emission_cost for candidate in candidates]
        previous: list[int | None] = [None] * len(candidates)
        flags = ["" for _ in candidates]
        if state_index:
            prior_candidates = candidates_by_state[state_index - 1]
            prior_scores = scores[-1]
            for current_index, current_candidate in enumerate(candidates):
                options = []
                for prior_index, prior_candidate in enumerate(prior_candidates):
                    transition_cost, flag = _transition_cost(
                        actor.trajectory[state_index - 1], actor.trajectory[state_index],
                        prior_candidate, current_candidate, graph, config,
                    )
                    options.append((prior_scores[prior_index] + transition_cost, prior_index, flag))
                best = min(options, key=lambda option: (option[0], option[1]))
                current[current_index] += best[0]
                previous[current_index] = best[1]
                flags[current_index] = best[2]
        scores.append(current)
        backpointers.append(previous)
        transition_flags.append(flags)
    last_index = min(range(len(scores[-1])), key=lambda index: (scores[-1][index], index))
    path = [last_index]
    for state_index in range(len(scores) - 1, 0, -1):
        path.append(backpointers[state_index][path[-1]])
    path.reverse()
    state_matches: list[LaneSequenceStateMatch] = []
    review_reasons: list[set[str]] = []
    topology_violations = 0
    for index, candidate_index in enumerate(path):
        candidate = candidates_by_state[index][candidate_index]
        ordered_scores = sorted(scores[index])
        best_score = scores[index][candidate_index]
        second_score = ordered_scores[1] if len(ordered_scores) > 1 else None
        margin = None if second_score is None else max(0.0, second_score - best_score)
        confidence = 0.0 if margin is None else 1.0 - math.exp(-margin / max(config.confidence_margin, 1e-12))
        direction_classification = _direction_classification(candidate, actor.trajectory, index, graph)
        reasons: set[str] = set()
        if candidate.lane_id is None:
            status = "unmatched_geometry"
            reasons.add("unmatched_geometry")
        else:
            alternative_inside = any(
                alternative.lane_id != candidate.lane_id and alternative.inside_polygon is True
                for alternative in candidates_by_state[index]
            )
            if index and transition_flags[index][candidate_index] == "topology_gap":
                status = "unmatched_topology"
                topology_violations += 1
                reasons.add("unresolved_topology_transition")
            elif candidate.inside_polygon is False and alternative_inside:
                status = "unmatched_topology"
                topology_violations += 1
                reasons.add("unresolved_topology_transition")
            elif direction_classification == "motion_reverse_of_lane":
                status = "direction_conflict"
                reasons.add("conflicting_annotation_and_motion_heading")
            elif candidate.inside_polygon is False:
                status = "outside_polygon"
                reasons.add("outside_polygon")
            elif margin is not None and margin < config.confidence_margin:
                status = "ambiguous_lane"
                reasons.add("low_score_margin")
            elif candidate.lateral_distance_m > config.persistent_lateral_error_m:
                status = "matched_low_confidence"
                reasons.add("persistent_high_lateral_residual")
            else:
                status = "matched_high_confidence"
        if candidate.lane_id is not None and candidate.inside_polygon is None:
            reasons.add("unsupported_width")
        if actor.width_m is None or actor.length_m is None:
            reasons.add("unsupported_width")
        if direction_classification == "annotation_yaw_mismatch":
            reasons.add("conflicting_annotation_and_motion_heading")
        if not reasons and status != "matched_high_confidence":
            reasons.add(status)
        review_reasons.append(reasons)
        state_matches.append(LaneSequenceStateMatch(
            actor_id, index, actor.trajectory[index].source_timestamp_us,
            actor.trajectory[index].source_record_token,
            candidate.lane_id, candidate.rank if candidate.lane_id is not None else None,
            candidate.projected_s_m if candidate.lane_id is not None else None,
            candidate.signed_lateral_offset_m if candidate.lane_id is not None else None,
            candidate.annotation_heading_error_rad if candidate.lane_id is not None else None,
            candidate.motion_heading_error_rad if candidate.lane_id is not None else None,
            candidate.inside_polygon, best_score, second_score, margin, confidence, status,
            direction_classification, tuple(candidates_by_state[index][:3]),
        ))
    intervals = _review_intervals(actor_id, review_reasons)
    lateral = [abs(match.signed_lateral_offset_m) for match in state_matches if match.signed_lateral_offset_m is not None]
    headings = [match.annotation_heading_error_rad for match in state_matches if match.annotation_heading_error_rad is not None]
    lane_ids = [match.best_lane_id for match in state_matches if match.best_lane_id is not None]
    lane_switches = sum(left != right for left, right in zip(lane_ids, lane_ids[1:]))
    matched = sum(match.best_lane_id is not None for match in state_matches)
    high = sum(match.status == "matched_high_confidence" for match in state_matches)
    low = sum(match.status == "matched_low_confidence" for match in state_matches)
    ambiguous = sum(match.status == "ambiguous_lane" for match in state_matches)
    unsupported = sum("unsupported_width" in reasons for reasons in review_reasons)
    summary = LaneSequenceTrackSummary(
        actor_id, matched, high, low, ambiguous, len(state_matches) - matched,
        sum(lateral) / len(lateral) if lateral else None,
        _p95(lateral), max(headings) if headings else None, topology_violations,
        lane_switches, unsupported, intervals, scores[-1][last_index],
    )
    return tuple(state_matches), summary


def _translated_scenario(scenario, dx, dy, yaw):
    rotated = cos(yaw), sin(yaw)
    actors = []
    for actor in scenario.actors:
        states = tuple(
            State(
                state.time_s,
                state.x_m * rotated[0] - state.y_m * rotated[1] + dx,
                state.x_m * rotated[1] + state.y_m * rotated[0] + dy,
                _wrap_angle(state.yaw_rad + yaw),
                state.speed_mps,
                state.source_timestamp_us,
                state.source_record_token,
            )
            for state in actor.trajectory
        )
        actors.append(Actor(actor.actor_id, actor.actor_type, states, actor.length_m, actor.width_m))
    return Scenario(scenario.scenario_id, scenario.duration_s, scenario.ego_actor_id, tuple(actors), scenario.coordinate_frame, scenario.provenance)


def _shifted_reference_scenario(scenario, hypothesis):
    actors = []
    for actor in scenario.actors:
        if hypothesis.name == "annotation_center" or actor.length_m is None:
            offset = 0.0
        elif hypothesis.name == "rear_axle":
            offset = -actor.length_m / 2.0
        elif hypothesis.name == "front_axle":
            offset = actor.length_m / 2.0
        else:
            offset = hypothesis.offset_m
        states = tuple(
            State(
                state.time_s,
                state.x_m + offset * cos(state.yaw_rad),
                state.y_m + offset * sin(state.yaw_rad),
                state.yaw_rad,
                state.speed_mps,
                state.source_timestamp_us,
                state.source_record_token,
            )
            for state in actor.trajectory
        )
        actors.append(Actor(actor.actor_id, actor.actor_type, states, actor.length_m, actor.width_m))
    return Scenario(
        scenario.scenario_id, scenario.duration_s, scenario.ego_actor_id,
        tuple(actors), scenario.coordinate_frame, scenario.provenance,
    )


def _candidate_lane_heading(lane, segment_index, projected_s):
    if segment_index < 0 or segment_index >= len(lane.poses) - 1:
        return None
    start = lane.poses[segment_index]
    end = lane.poses[segment_index + 1]
    segment_length = lane.cumulative_s_m[segment_index + 1] - lane.cumulative_s_m[segment_index]
    if segment_length <= 0:
        return None
    fraction = max(0.0, min(1.0, (projected_s - lane.cumulative_s_m[segment_index]) / segment_length))
    return _wrap_angle(start.yaw_rad + fraction * _wrap_angle(end.yaw_rad - start.yaw_rad))


def _classify_direction(annotation_error, motion_error):
    if motion_error is None:
        return "uncertain" if annotation_error > math.pi / 2 else "annotation_only"
    annotation_reverse = annotation_error > math.pi / 2
    motion_reverse = motion_error > math.pi / 2
    if motion_reverse and annotation_reverse:
        return "true_reverse_motion"
    if motion_reverse and not annotation_reverse:
        return "source_annotation_yaw_error"
    if not motion_reverse and annotation_reverse:
        return "source_annotation_yaw_error"
    return "aligned"


def _sequence_candidates(state, trajectory, state_index, graph, config):
    motion_heading = _motion_heading(trajectory, state_index)
    candidates = []
    for lane in graph.lanes:
        best = None
        for segment_index, (start, end) in enumerate(zip(lane.poses, lane.poses[1:])):
            dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
            length_sq = dx * dx + dy * dy
            if length_sq <= 1e-18:
                continue
            projection_t = max(0.0, min(1.0, ((state.x_m - start.x_m) * dx + (state.y_m - start.y_m) * dy) / length_sq))
            px, py = start.x_m + projection_t * dx, start.y_m + projection_t * dy
            distance = hypot(state.x_m - px, state.y_m - py)
            segment_length = math.sqrt(length_sq)
            lane_heading = _wrap_angle(start.yaw_rad + projection_t * _wrap_angle(end.yaw_rad - start.yaw_rad))
            offset = (state.x_m - px) * (-dy / segment_length) + (state.y_m - py) * (dx / segment_length)
            annotation_error = abs(_wrap_angle(state.yaw_rad - lane_heading))
            motion_error = None if motion_heading is None else abs(_wrap_angle(motion_heading - lane_heading))
            inside = None if lane.polygon is None else _point_in_polygon(state.x_m, state.y_m, lane.polygon)
            boundary = None if lane.polygon is None else _polygon_boundary_distance(state.x_m, state.y_m, lane.polygon)
            projected_s = lane.cumulative_s_m[segment_index] + projection_t * segment_length
            item = (distance, lane_id_sort_key(lane.lane_id), segment_index, projection_t, offset,
                    annotation_error, motion_error, inside, boundary, lane_heading, projected_s)
            if best is None or item[:4] < best[:4]:
                best = item
        if best is None:
            continue
        distance, _, segment_index, projection_t, offset, annotation_error, motion_error, inside, boundary, _, projected_s = best
        if distance > config.candidate_radius_m:
            continue
        emission = config.position_weight * (distance / config.position_sigma_m) ** 2
        emission += config.annotation_heading_weight * (annotation_error / config.heading_sigma_rad) ** 2
        if motion_error is not None:
            emission += config.motion_heading_weight * (motion_error / config.heading_sigma_rad) ** 2
        if inside is False:
            emission += config.outside_polygon_penalty
        if boundary is not None and lane.width_m is not None:
            emission += config.boundary_penalty / max(boundary, 0.25)
        reverse = motion_error is not None and motion_error > math.pi / 2
        if reverse:
            emission += config.reverse_direction_penalty
        reason = "outside_polygon" if inside is False else "reverse_direction" if reverse else "candidate"
        candidates.append((emission, lane.lane_id, segment_index, projection_t, projected_s, distance, offset,
                           annotation_error, motion_error, inside, boundary, lane.travel_direction, reverse, reason))
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return tuple(
        LaneSequenceCandidate(
            item[1], item[2], item[4], item[5], item[6], item[7], item[8], item[9], item[10],
            item[11], item[12], rank + 1, item[13], item[0],
        )
        for rank, item in enumerate(candidates[:config.max_candidates])
    )


def _transition_cost(previous_state, current_state, previous, current, graph, config):
    if previous.lane_id is None or current.lane_id is None:
        return config.topology_gap_penalty, "topology_gap"
    previous_lane = graph.by_id[previous.lane_id]
    current_lane = graph.by_id[current.lane_id]
    same = previous.lane_id == current.lane_id
    successor = current.lane_id in previous_lane.successor_set
    lane_change = current.lane_id in previous_lane.legal_lane_change_ids
    if not (same or successor or lane_change):
        if not config.allow_topology_gaps:
            return float("inf"), "topology_violation"
        return config.topology_gap_penalty + _progress_cost(previous_state, current_state, previous, current, config), "topology_gap"
    expected_progress = max(0.0, current_state.speed_mps) * max(0.0, current_state.time_s - previous_state.time_s)
    if same or lane_change:
        route_progress = current.projected_s_m - previous.projected_s_m
    else:
        route_progress = (previous_lane.length_m - previous.projected_s_m) + current.projected_s_m
    cost = abs(route_progress - expected_progress) / max(config.position_sigma_m, 1e-12)
    cost += _progress_cost(previous_state, current_state, previous, current, config)
    if lane_change:
        cost += config.lane_change_penalty
    if current.reverse_direction:
        cost += config.reverse_direction_penalty
    if previous_lane.junction_id != current_lane.junction_id and (previous_lane.is_connector or current_lane.is_connector):
        cost += config.lane_change_penalty / 2
    return cost, "lane_change" if lane_change else "declared"


def _progress_cost(previous_state, current_state, previous, current, config):
    dt = max(0.0, current_state.time_s - previous_state.time_s)
    observed_distance = hypot(current_state.x_m - previous_state.x_m, current_state.y_m - previous_state.y_m)
    expected_distance = max(0.0, previous_state.speed_mps) * dt
    return abs(observed_distance - expected_distance) / max(config.speed_sigma_mps, 1e-12)


def _unmatched_candidate():
    return LaneSequenceCandidate(None, -1, 0.0, float("inf"), 0.0, math.pi, None, None, None,
                                 "forward", False, 1, "no_candidate_within_radius", 1e6)


def _motion_heading(trajectory, index):
    if len(trajectory) < 2:
        return None
    if index < len(trajectory) - 1:
        current, other = trajectory[index], trajectory[index + 1]
    else:
        current, other = trajectory[index - 1], trajectory[index]
    dx, dy = other.x_m - current.x_m, other.y_m - current.y_m
    return atan2(dy, dx) if hypot(dx, dy) > 1e-9 else None


def _direction_classification(candidate, trajectory, index, graph):
    motion = candidate.motion_heading_error_rad
    annotation = candidate.annotation_heading_error_rad
    if motion is None:
        return "heading_uncertain"
    if motion > math.pi / 2:
        return "motion_reverse_of_lane"
    if annotation > math.pi / 2 and motion <= math.pi / 2:
        return "annotation_yaw_mismatch"
    if motion > math.pi / 2:
        return "lane_direction_candidate"
    return "consistent_heading"


def _review_intervals(actor_id, reasons_by_state):
    intervals = []
    start = None
    active: set[str] = set()
    for index, reasons in enumerate(reasons_by_state + [set()]):
        if reasons and start is None:
            start, active = index, set(reasons)
        elif reasons and start is not None:
            active.update(reasons)
        elif start is not None:
            intervals.append(LaneSequenceReviewInterval(actor_id, start, index - 1, tuple(sorted(active))))
            start, active = None, set()
    return tuple(intervals)


def _p95(values):
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[94]


def lane_id_sort_key(lane_id):
    return lane_id


def _polygon_area(polygon):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def _point_in_polygon(x, y, polygon):
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside or _polygon_boundary_distance(x, y, polygon) <= 1e-9


def _polygon_boundary_distance(x, y, polygon):
    return min(_point_segment_distance(x, y, x1, y1, x2, y2)
               for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]))


def _point_segment_distance(x, y, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-18:
        return hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_sq))
    return hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def _match_state(actor_id, state_index, state, segments, config):
    candidate = _candidate_evidence(state, segments, config)[0]
    return LaneRoadMatchState(actor_id, state_index, state, candidate.lane_id, candidate.segment_index, candidate.projection_t, candidate.distance_m, candidate.heading_error_rad, candidate.passes_centerline_tolerances, candidate.reason)


def _validated_inputs(scenario, lane_centerlines, lane_coordinate_frame, actor_ids):
    if lane_coordinate_frame != scenario.coordinate_frame:
        raise ValueError("lane_coordinate_frame must match scenario.coordinate_frame.")
    if not lane_centerlines:
        raise ValueError("At least one lane centerline is required.")
    if len({lane.lane_id for lane in lane_centerlines}) != len(lane_centerlines):
        raise ValueError("Lane centerline IDs must be unique.")
    selected = (scenario.ego_actor_id,) if actor_ids is None else actor_ids
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Selected actor IDs must be non-empty and unique.")
    known = {actor.actor_id for actor in scenario.actors}
    if any(actor_id not in known for actor_id in selected):
        raise ValueError("Selected actor IDs must identify scenario actors.")
    lanes = tuple(sorted(lane_centerlines, key=lambda lane: lane.lane_id))
    segments = _segments(lanes)
    if not segments:
        raise ValueError("Lane centerlines must contain a non-zero segment.")
    return tuple(actor.actor_id for actor in scenario.actors if actor.actor_id in selected), lanes, segments


def _segments(lanes):
    return tuple((lane.lane_id, index, start, end) for lane in lanes for index, (start, end) in enumerate(zip(lane.poses, lane.poses[1:])) if (end.x_m - start.x_m) ** 2 + (end.y_m - start.y_m) ** 2 > 1e-18)


def _candidate_evidence(state, segments, config):
    candidates = []
    for lane_id, segment_index, start, end in segments:
        dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
        length_sq = dx * dx + dy * dy
        projection_t = max(0.0, min(1.0, ((state.x_m - start.x_m) * dx + (state.y_m - start.y_m) * dy) / length_sq))
        projected_x, projected_y = start.x_m + projection_t * dx, start.y_m + projection_t * dy
        distance = hypot(state.x_m - projected_x, state.y_m - projected_y)
        heading = _wrap_angle(start.yaw_rad + projection_t * _wrap_angle(end.yaw_rad - start.yaw_rad))
        heading_error = abs(_wrap_angle(state.yaw_rad - heading))
        left_x, left_y = -dy / math.sqrt(length_sq), dx / math.sqrt(length_sq)
        signed_offset = (state.x_m - projected_x) * left_x + (state.y_m - projected_y) * left_y
        distance_ok, heading_ok = distance <= config.max_distance_m, heading_error <= config.max_heading_error_rad
        reason = "matched" if distance_ok and heading_ok else "distance_and_heading_exceed_tolerance" if not distance_ok and not heading_ok else "distance_exceeds_tolerance" if not distance_ok else "heading_exceeds_tolerance"
        candidates.append((distance, lane_id, segment_index, projection_t, signed_offset, heading_error, distance_ok, heading_ok, reason))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple(LaneCandidateEvidence(index + 1, item[1], item[2], item[3], item[0], item[4], item[5], item[6], item[7], item[6] and item[7], item[8]) for index, item in enumerate(candidates))


def _candidate_heading(state, segments, lane_id, segment_index, projection_t):
    for current_lane, current_index, start, end in segments:
        if current_lane == lane_id and current_index == segment_index:
            return _wrap_angle(start.yaw_rad + projection_t * _wrap_angle(end.yaw_rad - start.yaw_rad))
    raise ValueError("Candidate segment was not found.")


def _summary(matches):
    count = len(matches)
    matched = sum(match.matched for match in matches)
    rate = matched / count
    return LaneRoadMatchSummary(count, matched, rate, "at_or_above_95_percent" if rate >= 0.95 else "below_95_percent")


def _wrap_angle(angle: float) -> float:
    return atan2(sin(angle), cos(angle))


LANE_ROAD_MATCH_EVIDENCE_VERSION = "lane-road-match-evidence-v1"


@dataclass(frozen=True, slots=True)
class LaneRoadMatchEvidence:
    """Versioned, JSON-safe road-match summary supplied to the G3 gate.

    This is deliberately a summary contract. The per-state detail stays in the
    CP1 diagnostic artifacts, and the G3 gate only needs the declared counts.
    The evidence can never claim a final scientific status.
    """

    scenario_id: str
    coordinate_frame: str
    overall: LaneRoadMatchSummary
    algorithm_version: str = ROAD_MATCH_VERSION
    config: LaneRoadMatchConfig = LaneRoadMatchConfig()
    selected_actor_ids: tuple[str, ...] = ()
    evidence_version: str = LANE_ROAD_MATCH_EVIDENCE_VERSION
    diagnostic_status: Literal["diagnostic"] = "diagnostic"
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("LaneRoadMatchEvidence scenario_id must not be empty.")
        if not self.coordinate_frame:
            raise ValueError("LaneRoadMatchEvidence coordinate_frame must not be empty.")
        if not self.algorithm_version:
            raise ValueError("LaneRoadMatchEvidence algorithm_version must not be empty.")
        if self.evidence_version != LANE_ROAD_MATCH_EVIDENCE_VERSION:
            raise ValueError("Unsupported lane road-match evidence version.")
        if self.diagnostic_status != "diagnostic":
            raise ValueError("Lane road-match evidence must remain diagnostic.")
        if self.scientific_status != "PROVISIONAL":
            raise ValueError("Lane road-match evidence must remain PROVISIONAL.")


def lane_road_match_evidence_from_report(
    report: LaneRoadMatchReport,
) -> LaneRoadMatchEvidence:
    """Project a full road-match report into gate-level evidence."""
    return LaneRoadMatchEvidence(
        scenario_id=report.scenario_id,
        coordinate_frame=report.coordinate_frame,
        overall=report.overall,
        algorithm_version=report.algorithm_version,
        config=report.config,
        selected_actor_ids=report.selected_actor_ids,
    )


def lane_road_match_evidence_to_dict(evidence: LaneRoadMatchEvidence) -> dict[str, object]:
    """Convert lane road-match evidence to deterministic JSON-safe data."""
    return {
        "evidence_version": evidence.evidence_version,
        "scenario_id": evidence.scenario_id,
        "coordinate_frame": evidence.coordinate_frame,
        "algorithm_version": evidence.algorithm_version,
        "config": {
            "max_distance_m": evidence.config.max_distance_m,
            "max_heading_error_rad": evidence.config.max_heading_error_rad,
        },
        "selected_actor_ids": list(evidence.selected_actor_ids),
        "overall": {
            "state_count": evidence.overall.state_count,
            "matched_state_count": evidence.overall.matched_state_count,
            "raw_match_rate": evidence.overall.raw_match_rate,
            "provisional_95_status": evidence.overall.provisional_95_status,
        },
        "diagnostic_status": evidence.diagnostic_status,
        "scientific_status": evidence.scientific_status,
    }


def lane_road_match_evidence_from_dict(payload: Mapping[str, object]) -> LaneRoadMatchEvidence:
    """Rebuild validated lane road-match evidence from JSON data.

    Unknown keys, inconsistent counts, a mismatched provisional status or any
    non-provisional scientific claim are rejected instead of being silently
    accepted or repaired.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("Lane road-match evidence must be a JSON object.")
    known = {
        "evidence_version",
        "scenario_id",
        "coordinate_frame",
        "algorithm_version",
        "config",
        "selected_actor_ids",
        "overall",
        "diagnostic_status",
        "scientific_status",
    }
    unknown = sorted(set(payload) - known)
    if unknown:
        raise ValueError(f"Unsupported lane road-match evidence fields: {', '.join(unknown)}.")
    if payload.get("scientific_status") != "PROVISIONAL":
        raise ValueError("Lane road-match evidence must declare scientific_status=PROVISIONAL.")
    if payload.get("diagnostic_status") != "diagnostic":
        raise ValueError("Lane road-match evidence must declare diagnostic_status=diagnostic.")
    overall_payload = payload.get("overall")
    if not isinstance(overall_payload, Mapping):
        raise ValueError("Lane road-match evidence requires an 'overall' object.")
    config_payload = payload.get("config") or {}
    if not isinstance(config_payload, Mapping):
        raise ValueError("Lane road-match evidence 'config' must be an object.")
    actor_ids = payload.get("selected_actor_ids") or []
    if not isinstance(actor_ids, (list, tuple)) or not all(
        isinstance(value, str) and value for value in actor_ids
    ):
        raise ValueError("Lane road-match evidence 'selected_actor_ids' must be strings.")
    return LaneRoadMatchEvidence(
        scenario_id=_evidence_string(payload, "scenario_id"),
        coordinate_frame=_evidence_string(payload, "coordinate_frame"),
        algorithm_version=_evidence_string(payload, "algorithm_version"),
        config=LaneRoadMatchConfig(
            max_distance_m=_evidence_float(config_payload, "max_distance_m"),
            max_heading_error_rad=_evidence_float(config_payload, "max_heading_error_rad"),
        ),
        selected_actor_ids=tuple(actor_ids),
        overall=LaneRoadMatchSummary(
            state_count=_evidence_int(overall_payload, "state_count"),
            matched_state_count=_evidence_int(overall_payload, "matched_state_count"),
            raw_match_rate=_evidence_float(overall_payload, "raw_match_rate"),
            provisional_95_status=_evidence_status(overall_payload),
        ),
        evidence_version=str(payload.get("evidence_version", "")),
    )


def _evidence_string(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Lane road-match evidence {name!r} must be a non-empty string.")
    return value


def _evidence_float(payload: Mapping[str, object], name: str) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"Lane road-match evidence {name!r} must be a finite number.")
    return float(value)


def _evidence_int(payload: Mapping[str, object], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Lane road-match evidence {name!r} must be an integer.")
    return value


def _evidence_status(payload: Mapping[str, object]) -> str:
    value = payload.get("provisional_95_status")
    if value not in {"at_or_above_95_percent", "below_95_percent"}:
        raise ValueError(
            "Lane road-match evidence provisional_95_status must be an explicit recorded value."
        )
    return str(value)
