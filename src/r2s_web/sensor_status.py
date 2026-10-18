"""Explicit variant sensor-frame capability and parent-sweep fallback."""

from __future__ import annotations

from typing import Mapping

from .adapter import ArtifactRecord
from .lidar import LidarService


SENSOR_STATUS_VERSION = "workspace-variant-sensor-v1"
REASON_POST_EDIT_UNSUPPORTED = "post_edit_sensor_frames_not_generated"
REASON_BASELINE_POST_EDIT_NOT_APPLICABLE = "post_edit_sensor_frames_apply_to_variants_only"
REASON_PARENT_SWEEP_UNAVAILABLE = "recorded_parent_sweep_unavailable"


def variant_sensor_status(record: ArtifactRecord, lidar: LidarService) -> dict[str, object]:
    """Return post-edit status without turning a parent sweep into a variant frame."""
    window_token = record.scenario.provenance.get("source_window", "").split(":", 1)[0]
    try:
        token = lidar.sample_data_token(window_token)
    except (AssertionError, FileNotFoundError, ImportError, KeyError, OSError, RuntimeError, ValueError):
        token = window_token
    try:
        availability = lidar.availability(token)
    except (AssertionError, FileNotFoundError, ImportError, KeyError, OSError, RuntimeError, ValueError):
        availability = {"available": False, "unavailable_reason": "dataset_not_configured"}
    descriptor = None
    if availability["available"]:
        try:
            descriptor = lidar.descriptor(token)
        except (AssertionError, FileNotFoundError, ImportError, KeyError, OSError, RuntimeError, ValueError):
            descriptor = None
    parent = {
        "available": bool(availability["available"]),
        "scenario_id": record.parent_scenario_id,
        "sample_data_token": token or None,
        "timestamp_us": None if descriptor is None else descriptor.get("timestamp_us"),
        "source": "recorded_parent_sweep",
        "unavailable_reason": None
        if availability["available"]
        else str(availability["unavailable_reason"] or REASON_PARENT_SWEEP_UNAVAILABLE),
    }
    provenance = {
        key: record.scenario.provenance[key]
        for key in ("dataset_version", "source_scene_token", "coordinate_transform_version")
        if key in record.scenario.provenance
    }
    if record.artifact_type == "variant":
        return {
            "contract_version": SENSOR_STATUS_VERSION,
            "scenario_id": record.scenario.scenario_id,
            "artifact_type": "variant",
            "status": "unsupported",
            "post_edit_frames": {
                "available": False,
                "unavailable_reason": REASON_POST_EDIT_UNSUPPORTED,
            },
            "parent_sweep": parent,
            "unavailable_reason": REASON_POST_EDIT_UNSUPPORTED,
            "provenance": provenance,
            "artifact_visibility": "local_private",
        }
    return {
        "contract_version": SENSOR_STATUS_VERSION,
        "scenario_id": record.scenario.scenario_id,
        "artifact_type": "baseline",
        "status": "unavailable" if not availability["available"] else "unsupported",
        "post_edit_frames": {
            "available": False,
            "unavailable_reason": REASON_BASELINE_POST_EDIT_NOT_APPLICABLE,
        },
        "parent_sweep": {**parent, "scenario_id": record.scenario.scenario_id},
        "unavailable_reason": REASON_BASELINE_POST_EDIT_NOT_APPLICABLE,
        "provenance": provenance,
        "artifact_visibility": "local_private",
    }
