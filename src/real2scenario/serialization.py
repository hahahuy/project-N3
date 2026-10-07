"""Versioned JSON artifacts for canonical Real2Scenario models.

The functions in this module are intentionally limited to standard-library JSON
types. Simulator-specific artifacts belong to their respective adapters.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from math import isfinite
from typing import Any

from .models import Actor, Scenario, State, VariantConfig


SCHEMA_VERSION = "1.0"
REQUIRED_PROVENANCE_KEYS = frozenset(
    {
        "dataset_name",
        "dataset_version",
        "source_scene_token",
        "source_window",
        "coordinate_transform_version",
        "map_reconstruction_mode",
        "map_reconstruction_version",
        "generator_version",
    }
)

_STATE_FIELDS = frozenset({"time_s", "x_m", "y_m", "yaw_rad", "speed_mps"})
_ACTOR_FIELDS = frozenset(
    {"actor_id", "actor_type", "trajectory", "length_m", "width_m"}
)
_SCENARIO_FIELDS = frozenset(
    {
        "scenario_id",
        "duration_s",
        "ego_actor_id",
        "actors",
        "coordinate_frame",
        "provenance",
    }
)
_VARIANT_CONFIG_FIELDS = frozenset(
    {"speed_multiplier", "initial_gap_delta_m", "timing_offset_s", "seed"}
)
_BASELINE_ARTIFACT_FIELDS = frozenset({"schema_version", "artifact_type", "scenario"})
_VARIANT_ARTIFACT_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_type",
        "parent_scenario_id",
        "scenario",
        "variant_config",
    }
)


def state_to_dict(state: State) -> dict[str, float]:
    """Convert a state to JSON-safe SI-unit values."""
    return {
        "time_s": float(state.time_s),
        "x_m": float(state.x_m),
        "y_m": float(state.y_m),
        "yaw_rad": float(state.yaw_rad),
        "speed_mps": float(state.speed_mps),
    }


def state_from_dict(payload: Mapping[str, Any]) -> State:
    """Reconstruct a validated state from its JSON object."""
    data = _expect_object(payload, "state")
    _validate_fields(data, _STATE_FIELDS, "state")
    return State(**{field: _expect_number(data[field], f"state.{field}") for field in _STATE_FIELDS})


def actor_to_dict(actor: Actor) -> dict[str, Any]:
    """Convert an actor and its ordered trajectory to JSON-safe values."""
    return {
        "actor_id": actor.actor_id,
        "actor_type": actor.actor_type,
        "trajectory": [state_to_dict(state) for state in actor.trajectory],
        "length_m": None if actor.length_m is None else float(actor.length_m),
        "width_m": None if actor.width_m is None else float(actor.width_m),
    }


def actor_from_dict(payload: Mapping[str, Any]) -> Actor:
    """Reconstruct a validated actor from its JSON object."""
    data = _expect_object(payload, "actor")
    _validate_fields(data, _ACTOR_FIELDS, "actor")
    trajectory = data["trajectory"]
    if not isinstance(trajectory, list):
        raise ValueError("actor.trajectory must be a JSON array.")
    return Actor(
        actor_id=_expect_nonempty_string(data["actor_id"], "actor.actor_id"),
        actor_type=_expect_nonempty_string(data["actor_type"], "actor.actor_type"),
        trajectory=tuple(state_from_dict(item) for item in trajectory),
        length_m=_expect_optional_number(data["length_m"], "actor.length_m"),
        width_m=_expect_optional_number(data["width_m"], "actor.width_m"),
    )


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    """Convert a canonical scenario to a JSON-safe dictionary."""
    return {
        "scenario_id": scenario.scenario_id,
        "duration_s": float(scenario.duration_s),
        "ego_actor_id": scenario.ego_actor_id,
        "actors": [actor_to_dict(actor) for actor in scenario.actors],
        "coordinate_frame": scenario.coordinate_frame,
        "provenance": _provenance_to_dict(scenario.provenance),
    }


def scenario_from_dict(payload: Mapping[str, Any]) -> Scenario:
    """Reconstruct a canonical scenario and run its model invariants."""
    data = _expect_object(payload, "scenario")
    _validate_fields(data, _SCENARIO_FIELDS, "scenario")
    actors = data["actors"]
    if not isinstance(actors, list):
        raise ValueError("scenario.actors must be a JSON array.")
    return Scenario(
        scenario_id=_expect_nonempty_string(data["scenario_id"], "scenario.scenario_id"),
        duration_s=_expect_number(data["duration_s"], "scenario.duration_s"),
        ego_actor_id=_expect_nonempty_string(data["ego_actor_id"], "scenario.ego_actor_id"),
        actors=tuple(actor_from_dict(item) for item in actors),
        coordinate_frame=_expect_nonempty_string(
            data["coordinate_frame"], "scenario.coordinate_frame"
        ),
        provenance=_provenance_from_dict(data["provenance"]),
    )


def variant_config_to_dict(config: VariantConfig) -> dict[str, float | int]:
    """Convert replayable variant parameters to a JSON-safe dictionary."""
    if isinstance(config.seed, bool) or not isinstance(config.seed, int):
        raise ValueError("variant_config.seed must be an integer.")
    return {
        "speed_multiplier": float(config.speed_multiplier),
        "initial_gap_delta_m": float(config.initial_gap_delta_m),
        "timing_offset_s": float(config.timing_offset_s),
        "seed": config.seed,
    }


def variant_config_from_dict(payload: Mapping[str, Any]) -> VariantConfig:
    """Reconstruct a validated variant configuration from its JSON object."""
    data = _expect_object(payload, "variant_config")
    _validate_fields(data, _VARIANT_CONFIG_FIELDS, "variant_config")
    seed = data["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("variant_config.seed must be an integer.")
    return VariantConfig(
        speed_multiplier=_expect_number(
            data["speed_multiplier"], "variant_config.speed_multiplier"
        ),
        initial_gap_delta_m=_expect_number(
            data["initial_gap_delta_m"], "variant_config.initial_gap_delta_m"
        ),
        timing_offset_s=_expect_number(
            data["timing_offset_s"], "variant_config.timing_offset_s"
        ),
        seed=seed,
    )


def baseline_artifact_to_dict(scenario: Scenario) -> dict[str, Any]:
    """Create a versioned baseline artifact with complete provenance."""
    _validate_artifact_provenance(scenario.provenance)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "baseline",
        "scenario": scenario_to_dict(scenario),
    }


def variant_artifact_to_dict(
    scenario: Scenario, parent_scenario_id: str, config: VariantConfig
) -> dict[str, Any]:
    """Create a versioned variant artifact with its parent and configuration."""
    _validate_artifact_provenance(scenario.provenance)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "variant",
        "parent_scenario_id": _expect_nonempty_string(
            parent_scenario_id, "parent_scenario_id"
        ),
        "scenario": scenario_to_dict(scenario),
        "variant_config": variant_config_to_dict(config),
    }


def artifact_from_dict(
    payload: Mapping[str, Any],
) -> tuple[Scenario, str | None, VariantConfig | None]:
    """Read a baseline or variant artifact into canonical objects.

    Returns ``(scenario, parent_scenario_id, variant_config)``. Baseline
    artifacts return ``None`` for the final two values.
    """
    data = _expect_object(payload, "artifact")
    artifact_type = data.get("artifact_type")
    if artifact_type == "baseline":
        _validate_fields(data, _BASELINE_ARTIFACT_FIELDS, "baseline artifact")
    elif artifact_type == "variant":
        _validate_fields(data, _VARIANT_ARTIFACT_FIELDS, "variant artifact")
    else:
        raise ValueError("artifact.artifact_type must be 'baseline' or 'variant'.")

    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported artifact schema_version {data['schema_version']!r}; "
            f"expected {SCHEMA_VERSION!r}."
        )

    scenario = scenario_from_dict(data["scenario"])
    _validate_artifact_provenance(scenario.provenance)
    if artifact_type == "baseline":
        return scenario, None, None

    return (
        scenario,
        _expect_nonempty_string(data["parent_scenario_id"], "parent_scenario_id"),
        variant_config_from_dict(data["variant_config"]),
    )


def artifact_to_json(payload: Mapping[str, Any]) -> str:
    """Validate an artifact and return deterministic compact JSON."""
    scenario, parent_scenario_id, config = artifact_from_dict(payload)
    normalized = (
        baseline_artifact_to_dict(scenario)
        if config is None
        else variant_artifact_to_dict(scenario, parent_scenario_id or "", config)
    )
    return json.dumps(normalized, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def artifact_from_json(payload: str) -> tuple[Scenario, str | None, VariantConfig | None]:
    """Parse a JSON artifact and reconstruct its canonical objects."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"Artifact is not valid JSON: {error.msg}.") from error
    return artifact_from_dict(data)


def _expect_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a JSON object.")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path} keys must be strings.")
    return dict(value)


def _validate_fields(data: Mapping[str, Any], expected: frozenset[str], path: str) -> None:
    missing = expected.difference(data)
    unknown = set(data).difference(expected)
    if missing:
        raise ValueError(f"{path} is missing required field(s): {', '.join(sorted(missing))}.")
    if unknown:
        raise ValueError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}.")


def _expect_nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string.")
    return value


def _expect_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{path} must be a finite number.")
    return float(value)


def _expect_optional_number(value: Any, path: str) -> float | None:
    return None if value is None else _expect_number(value, path)


def _provenance_to_dict(provenance: Mapping[str, str]) -> dict[str, str]:
    return _provenance_from_dict(provenance)


def _provenance_from_dict(value: Any) -> dict[str, str]:
    data = _expect_object(value, "scenario.provenance")
    for key, item in data.items():
        _expect_nonempty_string(key, "scenario.provenance key")
        _expect_nonempty_string(item, f"scenario.provenance.{key}")
    return data


def _validate_artifact_provenance(provenance: Mapping[str, str]) -> None:
    data = _provenance_from_dict(provenance)
    missing = REQUIRED_PROVENANCE_KEYS.difference(data)
    if missing:
        raise ValueError(
            "artifact provenance is missing required field(s): "
            f"{', '.join(sorted(missing))}."
        )
