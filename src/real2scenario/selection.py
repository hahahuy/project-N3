"""Deterministically select interaction actors from a canonical scenario."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import hypot, isfinite

from .models import Actor, Scenario, State


SELECTION_CONFIG_VERSION = "interaction-selection-v1"


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    """Versioned thresholds and optional manual actor override.

    Automatic candidates qualify when either their minimum synchronized
    distance or constant-velocity TTC satisfies the respective threshold.
    ``manual_actor_ids`` preserves its supplied order and bypasses thresholds.
    """

    max_distance_m: float = 30.0
    max_ttc_s: float = 5.0
    max_actors: int = 3
    manual_actor_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.max_distance_m) or self.max_distance_m < 0:
            raise ValueError("Selection max_distance_m must be finite and non-negative.")
        if not isfinite(self.max_ttc_s) or self.max_ttc_s < 0:
            raise ValueError("Selection max_ttc_s must be finite and non-negative.")
        if self.max_actors < 1 or self.max_actors > 3:
            raise ValueError("Selection max_actors must be between 1 and 3.")
        if self.manual_actor_ids is not None:
            if not self.manual_actor_ids:
                raise ValueError("Selection manual_actor_ids must not be empty when provided.")
            if len(self.manual_actor_ids) > self.max_actors:
                raise ValueError("Selection manual_actor_ids exceeds max_actors.")
            if len(self.manual_actor_ids) != len(set(self.manual_actor_ids)):
                raise ValueError("Selection manual_actor_ids must be unique.")
            if any(not actor_id for actor_id in self.manual_actor_ids):
                raise ValueError("Selection manual_actor_ids must not contain empty IDs.")


def select_interaction_actors(scenario: Scenario, config: SelectionConfig = SelectionConfig()) -> Scenario:
    """Return a new scenario with ego plus selected interaction actors.

    The baseline scenario is never mutated. Automatic selection sorts qualifying
    candidates by minimum TTC, then minimum distance, then actor ID. This gives
    deterministic output even when candidate metrics tie.
    """
    actors_by_id = {actor.actor_id: actor for actor in scenario.actors}
    ego = actors_by_id[scenario.ego_actor_id]
    candidates = [actor for actor in scenario.actors if actor.actor_id != ego.actor_id]

    if config.manual_actor_ids is not None:
        selected = _manual_selection(actors_by_id, ego.actor_id, config)
        decisions = [
            {
                "actor_id": actor.actor_id,
                "decision": "selected",
                "reason": "manual_override",
            }
            if actor.actor_id in config.manual_actor_ids
            else {
                "actor_id": actor.actor_id,
                "decision": "rejected",
                "reason": "not_in_manual_override",
            }
            for actor in candidates
        ]
    else:
        evaluated = [_evaluate_candidate(ego, actor, config) for actor in candidates]
        qualifying = [entry for entry in evaluated if entry["decision"] == "selected"]
        qualifying.sort(key=_selection_sort_key)
        selected_ids = {entry["actor_id"] for entry in qualifying[: config.max_actors]}
        selected = [actors_by_id[entry["actor_id"]] for entry in qualifying[: config.max_actors]]
        decisions = []
        for entry in evaluated:
            if entry["actor_id"] not in selected_ids and entry["decision"] == "selected":
                entry = {**entry, "decision": "rejected", "reason": "max_actors_limit"}
            decisions.append(entry)

    provenance = dict(scenario.provenance)
    provenance.update(
        {
            "interaction_selection_version": SELECTION_CONFIG_VERSION,
            "interaction_selection_config": json.dumps(
                {
                    "manual_actor_ids": config.manual_actor_ids,
                    "max_actors": config.max_actors,
                    "max_distance_m": config.max_distance_m,
                    "max_ttc_s": config.max_ttc_s,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "interaction_selection_decisions": json.dumps(
                decisions, separators=(",", ":"), sort_keys=True
            ),
            "selected_actor_ids": ",".join(actor.actor_id for actor in selected),
        }
    )
    return Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=ego.actor_id,
        actors=(ego, *selected),
        coordinate_frame=scenario.coordinate_frame,
        provenance=provenance,
    )


def _manual_selection(
    actors_by_id: dict[str, Actor], ego_actor_id: str, config: SelectionConfig
) -> list[Actor]:
    assert config.manual_actor_ids is not None
    if ego_actor_id in config.manual_actor_ids:
        raise ValueError("Selection manual_actor_ids must not include the ego actor.")
    unknown = set(config.manual_actor_ids).difference(actors_by_id)
    if unknown:
        raise ValueError(
            f"Selection manual_actor_ids contains unknown actor(s): {', '.join(sorted(unknown))}."
        )
    return [actors_by_id[actor_id] for actor_id in config.manual_actor_ids]


def _evaluate_candidate(ego: Actor, candidate: Actor, config: SelectionConfig) -> dict[str, object]:
    ego_states = {state.time_s: state for state in ego.trajectory}
    candidate_states = {state.time_s: state for state in candidate.trajectory}
    common_times = sorted(set(ego_states).intersection(candidate_states))
    if not common_times:
        return {
            "actor_id": candidate.actor_id,
            "decision": "rejected",
            "reason": "no_synchronized_states",
            "minimum_distance_m": None,
            "minimum_ttc_s": None,
        }

    distances = [_distance(ego_states[time_s], candidate_states[time_s]) for time_s in common_times]
    ttcs = [_ttc(ego_states[time_s], candidate_states[time_s]) for time_s in common_times]
    minimum_distance_m = min(distances)
    minimum_ttc_s = min(ttcs)
    qualifies_distance = minimum_distance_m <= config.max_distance_m
    qualifies_ttc = minimum_ttc_s <= config.max_ttc_s
    if qualifies_distance or qualifies_ttc:
        reason = "distance_and_ttc" if qualifies_distance and qualifies_ttc else (
            "distance" if qualifies_distance else "ttc"
        )
        decision = "selected"
    else:
        decision = "rejected"
        reason = "outside_distance_and_ttc_thresholds"
    return {
        "actor_id": candidate.actor_id,
        "decision": decision,
        "reason": reason,
        "minimum_distance_m": minimum_distance_m,
        "minimum_ttc_s": minimum_ttc_s if isfinite(minimum_ttc_s) else None,
    }


def _selection_sort_key(entry: dict[str, object]) -> tuple[float, float, str]:
    minimum_ttc_s = entry["minimum_ttc_s"]
    minimum_distance_m = entry["minimum_distance_m"]
    actor_id = entry["actor_id"]
    return (
        float("inf") if minimum_ttc_s is None else float(minimum_ttc_s),
        float("inf") if minimum_distance_m is None else float(minimum_distance_m),
        str(actor_id),
    )


def _distance(ego: State, candidate: State) -> float:
    return hypot(candidate.x_m - ego.x_m, candidate.y_m - ego.y_m)


def _ttc(ego: State, candidate: State) -> float:
    delta_x_m = candidate.x_m - ego.x_m
    delta_y_m = candidate.y_m - ego.y_m
    distance_m = hypot(delta_x_m, delta_y_m)
    if distance_m == 0:
        return 0.0
    ego_velocity = (ego.speed_mps * _cos(ego.yaw_rad), ego.speed_mps * _sin(ego.yaw_rad))
    actor_velocity = (
        candidate.speed_mps * _cos(candidate.yaw_rad),
        candidate.speed_mps * _sin(candidate.yaw_rad),
    )
    relative_velocity_x = actor_velocity[0] - ego_velocity[0]
    relative_velocity_y = actor_velocity[1] - ego_velocity[1]
    closing_speed_mps = -(
        delta_x_m * relative_velocity_x + delta_y_m * relative_velocity_y
    ) / distance_m
    return distance_m / closing_speed_mps if closing_speed_mps > 0 else float("inf")


def _sin(angle_rad: float) -> float:
    from math import sin

    return sin(angle_rad)


def _cos(angle_rad: float) -> float:
    from math import cos

    return cos(angle_rad)
