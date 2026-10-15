"""Synchronized side-by-side comparison of two Workspace scenarios.

Compare answers one question: at the same timestamp, how do two documents differ,
and what evidence produced each side?  It is synchronized on scenario time, not
on sample index, and it never merges the two documents.

Every number carries the status of the side it came from.  A side without a
replay trace, metric or gate reason says so with an API-owned reason instead of
rendering zero.  Scientific status travels with the metric comparison because
replay alignment metrics remain provisional in this project.
"""

from __future__ import annotations

from math import atan2, cos, hypot, isfinite, sin
from typing import Mapping, Sequence

from real2scenario.models import Scenario

from .adapter import ArtifactRecord
from .gate_timeline import gate_timeline
from .lineage import variant_lineage

COMPARE_VERSION = "workspace-compare-v1"
SYNC_MODE = "scenario_time"
ACTOR_TIMING_TOLERANCE_S = 1e-6

REASON_ACTOR_ABSENT = "actor_is_absent_from_this_side"
REASON_STATE_BEYOND_HORIZON = "actor_state_unavailable_at_the_shared_timestamp"
REASON_METRICS_UNAVAILABLE = "replay_metrics_are_unavailable_for_this_side"
REASON_DURATION_MISMATCH = "side_durations_differ_the_shared_horizon_is_the_shorter_one"

AGGREGATE_ROWS = (
    ("ade_m.mean", "mean_ade_m", "m"),
    ("ade_m.p95", "p95_ade_m", "m"),
    ("fde_m.mean", "mean_fde_m", "m"),
)


def compare_payload(
    left: ArtifactRecord,
    right: ArtifactRecord,
    *,
    time_s: float,
    left_metrics: Mapping[str, object] | None,
    right_metrics: Mapping[str, object] | None,
    left_evidence: Mapping[str, object],
    right_evidence: Mapping[str, object],
) -> dict[str, object]:
    """Return the synchronized comparison payload for two scenarios."""
    horizon = min(left.scenario.duration_s, right.scenario.duration_s)
    at = min(max(time_s, 0.0), horizon)
    durations_differ = left.scenario.duration_s != right.scenario.duration_s
    return {
        "contract_version": COMPARE_VERSION,
        "synchronization": {
            "mode": SYNC_MODE,
            "time_s": at,
            "requested_time_s": time_s,
            "time_domain": {"start_s": 0.0, "end_s": horizon},
            "left_duration_s": left.scenario.duration_s,
            "right_duration_s": right.scenario.duration_s,
            "durations_differ": durations_differ,
            "duration_unavailable_reason": REASON_DURATION_MISMATCH if durations_differ else None,
            "reference_point": "scenario_time_origin",
        },
        "sides": [
            _side(left, left_evidence),
            _side(right, right_evidence),
        ],
        "actors": _actors(left.scenario, right.scenario, at),
        "metrics": _metric_rows(left_metrics, right_metrics),
        "metric_provenance": {
            "left": _metric_provenance(left, left_metrics),
            "right": _metric_provenance(right, right_metrics),
        },
        "metric_scientific_status": "PROVISIONAL",
        "gates": _gates(left.scenario, right.scenario),
        "artifact_visibility": "local_private",
    }


def _side(record: ArtifactRecord, evidence: Mapping[str, object]) -> dict[str, object]:
    lineage = variant_lineage(record)
    branch = lineage["branch"]
    fields = lineage["fields"]
    return {
        "scenario_id": record.scenario.scenario_id,
        "artifact_type": record.artifact_type,
        "parent_scenario_id": record.parent_scenario_id,
        "branch_id": branch["branch_id"],
        "branch_name": branch["branch_name"],
        "seed": fields["seed"],
        "config_hash": fields["config_hash"],
        "coordinate_frame": record.scenario.coordinate_frame,
        "duration_s": record.scenario.duration_s,
        "layer_kinds": [
            str(layer["layer"])
            for layer in evidence.get("layers", ())  # type: ignore[union-attr]
            if layer["status"] == "available"
        ],
        "evidence_layers": list(evidence.get("layers", ())),  # type: ignore[arg-type]
    }


def _actors(
    left: Scenario, right: Scenario, time_s: float
) -> list[dict[str, object]]:
    """Compare the union of both actor sets at one shared timestamp."""
    actors = sorted(
        {actor.actor_id for actor in left.actors} | {actor.actor_id for actor in right.actors}
    )
    rows: list[dict[str, object]] = []
    for actor_id in actors:
        left_actor = next((item for item in left.actors if item.actor_id == actor_id), None)
        right_actor = next((item for item in right.actors if item.actor_id == actor_id), None)
        left_state = _state(left, actor_id, time_s)
        right_state = _state(right, actor_id, time_s)
        deltas = _deltas(left_state, right_state)
        source = left_actor or right_actor
        rows.append(
            {
                "actor_id": actor_id,
                "actor_type": source.actor_type if source else None,
                "role": _role(left, actor_id) or _role(right, actor_id),
                "left": left_state,
                "right": right_state,
                **deltas,
            }
        )
    return rows


def _role(scenario: Scenario, actor_id: str) -> str | None:
    if any(actor.actor_id == actor_id for actor in scenario.actors) is False:
        return None
    return "ego" if actor_id == scenario.ego_actor_id else "actor"


def _state(scenario: Scenario, actor_id: str, time_s: float) -> dict[str, object]:
    """Nearest state at or before the shared timestamp, without extrapolation."""
    actor = next((item for item in scenario.actors if item.actor_id == actor_id), None)
    if actor is None:
        return {
            "status": "unavailable",
            "unavailable_reason": REASON_ACTOR_ABSENT,
            "x_m": None,
            "y_m": None,
            "yaw_rad": None,
            "speed_mps": None,
        }
    candidate = None
    for state in actor.trajectory:
        if state.time_s <= time_s + ACTOR_TIMING_TOLERANCE_S:
            candidate = state
    if candidate is None and actor.trajectory and time_s < actor.trajectory[0].time_s:
        candidate = actor.trajectory[0]
    if candidate is None:
        return {
            "status": "unavailable",
            "unavailable_reason": REASON_STATE_BEYOND_HORIZON,
            "x_m": None,
            "y_m": None,
            "yaw_rad": None,
            "speed_mps": None,
        }
    return {
        "status": "measured",
        "unavailable_reason": None,
        "x_m": candidate.x_m,
        "y_m": candidate.y_m,
        "yaw_rad": candidate.yaw_rad,
        "speed_mps": candidate.speed_mps,
    }


def _deltas(left: Mapping[str, object], right: Mapping[str, object]) -> dict[str, object]:
    if left["status"] != "measured" or right["status"] != "measured":
        reason = str(
            left["unavailable_reason"] or right["unavailable_reason"] or REASON_ACTOR_ABSENT
        )
        return {
            "position_delta_m": None,
            "heading_delta_rad": None,
            "speed_delta_mps": None,
            "delta_unavailable_reason": reason,
        }
    heading = atan2(
        sin(float(right["yaw_rad"]) - float(left["yaw_rad"])),
        cos(float(right["yaw_rad"]) - float(left["yaw_rad"])),
    )
    return {
        "position_delta_m": hypot(
            float(right["x_m"]) - float(left["x_m"]), float(right["y_m"]) - float(left["y_m"])
        ),
        "heading_delta_rad": heading,
        "speed_delta_mps": float(right["speed_mps"]) - float(left["speed_mps"]),
        "delta_unavailable_reason": None,
    }


def _metric_rows(
    left_metrics: Mapping[str, object] | None,
    right_metrics: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    """One row per comparable aggregate metric with both sides' status."""
    left_values = _aggregate_values(left_metrics)
    right_values = _aggregate_values(right_metrics)
    left_available = bool(left_values)
    right_available = bool(right_values)
    return [
        _metric_row(
            label,
            unit,
            left_values.get(key),
            left_available,
            left_metrics,
            right_values.get(key),
            right_available,
            right_metrics,
        )
        for label, key, unit in AGGREGATE_ROWS
    ]


def _metric_row(
    label: str,
    unit: str,
    left_value: float | None,
    left_available: bool,
    left_metrics: Mapping[str, object] | None,
    right_value: float | None,
    right_available: bool,
    right_metrics: Mapping[str, object] | None,
) -> dict[str, object]:
    left_status = "available" if left_available else "unavailable"
    right_status = "available" if right_available else "unavailable"
    left_reason = None if left_available else str(_reason(left_metrics))
    right_reason = None if right_available else str(_reason(right_metrics))
    delta = (
        float(right_value) - float(left_value)
        if left_value is not None and right_value is not None
        else None
    )
    return {
        "metric": label,
        "left_value": left_value,
        "left_status": left_status,
        "left_reason": left_reason,
        "right_value": right_value,
        "right_status": right_status,
        "right_reason": right_reason,
        "delta": delta,
        "delta_unavailable_reason": None
        if delta is not None
        else (left_reason or right_reason or REASON_METRICS_UNAVAILABLE),
        "unit": unit,
        "scientific_status": "PROVISIONAL",
    }


def _reason(metrics: Mapping[str, object] | None) -> str:
    if metrics is None:
        return REASON_METRICS_UNAVAILABLE
    return str(metrics.get("unavailable_reason") or REASON_METRICS_UNAVAILABLE)


def _metric_provenance(
    record: ArtifactRecord, metrics: Mapping[str, object] | None
) -> dict[str, object]:
    """Attach dataset, transform and alignment provenance to a metric block."""
    provenance = record.scenario.provenance
    return {
        "available": bool(metrics and metrics.get("available")),
        "unavailable_reason": None if metrics and metrics.get("available") else _reason(metrics),
        "source": (metrics or {}).get("source", "none"),
        "scientific_status": (metrics or {}).get("scientific_status", "PROVISIONAL"),
        "alignment_method": (metrics or {}).get("alignment_method"),
        "dataset_version": provenance.get("dataset_version"),
        "source_scene_token": provenance.get("source_scene_token"),
        "transform_version": provenance.get("coordinate_transform_version"),
        "generator_version": provenance.get("generator_version"),
    }


def _aggregate_values(metrics: Mapping[str, object] | None) -> dict[str, float]:
    """Flatten the aggregate distribution the metric block actually carries."""
    if not metrics or not metrics.get("available"):
        return {}
    aggregate = metrics.get("aggregate")
    if not isinstance(aggregate, Mapping):
        return {}
    values: dict[str, float] = {}
    for prefix, key, _ in AGGREGATE_ROWS:
        group, _, statistic = prefix.partition(".")
        block = aggregate.get(group) if isinstance(aggregate.get(group), Mapping) else None
        if block is None or block.get(statistic) is None:
            continue
        value = float(block[statistic])
        if not isfinite(value):
            continue
        values[key] = value
    return values


def _gates(left: Scenario, right: Scenario) -> list[dict[str, object]]:
    """Compare gate statuses by gate id, including sides that do not evaluate."""
    left_gates = {gate["gate_id"]: gate for gate in gate_timeline(left)["gates"]}  # type: ignore[index]
    right_gates = {gate["gate_id"]: gate for gate in gate_timeline(right)["gates"]}  # type: ignore[index]
    rows: list[dict[str, object]] = []
    for gate_id in sorted(set(left_gates) | set(right_gates)):
        left_gate = left_gates.get(gate_id, {})
        right_gate = right_gates.get(gate_id, {})
        rows.append(
            {
                "gate_id": gate_id,
                "left_status": left_gate.get("status"),
                "right_status": right_gate.get("status"),
                "differs": left_gate.get("status") != right_gate.get("status"),
                "left_scientific_status": left_gate.get("scientific_status"),
                "right_scientific_status": right_gate.get("scientific_status"),
                "left_reasons": list(left_gate.get("reasons", ())),
                "right_reasons": list(right_gate.get("reasons", ())),
            }
        )
    return rows


def metric_labels() -> Sequence[str]:
    """Expose the aggregate comparison labels for documentation and tests."""
    return tuple(label for label, _, _ in AGGREGATE_ROWS)