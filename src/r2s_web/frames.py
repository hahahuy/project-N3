"""Simulator-backed frame contracts for Workspace POV views."""

from __future__ import annotations

from typing import Literal

from real2scenario import Scenario, State

FRAME_CONTRACT_VERSION = "simulator-frame-v1"
INTERNAL_SIMULATOR_VERSION = "kinematic-open-loop-v1"


def capability(scenario: Scenario) -> dict[str, object]:
    available = bool(scenario.actors) and all(actor.trajectory for actor in scenario.actors)
    return {
        "available": available,
        "unavailable_reason": None if available else "time_indexed_actor_states_unavailable",
        "simulator": "internal-kinematic-preview",
        "version": INTERNAL_SIMULATOR_VERSION,
        "frame_contract": FRAME_CONTRACT_VERSION,
        "modes": ["third-person", "in-car"] if available else [],
        "rendering": "browser_transform_renderer" if available else None,
    }


def frame(scenario: Scenario, *, mode: Literal["third-person", "in-car"], time_s: float) -> dict[str, object]:
    states = {actor.actor_id: _state_at(actor.trajectory, time_s) for actor in scenario.actors if actor.trajectory}
    if not states:
        raise ValueError("time_indexed_actor_states_unavailable")
    ego = states.get(scenario.ego_actor_id) or next(iter(states.values()))
    return {
        "contract_version": FRAME_CONTRACT_VERSION,
        "frame_id": f"{scenario.scenario_id}:{mode}:{ego.time_s:.6f}",
        "mode": mode,
        "status": "rendered",
        "simulator": "internal-kinematic-preview",
        "simulator_version": INTERNAL_SIMULATOR_VERSION,
        "timestamp_s": ego.time_s,
        "coordinate_frame": scenario.coordinate_frame,
        "transform_version": scenario.provenance.get("coordinate_transform_version"),
        "camera_transform": {"x_m": ego.x_m, "y_m": ego.y_m, "z_m": 1.45 if mode == "in-car" else 2.8, "yaw_rad": ego.yaw_rad, "pitch_rad": 0.0 if mode == "in-car" else -0.12, "reference": "ego_mount" if mode == "in-car" else "ego_follow"},
        "actors": [{"actor_id": actor.actor_id, "actor_type": actor.actor_type, "transform": {"x_m": state.x_m, "y_m": state.y_m, "z_m": 0.0, "yaw_rad": state.yaw_rad}, "speed_mps": state.speed_mps, "dimensions": {"length_m": actor.length_m, "width_m": actor.width_m}} for actor in scenario.actors if (state := states.get(actor.actor_id)) is not None],
        "provenance": {"source": "canonical_scenario_states", "source_scene": scenario.provenance.get("source_scene", scenario.scenario_id), "dataset_version": scenario.provenance.get("dataset_version", "unknown"), "reference_point": scenario.provenance.get("reference_point", "center"), "artifact_visibility": "local_private"},
    }


def _state_at(trajectory: tuple[State, ...], time_s: float) -> State:
    if time_s <= trajectory[0].time_s:
        return trajectory[0]
    if time_s >= trajectory[-1].time_s:
        return trajectory[-1]
    for before, after in zip(trajectory, trajectory[1:]):
        if before.time_s <= time_s <= after.time_s:
            ratio = (time_s - before.time_s) / (after.time_s - before.time_s)
            return State(
                time_s=time_s,
                x_m=before.x_m + ratio * (after.x_m - before.x_m),
                y_m=before.y_m + ratio * (after.y_m - before.y_m),
                yaw_rad=before.yaw_rad + ratio * (after.yaw_rad - before.yaw_rad),
                speed_mps=before.speed_mps + ratio * (after.speed_mps - before.speed_mps),
            )
    return trajectory[-1]
