"""Time-aligned gate segments for the Workspace gate lane.

The Workspace gate lane must never show placeholder segments.  Every segment
here is derived from gate evidence that exists for the canonical scenario that
the document currently shows, and every segment states its own status,
scientific status, reasons, observed values and time extent.

The domain CP4 contract fixes ``pass``/``fail``/``skipped``/``error`` for
:class:`real2scenario.gates.GateResult`.  A Workspace segment additionally
carries ``unsupported`` for a capability this surface does not evaluate, which
is a first-class state in the Workspace status vocabulary and never a pass.

Extents come from the scenario time domain, or from a declared main event when
the scenario declares one.  A gate never receives an invented window.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from real2scenario import evaluate_g4_g5, evaluate_temporary_g6_g7
from real2scenario.gates import G1_CONFIG_VERSION, GateResult
from real2scenario.models import Scenario


GATE_TIMELINE_VERSION = "workspace-gate-timeline-v1"
SEGMENT_STATUSES = ("pass", "fail", "skipped", "error", "unsupported")
EXTENT_SCENARIO_DOMAIN = "scenario_time_domain"
EXTENT_DECLARED_EVENT = "declared_main_event_window"

WORKSPACE_G1_REASON = "xosc_subset_not_evaluated_in_workspace_surface"
WORKSPACE_G2_REASON = "simulator_replay_not_recorded_for_this_scenario"
WORKSPACE_G3_REASON = "lane_road_match_evidence_not_supplied_for_this_scenario"


@dataclass(frozen=True, slots=True)
class GateSegment:
    """One gate lane segment aligned to the scenario time domain."""

    gate_id: str
    status: str
    start_s: float
    end_s: float
    reasons: tuple[str, ...] = ()
    config_version: str | None = None
    observed: Mapping[str, object] | None = None
    scientific_status: str = "not-applicable"
    extent_source: str = EXTENT_SCENARIO_DOMAIN

    def __post_init__(self) -> None:
        if self.status not in SEGMENT_STATUSES:
            raise ValueError("Gate segment status is outside the Workspace vocabulary.")
        if not all(isfinite(value) for value in (self.start_s, self.end_s)):
            raise ValueError("Gate segment extents must be finite.")
        if self.end_s < self.start_s:
            raise ValueError("Gate segment end_s must not precede start_s.")
        if self.extent_source not in {EXTENT_SCENARIO_DOMAIN, EXTENT_DECLARED_EVENT}:
            raise ValueError("Unknown gate segment extent source.")


def gate_timeline(scenario: Scenario) -> dict[str, object]:
    """Return gate segments aligned to the canonical scenario time domain."""
    segments = tuple(_segments(scenario))
    return {
        "contract_version": GATE_TIMELINE_VERSION,
        "scenario_id": scenario.scenario_id,
        "coordinate_frame": scenario.coordinate_frame,
        "time_domain": {"start_s": 0.0, "end_s": scenario.duration_s},
        "gates": [_to_dict(segment) for segment in segments],
        "counts": {
            status: sum(segment.status == status for segment in segments)
            for status in SEGMENT_STATUSES
        },
        "provisional_count": sum(
            segment.scientific_status == "PROVISIONAL" for segment in segments
        ),
        "artifact_visibility": "local_private",
    }


def _segments(scenario: Scenario) -> tuple[GateSegment, ...]:
    """Evaluate the Workspace gate subset from canonical evidence only."""
    unevaluated = (
        GateResult("G1", "skipped", (WORKSPACE_G1_REASON,), G1_CONFIG_VERSION, None),
        GateResult("G2", "skipped", (WORKSPACE_G2_REASON,), "simulator-completion-v1", None),
        GateResult(
            "G3", "skipped", (WORKSPACE_G3_REASON,), "lane-road-match-v1", None, "PROVISIONAL"
        ),
    )
    feasibility = evaluate_g4_g5(scenario)
    provisional = evaluate_temporary_g6_g7(scenario, variant_id=scenario.scenario_id).gates
    return (
        tuple(
            GateSegment(
                gate_id=gate.gate_id,
                status="skipped" if gate.gate_id == "G3" else "unsupported",
                start_s=0.0,
                end_s=scenario.duration_s,
                reasons=tuple(gate.reasons),
                config_version=gate.config_version,
                observed=None,
                scientific_status=gate.scientific_status,
            )
            for gate in unevaluated
        )
        + tuple(_segment(gate, scenario) for gate in (*feasibility.values(), *provisional))
    )


def _segment(gate: GateResult, scenario: Scenario) -> GateSegment:
    """Project one evaluated gate result onto the scenario time domain."""
    start_s, end_s, extent_source = _extent(gate, scenario)
    return GateSegment(
        gate_id=gate.gate_id,
        status=gate.status,
        start_s=start_s,
        end_s=end_s,
        reasons=tuple(gate.reasons),
        config_version=gate.config_version,
        observed=None if gate.observed is None else dict(gate.observed),
        scientific_status=gate.scientific_status,
        extent_source=extent_source,
    )


def _extent(gate: GateResult, scenario: Scenario) -> tuple[float, float, str]:
    """Use the declared main event window only when the gate recorded one."""
    if gate.gate_id == "G5" and gate.observed is not None:
        declared = _declared_event_window(gate.observed)
        if declared is not None:
            return declared[0], declared[1], EXTENT_DECLARED_EVENT
    return 0.0, scenario.duration_s, EXTENT_SCENARIO_DOMAIN


def _declared_event_window(observed: Mapping[str, object]) -> tuple[float, float] | None:
    start = observed.get("main_event_start_s")
    end = observed.get("main_event_end_s")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return None
    return float(start), float(end)


def _to_dict(segment: GateSegment) -> dict[str, object]:
    return {
        "gate_id": segment.gate_id,
        "status": segment.status,
        "scientific_status": segment.scientific_status,
        "reasons": list(segment.reasons),
        "config_version": segment.config_version,
        "observed": None if segment.observed is None else dict(segment.observed),
        "start_s": segment.start_s,
        "end_s": segment.end_s,
        "extent_source": segment.extent_source,
    }