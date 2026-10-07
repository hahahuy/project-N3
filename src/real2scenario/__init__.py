"""Canonical models and pipeline components for Real2Scenario."""

from .models import Actor, Scenario, State, VariantConfig
from .ingestion import SourceWindow, extract_scenario
from .serialization import (
    REQUIRED_PROVENANCE_KEYS,
    SCHEMA_VERSION,
    actor_from_dict,
    actor_to_dict,
    artifact_from_dict,
    artifact_from_json,
    artifact_to_json,
    baseline_artifact_to_dict,
    scenario_from_dict,
    scenario_to_dict,
    state_from_dict,
    state_to_dict,
    variant_artifact_to_dict,
    variant_config_from_dict,
    variant_config_to_dict,
)

__all__ = [
    "Actor",
    "REQUIRED_PROVENANCE_KEYS",
    "SCHEMA_VERSION",
    "Scenario",
    "SourceWindow",
    "State",
    "VariantConfig",
    "actor_from_dict",
    "actor_to_dict",
    "artifact_from_dict",
    "artifact_from_json",
    "artifact_to_json",
    "baseline_artifact_to_dict",
    "extract_scenario",
    "scenario_from_dict",
    "scenario_to_dict",
    "state_from_dict",
    "state_to_dict",
    "variant_artifact_to_dict",
    "variant_config_from_dict",
    "variant_config_to_dict",
]
