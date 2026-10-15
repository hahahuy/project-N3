"""Variant lineage, branch identity, seed and configuration hash.

The Variant studio must be able to answer "which document is this, which
document did it come from, which branch does it belong to, what seed and
configuration produced it, and what is the hash of that configuration" without
the browser inventing any of it.

Every field here is read from a canonical artifact or computed from declared
artifact content.  A field that no artifact declares is ``null`` together with
an API-owned reason; it is never defaulted to ``0``, ``""`` or a placeholder
hash.  The configuration hash covers the canonical variant configuration and
names the content it covers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from .adapter import ArtifactRecord

VARIANT_LINEAGE_VERSION = "workspace-variant-lineage-v1"
BRANCH_ID_PREFIX = "branch-"
MAX_LINEAGE_DEPTH = 64

REASON_NO_VARIANT_CONFIG = "artifact_declares_no_variant_configuration"
REASON_NO_SEED = "variant_configuration_declares_no_seed"
REASON_NO_RUN_ID = "scenario_provenance_declares_no_run_id"
REASON_NO_BRANCH_NAME = "scenario_provenance_declares_no_branch_name"
REASON_PARENT_ARTIFACT_ABSENT = "parent_artifact_is_not_present_in_the_artifact_root"

PROVENANCE_KEYS = (
    "dataset_name",
    "dataset_version",
    "generator_version",
    "source_scene_token",
    "coordinate_transform_version",
    "map_reconstruction_version",
)


@dataclass(frozen=True, slots=True)
class LineageNode:
    """One scenario in a lineage chain, flagged when its artifact is absent."""

    scenario_id: str
    artifact_type: str
    present: bool
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "artifact_type": self.artifact_type,
            "present": self.present,
            "unavailable_reason": self.unavailable_reason,
        }


def variant_lineage(
    record: ArtifactRecord,
    *,
    records: Sequence[ArtifactRecord] = (),
) -> dict[str, object]:
    """Return lineage, branch identity, seed, config hash and completeness."""
    by_id = {item.scenario.scenario_id: item for item in records}
    chain = _chain(record, by_id)
    root = chain[-1]
    branch_id = f"{BRANCH_ID_PREFIX}{root.scenario_id}"
    declared_branch = record.scenario.provenance.get("branch_name")
    children = sorted(
        item.scenario.scenario_id
        for item in records
        if item.parent_scenario_id == record.scenario.scenario_id
    )
    configuration = _configuration(record)
    seed, seed_reason = _seed(record)
    config_hash, config_hash_reason = _config_hash(record)
    run_id = record.scenario.provenance.get("run_id")
    provenance = dict(record.scenario.provenance)
    fields = {
        "parent_scenario_id": record.parent_scenario_id,
        "branch_id": branch_id,
        "branch_name": declared_branch,
        "seed": seed,
        "config_hash": config_hash,
        "run_id": run_id,
        "variant_configuration": configuration,
        "dataset_version": provenance.get("dataset_version"),
        "generator_version": provenance.get("generator_version"),
        "transform_version": provenance.get("coordinate_transform_version"),
        "source_scene_token": provenance.get("source_scene_token"),
    }
    reasons = {
        "parent_scenario_id": None
        if record.parent_scenario_id is not None
        else "artifact_is_a_root_baseline_document",
        "branch_id": None,
        "branch_name": None if declared_branch else REASON_NO_BRANCH_NAME,
        "seed": seed_reason,
        "config_hash": config_hash_reason,
        "run_id": None if run_id else REASON_NO_RUN_ID,
        "variant_configuration": None
        if configuration is not None
        else REASON_NO_VARIANT_CONFIG,
        "dataset_version": _missing(provenance, "dataset_version", "dataset_version"),
        "generator_version": _missing(provenance, "generator_version", "generator_version"),
        "transform_version": _missing(
            provenance, "coordinate_transform_version", "transform_version"
        ),
        "source_scene_token": _missing(provenance, "source_scene_token", "source_scene_token"),
    }
    return {
        "contract_version": VARIANT_LINEAGE_VERSION,
        "scenario_id": record.scenario.scenario_id,
        "artifact_type": record.artifact_type,
        "artifact_path": record.relative_path,
        "coordinate_frame": record.scenario.coordinate_frame,
        "lineage_path": [node.to_dict() for node in reversed(chain)],
        "lineage_depth": len(chain) - 1,
        "branch": {
            "branch_id": branch_id,
            "branch_name": declared_branch,
            "root_scenario_id": root.scenario_id,
            "branch_id_source": "lineage_root_scenario_id",
            "branch_name_source": "scenario_provenance" if declared_branch else None,
            "branch_name_unavailable_reason": None if declared_branch else REASON_NO_BRANCH_NAME,
        },
        "child_scenario_ids": children,
        "fields": fields,
        "unavailable_reasons": reasons,
        "provenance": {key: provenance[key] for key in PROVENANCE_KEYS if key in provenance},
        "artifact_visibility": "local_private",
    }


def config_hash(record: ArtifactRecord) -> str | None:
    """Expose the canonical configuration hash, or ``None`` when unavailable."""
    return _config_hash(record)[0]


def _chain(record: ArtifactRecord, by_id: Mapping[str, ArtifactRecord]) -> tuple[LineageNode, ...]:
    """Walk declared parents, flagging the first artifact that is absent."""
    chain = [
        LineageNode(
            scenario_id=record.scenario.scenario_id,
            artifact_type=record.artifact_type,
            present=True,
        )
    ]
    current = record
    while current.parent_scenario_id is not None and len(chain) < MAX_LINEAGE_DEPTH:
        parent = by_id.get(current.parent_scenario_id)
        if parent is None:
            chain.append(
                LineageNode(
                    scenario_id=current.parent_scenario_id,
                    artifact_type="unknown",
                    present=False,
                    unavailable_reason=REASON_PARENT_ARTIFACT_ABSENT,
                )
            )
            break
        chain.append(
            LineageNode(
                scenario_id=parent.scenario.scenario_id,
                artifact_type=parent.artifact_type,
                present=True,
            )
        )
        current = parent
    return tuple(chain)


def _missing(provenance: Mapping[str, str], key: str, field: str) -> str | None:
    """Name the reason a provenance field is absent instead of defaulting it."""
    if provenance.get(key) is not None:
        return None
    return f"scenario_provenance_declares_no_{field}"


def _configuration(record: ArtifactRecord) -> dict[str, object] | None:
    """Return the canonical variant configuration when the artifact declares one."""
    if record.variant_config is None:
        return None
    return {
        "speed_multiplier": record.variant_config.speed_multiplier,
        "initial_gap_delta_m": record.variant_config.initial_gap_delta_m,
        "timing_offset_s": record.variant_config.timing_offset_s,
        "seed": record.variant_config.seed,
    }


def _seed(record: ArtifactRecord) -> tuple[int | None, str | None]:
    if record.variant_config is None:
        return None, REASON_NO_VARIANT_CONFIG
    return record.variant_config.seed, None


def _config_hash(record: ArtifactRecord) -> tuple[str | None, str | None]:
    """Hash the declared variant configuration, naming what the hash covers."""
    configuration = _configuration(record)
    if configuration is None:
        return None, REASON_NO_VARIANT_CONFIG
    payload = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}", None