"""Versioned validity-gate and temporary funnel contracts."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, isfinite, sin
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from .models import Scenario
from .ranking import compute_risk_features
from .validation import FeasibilityLimits, validate_feasibility
from .road_match import LaneRoadMatchEvidence, LaneRoadMatchReport
from .xosc_subset import parse_xosc_subset


GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
G6_CONFIG_VERSION = "rare-event-v0-provisional"
G7_CONFIG_VERSION = "diversity-v0-provisional"
G1_CONFIG_VERSION = "xosc-schema-v1"
G2_CONFIG_VERSION = "simulator-completion-v1"
G3_CONFIG_VERSION = "lane-road-match-v1"
G5_EVENT_PROVENANCE_KEYS = (
    "main_event_start_s",
    "main_event_end_s",
    "event_type",
    "event_target_actor_id",
)
G3_MINIMUM_MATCH_RATE = 0.95


class RoadMatchEvidence(Protocol):
    """Minimal road-match evidence contract accepted by the G3 gate."""

    overall: object
    scientific_status: str


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: str
    status: str
    reasons: tuple[str, ...] = ()
    config_version: str | None = None
    observed: Mapping[str, float | str | bool | None] | None = None
    scientific_status: str = "not-applicable"

    def __post_init__(self) -> None:
        if self.gate_id not in GATE_IDS:
            raise ValueError(f"Unknown gate {self.gate_id!r}.")
        if self.status not in {"pass", "fail", "skipped", "error"}:
            raise ValueError("Gate status must be pass, fail, skipped or error.")
        if self.scientific_status not in {"not-applicable", "PROVISIONAL", "FINAL"}:
            raise ValueError("Invalid scientific_status.")


@dataclass(frozen=True, slots=True)
class FunnelReport:
    variant_id: str
    gates: tuple[GateResult, ...]
    temporary: bool = True

    def __post_init__(self) -> None:
        ids = tuple(gate.gate_id for gate in self.gates)
        if ids != tuple(dict.fromkeys(ids)):
            raise ValueError("Funnel gates must not contain duplicate gate IDs.")
        if any(gate.gate_id not in GATE_IDS for gate in self.gates):
            raise ValueError("Funnel contains an unknown gate.")

    @property
    def final_valid(self) -> bool:
        return not self.temporary and all(gate.status == "pass" for gate in self.gates)

    @property
    def temporary_valid(self) -> bool:
        return all(gate.status == "pass" for gate in self.gates if gate.status not in {"skipped", "error"})

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(gate.gate_id for gate in self.gates if gate.status == "fail")

    @property
    def first_failed_gate(self) -> str | None:
        return self.failed_gates[0] if self.failed_gates else None


@dataclass(frozen=True, slots=True)
class FunnelSummary:
    generated: int
    gate_pass_counts: Mapping[str, int]
    temporary_valid_count: int
    scientific_status: str = "PROVISIONAL"

    def __post_init__(self) -> None:
        if self.generated < 0 or self.temporary_valid_count < 0:
            raise ValueError("Funnel counts must be non-negative.")
        if self.temporary_valid_count > self.generated:
            raise ValueError("temporary_valid_count cannot exceed generated.")
        if self.scientific_status not in {"PROVISIONAL", "FINAL"}:
            raise ValueError("Invalid funnel scientific_status.")

    @property
    def final_valid_count(self) -> None:
        """Final scientific count is intentionally unavailable for provisional funnels."""
        if self.scientific_status != "FINAL":
            return None
        return self.temporary_valid_count


@dataclass(frozen=True, slots=True)
class GateFunnelSummary:
    """Reconciled per-gate and cumulative counts for a CP4 candidate set."""

    generated: int
    evaluated_counts: Mapping[str, int]
    pass_counts: Mapping[str, int]
    cumulative_pass_counts: Mapping[str, int]
    scientific_status: str = "PROVISIONAL"

    def __post_init__(self) -> None:
        if self.generated < 0:
            raise ValueError("generated must be non-negative.")
        if tuple(self.evaluated_counts) != GATE_IDS:
            raise ValueError("evaluated_counts must contain G1-G7 in order.")
        if tuple(self.pass_counts) != GATE_IDS or tuple(self.cumulative_pass_counts) != GATE_IDS:
            raise ValueError("funnel count maps must contain G1-G7 in order.")
        for counts in (self.evaluated_counts, self.pass_counts, self.cumulative_pass_counts):
            if any(value < 0 or value > self.generated for value in counts.values()):
                raise ValueError("funnel counts must be within generated bounds.")
        if any(self.pass_counts[gate_id] > self.evaluated_counts[gate_id] for gate_id in GATE_IDS):
            raise ValueError("pass counts cannot exceed evaluated counts.")
        if any(
            self.cumulative_pass_counts[gate_id] > self.cumulative_pass_counts[GATE_IDS[index - 1]]
            for index, gate_id in enumerate(GATE_IDS) if index
        ):
            raise ValueError("cumulative funnel counts must not increase.")
        if self.scientific_status not in {"PROVISIONAL", "FINAL"}:
            raise ValueError("Invalid funnel scientific_status.")


def evaluate_temporary_g6_g7(
    scenario: Scenario,
    *,
    variant_id: str | None = None,
    ttc_threshold_s: float = 2.0,
    clearance_threshold_m: float = 1.0,
    ttc_horizon_s: float = 10.0,
    diversity_distance: float | None = None,
    diversity_epsilon: float = 0.15,
    normalization_bounds: Mapping[str, tuple[float, float]] | None = None,
    no_collision: bool | None = None,
) -> FunnelReport:
    """Evaluate the development-only G6/G7 policy without final claims."""
    if not all(isfinite(value) and value > 0 for value in (ttc_threshold_s, ttc_horizon_s, diversity_epsilon)):
        raise ValueError("G6/G7 positive configuration values must be finite.")
    if not isfinite(clearance_threshold_m) or clearance_threshold_m < 0:
        raise ValueError("clearance_threshold_m must be finite and non-negative.")
    features = compute_risk_features(scenario, ttc_horizon_s=ttc_horizon_s)
    minimum_ttc = features.minimum_ttc_s
    minimum_distance = features.minimum_distance_m
    rare = (
        (minimum_ttc is not None and minimum_ttc <= ttc_threshold_s)
        or (minimum_distance is not None and minimum_distance <= clearance_threshold_m)
    )
    collision_free = no_collision is True
    g6 = GateResult(
        "G6",
        "pass" if rare and collision_free else "fail",
        tuple(
            reason
            for reason, condition in (
                ("rare_threshold_not_reached", not rare),
                ("collision_status_unverified", no_collision is None),
                ("collision_detected", no_collision is False),
            )
            if condition
        ),
        G6_CONFIG_VERSION,
        {
            "minimum_ttc_s": minimum_ttc,
            "minimum_clearance_m": minimum_distance,
            "ttc_threshold_s": ttc_threshold_s,
            "clearance_threshold_m": clearance_threshold_m,
            "ttc_horizon_s": ttc_horizon_s,
            "no_collision": no_collision,
        },
        "PROVISIONAL",
    )
    g7_pass = diversity_distance is None or diversity_distance >= diversity_epsilon
    g7 = GateResult(
        "G7",
        "pass" if g7_pass else "fail",
        () if g7_pass else ("near_duplicate",),
        G7_CONFIG_VERSION,
        {
            "distance": diversity_distance,
            "epsilon": diversity_epsilon,
            "normalization_bounds": str(normalization_bounds or {}),
        },
        "PROVISIONAL",
    )
    return FunnelReport(variant_id or scenario.scenario_id, (g6, g7), temporary=True)


def evaluate_g1_xosc(
    xosc_path: str | Path,
    xodr_path: str | Path | None,
) -> GateResult:
    """Validate the supported XOSC subset as a structured CP4 G1 result."""
    try:
        validated = parse_xosc_subset(xosc_path, xodr_path)
    except (OSError, ValueError) as error:
        return GateResult(
            "G1", "error", (str(error),), G1_CONFIG_VERSION,
            {"xosc_path": str(xosc_path), "xodr_path": None if xodr_path is None else str(xodr_path)},
        )
    return GateResult(
        "G1", "pass", (), G1_CONFIG_VERSION,
        {
            "subset_version": validated.subset_version,
            "entity_count": len(validated.entity_names),
            "trajectory_count": len(validated.trajectories),
            "map_reference": validated.map_reference,
        },
    )


def evaluate_g2_simulator_completion(
    simulator_statuses: Mapping[str, str],
    *,
    required_simulators: Sequence[str] = ("esmini",),
) -> GateResult:
    """Record simulator completion independently for each requested backend."""
    required = tuple(required_simulators)
    if not required or len(set(required)) != len(required):
        raise ValueError("required_simulators must be non-empty and unique.")
    allowed = {"completed", "failed", "unverified", "skipped"}
    if any(status not in allowed for status in simulator_statuses.values()):
        raise ValueError("Simulator status must be completed, failed, unverified or skipped.")
    missing = tuple(simulator for simulator in required if simulator not in simulator_statuses)
    observed = {simulator: simulator_statuses.get(simulator, "unverified") for simulator in required}
    if missing:
        return GateResult("G2", "error", ("missing_simulator_status",), G2_CONFIG_VERSION, observed)
    if any(status == "failed" for status in observed.values()):
        status = "fail"
        reasons = ("simulator_failed",)
    elif all(status == "completed" for status in observed.values()):
        status = "pass"
        reasons = ()
    else:
        status = "skipped"
        reasons = ("simulator_completion_unverified",)
    return GateResult("G2", status, reasons, G2_CONFIG_VERSION, observed)


def evaluate_g3_road_match(
    report: LaneRoadMatchReport | LaneRoadMatchEvidence | None,
    *,
    minimum_match_rate: float = G3_MINIMUM_MATCH_RATE,
) -> GateResult:
    """Evaluate the provisional road-match reference without declaring science.

    ``report`` may be a full CP1 road-match report or the gate-level
    ``LaneRoadMatchEvidence`` summary. Missing evidence is reported as an
    explicit skip, never as a pass, and the provisional 95% reference is fixed.
    """
    if not isfinite(minimum_match_rate) or not 0 <= minimum_match_rate <= 1:
        raise ValueError("minimum_match_rate must be finite and within [0, 1].")
    if report is None:
        return GateResult("G3", "skipped", ("road_match_unavailable",), G3_CONFIG_VERSION, None, "PROVISIONAL")
    passed = report.overall.raw_match_rate >= minimum_match_rate
    return GateResult(
        "G3", "pass" if passed else "fail",
        () if passed else ("road_match_below_provisional_threshold",),
        G3_CONFIG_VERSION,
        {
            "raw_match_rate": report.overall.raw_match_rate,
            "matched_state_count": report.overall.matched_state_count,
            "state_count": report.overall.state_count,
            "minimum_match_rate": minimum_match_rate,
            "scientific_status": report.scientific_status,
        },
        "PROVISIONAL",
    )


def evaluate_cp4_gates(
    scenario: Scenario,
    *,
    xosc_path: str | Path | None = None,
    xodr_path: str | Path | None = None,
    simulator_statuses: Mapping[str, str] | None = None,
    required_simulators: Sequence[str] = ("esmini",),
    lane_match_report: LaneRoadMatchReport | LaneRoadMatchEvidence | None = None,
    minimum_match_rate: float = G3_MINIMUM_MATCH_RATE,
    event_declaration: Mapping[str, object] | None = None,
    limits: FeasibilityLimits = FeasibilityLimits(),
    diversity_distance: float | None = None,
    no_collision: bool | None = None,
) -> tuple[GateResult, ...]:
    """Evaluate one candidate across the complete additive CP4 G1-G7 funnel."""
    g1 = evaluate_g1_xosc(xosc_path, xodr_path) if xosc_path is not None else GateResult(
        "G1", "skipped", ("xosc_unavailable",), G1_CONFIG_VERSION, None,
    )
    g2 = evaluate_g2_simulator_completion(
        simulator_statuses or {}, required_simulators=required_simulators,
    )
    g3 = evaluate_g3_road_match(lane_match_report, minimum_match_rate=minimum_match_rate)
    g45 = evaluate_g4_g5(scenario, limits=limits, event_declaration=event_declaration)
    g67 = evaluate_temporary_g6_g7(
        scenario, variant_id=scenario.scenario_id,
        diversity_distance=diversity_distance, no_collision=no_collision,
    ).gates
    return (g1, g2, g3, g45["G4"], g45["G5"], *g67)


def summarize_gate_funnel(reports: Sequence[Sequence[GateResult]]) -> GateFunnelSummary:
    """Reconcile candidate counts through G1->G7 without exposing final validity."""
    normalized = []
    for report in reports:
        by_id = {gate.gate_id: gate for gate in report}
        if tuple(sorted(by_id, key=lambda gate_id: GATE_IDS.index(gate_id))) != GATE_IDS:
            raise ValueError("Each CP4 report must contain exactly G1-G7 once.")
        normalized.append(by_id)
    evaluated = {gate_id: sum(gate_id in report and report[gate_id].status not in {"skipped", "error"} for report in normalized) for gate_id in GATE_IDS}
    passed = {gate_id: sum(report[gate_id].status == "pass" for report in normalized) for gate_id in GATE_IDS}
    cumulative: dict[str, int] = {}
    eligible = len(normalized)
    for gate_id in GATE_IDS:
        eligible = sum(
            all(report[prior].status == "pass" for prior in GATE_IDS[: GATE_IDS.index(gate_id) + 1])
            for report in normalized
        )
        cumulative[gate_id] = eligible
    return GateFunnelSummary(len(normalized), evaluated, passed, cumulative)


def evaluate_g4_g5(
    scenario: Scenario,
    *,
    limits: FeasibilityLimits = FeasibilityLimits(),
    event_declaration: Mapping[str, object] | None = None,
) -> dict[str, GateResult]:
    """Evaluate physics and pre-event footprint collision gates.

    G5 evaluates a declared main event. The declaration comes from scenario
    provenance or from an explicit caller-supplied mapping; the caller value is
    validated before use and never inferred from the trajectory. A candidate
    without a declaration is explicitly ``skipped`` because the capability was
    not declared, while a malformed declaration is an ``error`` because supplied
    evidence could not be used.
    """
    feasibility = validate_feasibility(scenario, limits)
    g4 = GateResult(
        "G4",
        "pass" if feasibility.valid else "fail",
        tuple(reason.code for reason in feasibility.reasons),
        limits.version,
        {"reason_count": len(feasibility.reasons)},
    )
    declared = _event_declaration(scenario, event_declaration)
    if not declared:
        return {
            "G4": g4,
            "G5": GateResult("G5", "skipped", ("event_definition_not_declared",)),
        }
    try:
        event_start_s, event_end_s, event_type, target_id = _validated_event(
            scenario, declared
        )
    except ValueError as error:
        return {"G4": g4, "G5": GateResult("G5", "error", (str(error),))}
    actors = [actor for actor in scenario.actors if actor.actor_id != target_id]
    target = next(actor for actor in scenario.actors if actor.actor_id == target_id)
    collision = any(
        _footprints_overlap(first, first_state, target, target_state)
        for first in actors
        for first_state in first.trajectory
        for target_state in target.trajectory
        if first_state.time_s == target_state.time_s and first_state.time_s < event_start_s
    )
    return {
        "G4": g4,
        "G5": GateResult(
            "G5",
            "fail" if collision else "pass",
            ("collision_before_main_event",) if collision else (),
            "footprint-collision-v0",
            {
                "main_event_start_s": event_start_s,
                "main_event_end_s": event_end_s,
                "event_type": event_type,
                "event_source": declared.get("event_source", "scenario_provenance"),
            },
        ),
    }


def _event_declaration(
    scenario: Scenario, event_declaration: Mapping[str, object] | None
) -> Mapping[str, object] | None:
    """Return the explicit event declaration without inferring one."""
    if event_declaration is not None:
        unknown = sorted(set(event_declaration) - set(G5_EVENT_PROVENANCE_KEYS) - {"event_source"})
        if unknown:
            raise ValueError(f"unsupported_event_fields: {','.join(unknown)}")
        if any(key not in event_declaration for key in G5_EVENT_PROVENANCE_KEYS):
            raise ValueError("incomplete_event_declaration")
        return event_declaration
    if all(key in scenario.provenance for key in G5_EVENT_PROVENANCE_KEYS):
        return scenario.provenance
    return None


def _validated_event(
    scenario: Scenario, declared: Mapping[str, object]
) -> tuple[float, float, str, str]:
    try:
        event_start_s = float(declared["main_event_start_s"])  # type: ignore[arg-type]
        event_end_s = float(declared["main_event_end_s"])  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError("invalid_event_window") from error
    if not isfinite(event_start_s) or not isfinite(event_end_s):
        raise ValueError("invalid_event_window")
    if event_end_s <= event_start_s:
        raise ValueError("invalid_event_window")
    duration_s = scenario.duration_s
    if event_start_s < 0 or event_end_s > duration_s:
        raise ValueError("event_window_outside_scenario")
    event_type = declared["event_type"]
    target_id = declared["event_target_actor_id"]
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("invalid_event_type")
    if not isinstance(target_id, str) or not target_id:
        raise ValueError("unknown_event_target")
    if all(actor.actor_id != target_id for actor in scenario.actors):
        raise ValueError("unknown_event_target")
    return event_start_s, event_end_s, event_type, target_id


def _footprints_overlap(first, first_state, second, second_state) -> bool:
    distance = hypot(first_state.x_m - second_state.x_m, first_state.y_m - second_state.y_m)
    radius = ((first.length_m or 4.5) ** 2 + (first.width_m or 1.8) ** 2) ** 0.5 / 2
    radius += ((second.length_m or 4.5) ** 2 + (second.width_m or 1.8) ** 2) ** 0.5 / 2
    return distance <= radius


def summarize_funnels(reports: Sequence[FunnelReport]) -> FunnelSummary:
    """Summarize temporary gate counts without exposing final_valid_count."""
    gate_pass_counts = {
        gate_id: sum(
            any(gate.gate_id == gate_id and gate.status == "pass" for gate in report.gates)
            for report in reports
        )
        for gate_id in GATE_IDS
    }
    temporary_valid_count = sum(report.temporary_valid for report in reports)
    return FunnelSummary(
        generated=len(reports),
        gate_pass_counts=gate_pass_counts,
        temporary_valid_count=temporary_valid_count,
    )
