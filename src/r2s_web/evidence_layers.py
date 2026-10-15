"""Evidence layers for the Workspace scenario surfaces.

The Workspace must never let a recorded trajectory, a generated variant
trajectory, a simulator replay trace and a recorded sensor sweep look like the
same evidence.  This module names each of those four layers separately and
reports, per layer, whether it exists, why it does not, which source produced
it, what provenance it carries, and which surface shows it.

A layer is never invented.  ``recorded`` comes from canonical scenario states,
``generated`` only from a variant artifact, ``replayed`` only from a replay trace
artifact that exists next to the scenario, and ``sensor-evidence`` only from the
recorded private LiDAR payload.  For a variant, post-edit sensor frames are not
generated, so the layer is ``unsupported`` with a reason and the recorded parent
sweep is offered as an explicit fallback rather than as a post-edit frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence

from real2scenario.models import Scenario

from .config import WebSettings
from .lidar import LidarService


EVIDENCE_LAYERS_VERSION = "workspace-evidence-layers-v1"
LAYER_KINDS = ("recorded", "generated", "replayed", "sensor-evidence")
LAYER_STATUSES = ("available", "unavailable", "unsupported")

REASON_GENERATED_REQUIRES_VARIANT = "generated_trajectory_requires_a_variant_artifact"
REASON_REPLAY_TRACE_ABSENT = "replay_trace_artifact_absent_for_this_scenario"
REASON_SENSOR_AFTER_EDIT = "post_edit_sensor_frames_are_not_generated_for_a_variant"
REASON_REPLAY_METRIC_STATUS = "replay_alignment_metrics_are_provisional"

RECORDED_SOURCE = "canonical-scenario-trajectory-v1"
GENERATED_SOURCE = "variant-artifact-trajectory-v1"
REPLAYED_SOURCE = "simulator-replay-trace-v1"
SENSOR_SOURCE = "recorded-lidar-top-sweep-v1"


@dataclass(frozen=True, slots=True)
class EvidenceLayer:
    """One named evidence layer with its own status and provenance."""

    layer: str
    status: str
    source: str
    unavailable_reason: str | None = None
    scientific_status: str = "PROVISIONAL"
    provenance: Mapping[str, str] | None = None
    coverage: float | None = None
    reference: str = ""
    parent_fallback: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if self.layer not in LAYER_KINDS:
            raise ValueError("Evidence layer is outside the Workspace vocabulary.")
        if self.status not in LAYER_STATUSES:
            raise ValueError("Evidence layer status is outside the Workspace vocabulary.")
        if self.status == "available" and self.unavailable_reason is not None:
            raise ValueError("An available evidence layer cannot carry an unavailable reason.")
        if self.status != "available" and not self.unavailable_reason:
            raise ValueError("An unavailable evidence layer must name its reason.")
        if self.coverage is not None and not isfinite(self.coverage):
            raise ValueError("Evidence layer coverage must be finite.")

    def to_dict(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "status": self.status,
            "unavailable_reason": self.unavailable_reason,
            "source": self.source,
            "scientific_status": self.scientific_status,
            "provenance": dict(self.provenance or {}),
            "coverage": self.coverage,
            "reference": self.reference,
            "parent_fallback": None if self.parent_fallback is None else dict(self.parent_fallback),
        }


def evidence_layers(
    scenario: Scenario,
    *,
    artifact_type: str,
    replay_trace_available: bool,
    replay_artifact: str | None,
    lidar: LidarService,
    settings: WebSettings | None,
    parent_scenario_id: str | None = None,
    reference_prefix: str = "/api/workspace/scenarios",
) -> dict[str, object]:
    """Return the four Workspace evidence layers for one scenario."""
    provenance = _scenario_provenance(scenario)
    recorded = EvidenceLayer(
        layer="recorded",
        status="available",
        source=RECORDED_SOURCE,
        provenance=provenance,
        coverage=_trajectory_coverage(scenario),
        reference=f"/api/scenarios/{scenario.scenario_id}/trajectory",
    )
    generated = (
        EvidenceLayer(
            layer="generated",
            status="available",
            source=GENERATED_SOURCE,
            provenance={**provenance, "artifact_type": artifact_type},
            coverage=_trajectory_coverage(scenario),
            reference=f"/api/scenarios/{scenario.scenario_id}/trajectory",
        )
        if artifact_type == "variant"
        else EvidenceLayer(
            layer="generated",
            status="unavailable",
            source=GENERATED_SOURCE,
            unavailable_reason=REASON_GENERATED_REQUIRES_VARIANT,
            provenance={**provenance, "artifact_type": artifact_type},
            reference=f"/api/scenarios/{scenario.scenario_id}/trajectory",
        )
    )
    replayed = (
        EvidenceLayer(
            layer="replayed",
            status="available",
            source=REPLAYED_SOURCE,
            provenance={
                **provenance,
                "replay_artifact": replay_artifact or "",
                "metric_status": REASON_REPLAY_METRIC_STATUS,
            },
            coverage=_trajectory_coverage(scenario),
            reference=f"/api/scenarios/{scenario.scenario_id}/trajectory",
        )
        if replay_trace_available
        else EvidenceLayer(
            layer="replayed",
            status="unavailable",
            source=REPLAYED_SOURCE,
            unavailable_reason=REASON_REPLAY_TRACE_ABSENT,
            provenance=provenance,
            reference=f"/api/scenarios/{scenario.scenario_id}/trajectory",
        )
    )
    sensor = _sensor_layer(
        scenario,
        artifact_type=artifact_type,
        lidar=lidar,
        settings=settings,
        parent_scenario_id=parent_scenario_id,
        reference_prefix=reference_prefix,
        provenance=provenance,
    )
    layers = (recorded, generated, replayed, sensor)
    return {
        "contract_version": EVIDENCE_LAYERS_VERSION,
        "scenario_id": scenario.scenario_id,
        "coordinate_frame": scenario.coordinate_frame,
        "layers": [layer.to_dict() for layer in layers],
        "available_count": sum(layer.status == "available" for layer in layers),
        "artifact_visibility": "local_private",
    }


def _sensor_layer(
    scenario: Scenario,
    *,
    artifact_type: str,
    lidar: LidarService,
    settings: WebSettings | None,
    parent_scenario_id: str | None,
    reference_prefix: str,
    provenance: Mapping[str, str],
) -> EvidenceLayer:
    """Report recorded sensor evidence, or the explicit post-edit gap."""
    token = _source_window_token(scenario)
    availability = lidar.availability(token)
    reference = f"{reference_prefix}/{scenario.scenario_id}/lidar"
    if artifact_type == "variant":
        return EvidenceLayer(
            layer="sensor-evidence",
            status="unsupported",
            source=SENSOR_SOURCE,
            unavailable_reason=REASON_SENSOR_AFTER_EDIT,
            provenance=provenance,
            reference=reference,
            parent_fallback={
                "available": bool(availability["available"]),
                "parent_scenario_id": parent_scenario_id,
                "unavailable_reason": availability["unavailable_reason"],
                "source": "recorded_parent_sweep",
                "note": "The parent sweep is recorded sensor evidence, not a post-edit frame.",
            },
        )
    available = bool(availability["available"])
    return EvidenceLayer(
        layer="sensor-evidence",
        status="available" if available else "unavailable",
        source=SENSOR_SOURCE,
        unavailable_reason=None if available else str(availability["unavailable_reason"]),
        provenance={**provenance, "sample_data_token": token},
        reference=reference,
    )


def _source_window_token(scenario: Scenario) -> str:
    return scenario.provenance.get("source_window", "").split(":", 1)[0]


def _scenario_provenance(scenario: Scenario) -> dict[str, str]:
    keys = (
        "dataset_version",
        "source_scene_token",
        "coordinate_transform_version",
        "generator_version",
    )
    return {key: scenario.provenance[key] for key in keys if key in scenario.provenance}


def _trajectory_coverage(scenario: Scenario) -> float | None:
    """Coverage is the share of declared actors that carry at least one state."""
    if not scenario.actors:
        return None
    resolved = sum(bool(actor.trajectory) for actor in scenario.actors)
    return resolved / len(scenario.actors)


def layer_map(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    """Index an evidence-layer payload by layer name."""
    layers: Sequence[Mapping[str, object]] = payload.get("layers", ())  # type: ignore[assignment]
    return {str(layer["layer"]): layer for layer in layers}