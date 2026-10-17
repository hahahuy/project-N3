"""Deterministic parameterized perturbations for canonical scenarios."""

from __future__ import annotations

import hashlib
import json
from math import cos, sin
from random import Random
from typing import Sequence
from dataclasses import dataclass

from .models import Actor, Scenario, State, VariantConfig
from .serialization import variant_config_to_dict


GENERATOR_VERSION = "parameterized-perturbation-v1"
BATCH_MANIFEST_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class BatchManifest:
    """Deterministic record of the variants produced for one parent scenario."""

    parent_scenario_id: str
    generator_version: str
    mode: str
    seed: int
    variant_ids: tuple[str, ...]
    configurations: tuple[VariantConfig, ...]

    def __post_init__(self) -> None:
        if not self.parent_scenario_id:
            raise ValueError("BatchManifest parent_scenario_id must not be empty.")
        if not self.generator_version:
            raise ValueError("BatchManifest generator_version must not be empty.")
        if self.mode not in {"grid", "random"}:
            raise ValueError("BatchManifest mode must be 'grid' or 'random'.")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("BatchManifest seed must be an integer.")
        if len(self.variant_ids) != len(self.configurations):
            raise ValueError("BatchManifest IDs and configurations must have equal lengths.")
        if len(set(self.variant_ids)) != len(self.variant_ids):
            raise ValueError("BatchManifest variant IDs must be unique.")


@dataclass(frozen=True, slots=True)
class ActorMotionEdit:
    """One actor-scoped, parameterized edit used by the U0 preview flow."""

    actor_id: str
    speed_multiplier: float = 1.0
    heading_offset_rad: float = 0.0
    initial_gap_delta_m: float = 0.0
    timing_offset_s: float = 0.0
    steering_angle_rad: float = 0.0
    acceleration_mps2: float | None = None
    braking_mps2: float | None = None
    target_speed_mps: float | None = None
    start_time_s: float = 0.0
    end_time_s: float | None = None

    def __post_init__(self) -> None:
        if not self.actor_id:
            raise ValueError("ActorMotionEdit actor_id must not be empty.")
        values = (self.speed_multiplier, self.heading_offset_rad, self.initial_gap_delta_m, self.timing_offset_s, self.steering_angle_rad, self.start_time_s)
        from math import isfinite
        if not all(isfinite(value) for value in values):
            raise ValueError("ActorMotionEdit values must be finite.")
        if self.speed_multiplier <= 0:
            raise ValueError("ActorMotionEdit speed_multiplier must be positive.")
        if self.acceleration_mps2 is not None and not isfinite(self.acceleration_mps2):
            raise ValueError("ActorMotionEdit acceleration_mps2 must be finite.")
        if self.braking_mps2 is not None and (not isfinite(self.braking_mps2) or self.braking_mps2 < 0):
            raise ValueError("ActorMotionEdit braking_mps2 must be finite and non-negative.")
        if self.target_speed_mps is not None and (not isfinite(self.target_speed_mps) or self.target_speed_mps < 0):
            raise ValueError("ActorMotionEdit target_speed_mps must be finite and non-negative.")
        if self.end_time_s is not None and self.end_time_s < self.start_time_s:
            raise ValueError("ActorMotionEdit end_time_s must not precede start_time_s.")


def preview_variant(
    scenario: Scenario,
    edits: Sequence[ActorMotionEdit],
    *,
    seed: int = 0,
    generator_version: str = GENERATOR_VERSION,
) -> Scenario:
    """Create a deterministic actor-scoped child without mutating its parent."""
    _validate_batch_seed(seed)
    if not edits:
        raise ValueError("At least one actor motion edit is required.")
    by_id = {edit.actor_id: edit for edit in edits}
    if len(by_id) != len(edits):
        raise ValueError("Actor motion edit actor IDs must be unique.")
    known = {actor.actor_id for actor in scenario.actors}
    unknown = sorted(set(by_id) - known)
    if unknown:
        raise ValueError(f"Unknown actor ID(s): {', '.join(unknown)}.")

    payload = {
        "generator_version": generator_version,
        "parent_scenario_id": scenario.scenario_id,
        "seed": seed,
        "actor_edits": [
            {"actor_id": actor_id, "speed_multiplier": edit.speed_multiplier,
             "heading_offset_rad": edit.heading_offset_rad,
             "initial_gap_delta_m": edit.initial_gap_delta_m,
             "timing_offset_s": edit.timing_offset_s}
            for actor_id, edit in sorted(by_id.items())
        ],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    variant_id = f"{scenario.scenario_id}--preview-{digest}"
    actors = tuple(_preview_actor(actor, by_id.get(actor.actor_id)) for actor in scenario.actors)
    duration_s = max(scenario.duration_s, max(state.time_s for actor in actors for state in actor.trajectory))
    provenance = dict(scenario.provenance)
    provenance.update({"parent_scenario_id": scenario.scenario_id, "generator_version": generator_version,
                       "preview_seed": str(seed), "preview_config_hash": hashlib.sha256(
                           json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
    return Scenario(variant_id, duration_s, scenario.ego_actor_id, actors, scenario.coordinate_frame, provenance)


def _preview_actor(actor: Actor, edit: ActorMotionEdit | None) -> Actor:
    if edit is None:
        return actor
    first = actor.trajectory[0]
    heading = edit.heading_offset_rad
    transformed = []
    for state in actor.trajectory:
        relative_x = (state.x_m - first.x_m) * cos(heading) - (state.y_m - first.y_m) * sin(heading)
        relative_y = (state.x_m - first.x_m) * sin(heading) + (state.y_m - first.y_m) * cos(heading)
        time_s = state.time_s + edit.timing_offset_s
        if time_s < 0:
            raise ValueError(f"timing_offset_s would create a negative timestamp for actor {actor.actor_id!r}.")
        maneuver_time = max(0.0, state.time_s - edit.start_time_s)
        active = edit.end_time_s is None or state.time_s <= edit.end_time_s
        acceleration = (edit.acceleration_mps2 or 0.0) - (edit.braking_mps2 or 0.0)
        speed = state.speed_mps * edit.speed_multiplier
        if active:
            speed += acceleration * maneuver_time
            if edit.target_speed_mps is not None:
                speed = edit.target_speed_mps
        # Do not clamp an infeasible maneuver. Tier 1 reports the violation.
        yaw_offset = heading + (edit.steering_angle_rad * maneuver_time if active else 0.0)
        transformed.append(State(time_s, first.x_m + relative_x * edit.speed_multiplier + edit.initial_gap_delta_m,
                                  first.y_m + relative_y * edit.speed_multiplier, state.yaw_rad + yaw_offset,
                                  speed, state.source_timestamp_us,
                                  state.source_record_token))
    return Actor(actor.actor_id, actor.actor_type, tuple(transformed), actor.length_m, actor.width_m, actor.height_m)


def generate_grid_variants(
    scenario: Scenario,
    *,
    speed_multipliers: Sequence[float],
    initial_gap_deltas_m: Sequence[float],
    timing_offsets_s: Sequence[float],
    seed: int = 0,
    generator_version: str = GENERATOR_VERSION,
) -> tuple[tuple[Scenario, ...], BatchManifest]:
    """Generate variants in stable Cartesian-product order."""
    _validate_batch_seed(seed)
    values = (
        tuple(speed_multipliers),
        tuple(initial_gap_deltas_m),
        tuple(timing_offsets_s),
    )
    if any(not items for items in values):
        raise ValueError("Grid parameter values must not be empty.")
    configurations = tuple(
        VariantConfig(
            speed_multiplier=speed_multiplier,
            initial_gap_delta_m=initial_gap_delta_m,
            timing_offset_s=timing_offset,
            seed=seed,
        )
        for speed_multiplier in values[0]
        for initial_gap_delta_m in values[1]
        for timing_offset in values[2]
    )
    return _generate_batch(scenario, configurations, "grid", seed, generator_version)


def generate_random_variants(
    scenario: Scenario,
    *,
    count: int,
    speed_multiplier_range: tuple[float, float],
    initial_gap_delta_range_m: tuple[float, float],
    timing_offset_range_s: tuple[float, float],
    seed: int = 0,
    generator_version: str = GENERATOR_VERSION,
) -> tuple[tuple[Scenario, ...], BatchManifest]:
    """Generate uniformly sampled variants using a private seeded RNG."""
    _validate_batch_seed(seed)
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("Random variant count must be a positive integer.")
    ranges = (
        speed_multiplier_range,
        initial_gap_delta_range_m,
        timing_offset_range_s,
    )
    for name, bounds in zip(
        ("speed_multiplier_range", "initial_gap_delta_range_m", "timing_offset_range_s"),
        ranges,
    ):
        _validate_range(name, bounds)
    if speed_multiplier_range[0] <= 0:
        raise ValueError("speed_multiplier_range must contain only positive values.")

    rng = Random(seed)
    configurations = tuple(
        VariantConfig(
            speed_multiplier=rng.uniform(*speed_multiplier_range),
            initial_gap_delta_m=rng.uniform(*initial_gap_delta_range_m),
            timing_offset_s=rng.uniform(*timing_offset_range_s),
            seed=rng.randrange(0, 2**63),
        )
        for _ in range(count)
    )
    return _generate_batch(scenario, configurations, "random", seed, generator_version)


def batch_manifest_to_dict(manifest: BatchManifest) -> dict[str, object]:
    """Convert a batch manifest to deterministic JSON-safe data."""
    return {
        "manifest_version": BATCH_MANIFEST_VERSION,
        "parent_scenario_id": manifest.parent_scenario_id,
        "generator_version": manifest.generator_version,
        "mode": manifest.mode,
        "seed": manifest.seed,
        "variants": [
            {
                "variant_id": variant_id,
                "variant_config": variant_config_to_dict(config),
            }
            for variant_id, config in zip(manifest.variant_ids, manifest.configurations)
        ],
    }


def batch_manifest_to_json(manifest: BatchManifest) -> str:
    """Serialize a batch manifest with stable key and list ordering."""
    return json.dumps(
        batch_manifest_to_dict(manifest),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def perturb_scenario(
    scenario: Scenario,
    config: VariantConfig,
    *,
    generator_version: str = GENERATOR_VERSION,
) -> Scenario:
    """Create one deterministic child scenario without mutating ``scenario``.

    Speed is changed for every actor by scaling longitudinal displacement from
    each actor's initial state and every state's speed. Initial gap is applied
    to non-ego actors along the ego actor's initial heading. Timing offset is
    applied to non-ego timestamps. A negative offset is rejected when it would
    create a negative timestamp.
    """
    if not generator_version:
        raise ValueError("generator_version must not be empty.")

    ego = next(actor for actor in scenario.actors if actor.actor_id == scenario.ego_actor_id)
    ego_heading = ego.trajectory[0].yaw_rad
    longitudinal_axis = (cos(ego_heading), sin(ego_heading))
    lateral_axis = (-sin(ego_heading), cos(ego_heading))

    actors = tuple(
        _perturb_actor(
            actor,
            scenario.ego_actor_id,
            config,
            longitudinal_axis,
            lateral_axis,
        )
        for actor in scenario.actors
    )
    duration_s = max(
        scenario.duration_s,
        max(state.time_s for actor in actors for state in actor.trajectory),
    )
    variant_id = _variant_id(scenario.scenario_id, config, generator_version)
    provenance = dict(scenario.provenance)
    provenance.update(
        {
            "parent_scenario_id": scenario.scenario_id,
            "generator_version": generator_version,
            "variant_speed_multiplier": _number(config.speed_multiplier),
            "variant_initial_gap_delta_m": _number(config.initial_gap_delta_m),
            "variant_timing_offset_s": _number(config.timing_offset_s),
            "variant_seed": str(config.seed),
        }
    )
    return Scenario(
        scenario_id=variant_id,
        duration_s=duration_s,
        ego_actor_id=scenario.ego_actor_id,
        actors=actors,
        coordinate_frame=scenario.coordinate_frame,
        provenance=provenance,
    )


def _generate_batch(
    scenario: Scenario,
    configurations: tuple[VariantConfig, ...],
    mode: str,
    seed: int,
    generator_version: str,
) -> tuple[tuple[Scenario, ...], BatchManifest]:
    variants = tuple(
        perturb_scenario(scenario, config, generator_version=generator_version)
        for config in configurations
    )
    manifest = BatchManifest(
        parent_scenario_id=scenario.scenario_id,
        generator_version=generator_version,
        mode=mode,
        seed=seed,
        variant_ids=tuple(variant.scenario_id for variant in variants),
        configurations=configurations,
    )
    return variants, manifest


def _validate_batch_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Batch seed must be an integer.")


def _validate_range(name: str, bounds: tuple[float, float]) -> None:
    if len(bounds) != 2 or bounds[0] > bounds[1]:
        raise ValueError(f"{name} must be an ordered (minimum, maximum) pair.")


def _perturb_actor(
    actor: Actor,
    ego_actor_id: str,
    config: VariantConfig,
    longitudinal_axis: tuple[float, float],
    lateral_axis: tuple[float, float],
) -> Actor:
    first = actor.trajectory[0]
    gap_x, gap_y = (0.0, 0.0)
    if actor.actor_id != ego_actor_id:
        gap_x = config.initial_gap_delta_m * longitudinal_axis[0]
        gap_y = config.initial_gap_delta_m * longitudinal_axis[1]

    transformed = tuple(
        _perturb_state(
            state,
            first,
            actor.actor_id != ego_actor_id,
            config,
            longitudinal_axis,
            lateral_axis,
            gap_x,
            gap_y,
            actor.actor_id,
        )
        for state in actor.trajectory
    )
    return Actor(
        actor_id=actor.actor_id,
        actor_type=actor.actor_type,
        trajectory=transformed,
        length_m=actor.length_m,
        width_m=actor.width_m,
        height_m=actor.height_m,
    )


def _perturb_state(
    state: State,
    first: State,
    is_non_ego: bool,
    config: VariantConfig,
    longitudinal_axis: tuple[float, float],
    lateral_axis: tuple[float, float],
    gap_x: float,
    gap_y: float,
    actor_id: str,
) -> State:
    relative_x = state.x_m - first.x_m
    relative_y = state.y_m - first.y_m
    longitudinal = relative_x * longitudinal_axis[0] + relative_y * longitudinal_axis[1]
    lateral = relative_x * lateral_axis[0] + relative_y * lateral_axis[1]
    scaled_longitudinal = longitudinal * config.speed_multiplier
    x_m = (
        first.x_m
        + scaled_longitudinal * longitudinal_axis[0]
        + lateral * lateral_axis[0]
        + gap_x
    )
    y_m = (
        first.y_m
        + scaled_longitudinal * longitudinal_axis[1]
        + lateral * lateral_axis[1]
        + gap_y
    )
    time_s = state.time_s + (config.timing_offset_s if is_non_ego else 0.0)
    if time_s < 0:
        raise ValueError(
            "timing_offset_s would create a negative timestamp for "
            f"actor {actor_id!r}."
        )
    return State(
        time_s=time_s,
        x_m=x_m,
        y_m=y_m,
        yaw_rad=state.yaw_rad,
        speed_mps=state.speed_mps * config.speed_multiplier,
    )


def _variant_id(parent_scenario_id: str, config: VariantConfig, generator_version: str) -> str:
    payload = json.dumps(
        {
            "generator_version": generator_version,
            "parent_scenario_id": parent_scenario_id,
            "variant_config": {
                "initial_gap_delta_m": config.initial_gap_delta_m,
                "seed": config.seed,
                "speed_multiplier": config.speed_multiplier,
                "timing_offset_s": config.timing_offset_s,
            },
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"{parent_scenario_id}--variant-{digest}"


def _number(value: float) -> str:
    return format(value, ".17g")
