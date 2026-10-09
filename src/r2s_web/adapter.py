"""Adapter between local artifacts and API view models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from real2scenario import (
    Actor,
    Scenario,
    VariantConfig,
    artifact_from_json,
    actor_to_dict,
    compute_scenario_replay_metrics,
    scenario_to_dict,
    state_to_dict,
)
from real2scenario.simulation import ReplayState, ReplayTrace

from .config import WebSettings
from .schemas import (
    ActorSummary,
    ArtifactLink,
    ReplayMetricView,
    ScenarioDetail,
    ScenarioSummary,
    TrajectoryPath,
    TrajectoryResponse,
    TrajectoryState,
)


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    scenario: Scenario
    path: Path
    relative_path: str
    artifact_type: str
    parent_scenario_id: str | None
    variant_config: VariantConfig | None


class ArtifactAdapter:
    """Discover and load strict canonical artifacts below one configured root."""

    def __init__(self, settings: WebSettings):
        self.settings = settings

    def discover(self) -> tuple[ArtifactRecord, ...]:
        if not self.settings.artifact_root.is_dir():
            return ()
        records: list[ArtifactRecord] = []
        for path in sorted(self.settings.artifact_root.rglob("*.json")):
            if path.name.endswith(".replay.json") or path.name in {
                "aggregate.json",
                "manifest.json",
            }:
                continue
            try:
                scenario, parent_id, config = artifact_from_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            records.append(
                ArtifactRecord(
                    scenario=scenario,
                    path=path,
                    relative_path=self.relative_path(path),
                    artifact_type="variant" if config is not None else "baseline",
                    parent_scenario_id=parent_id,
                    variant_config=config,
                )
            )
        return tuple(records)

    def get(self, scenario_id: str) -> ArtifactRecord:
        for record in self.discover():
            if record.scenario.scenario_id == scenario_id:
                return record
        raise KeyError(f"Scenario {scenario_id!r} was not found.")

    def relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.settings.project_root).as_posix()

    def resolve_artifact(self, relative_path: str) -> Path:
        candidate = (self.settings.project_root / relative_path).resolve()
        allowed_roots = (self.settings.artifact_root, self.settings.output_root)
        if not any(_is_relative_to(candidate, root) for root in allowed_roots):
            raise ValueError("Artifact path is outside the configured project roots.")
        if not candidate.is_file():
            raise FileNotFoundError(relative_path)
        return candidate

    def summary(self, record: ArtifactRecord) -> ScenarioSummary:
        return ScenarioSummary(
            scenario_id=record.scenario.scenario_id,
            parent_scenario_id=record.parent_scenario_id,
            artifact_type=record.artifact_type,
            duration_s=record.scenario.duration_s,
            coordinate_frame=record.scenario.coordinate_frame,
            actors=[_actor_summary(actor) for actor in record.scenario.actors],
            provenance=dict(record.scenario.provenance),
            available_artifacts=self.artifact_links(record),
        )

    def detail(self, record: ArtifactRecord) -> ScenarioDetail:
        summary = self.summary(record)
        return ScenarioDetail(
            **summary.model_dump(),
            variant_config=None
            if record.variant_config is None
            else {
                "speed_multiplier": record.variant_config.speed_multiplier,
                "initial_gap_delta_m": record.variant_config.initial_gap_delta_m,
                "timing_offset_s": record.variant_config.timing_offset_s,
                "seed": record.variant_config.seed,
            },
        )

    def artifact_links(self, record: ArtifactRecord) -> list[ArtifactLink]:
        links = [
            ArtifactLink(
                kind="canonical-json",
                path=record.relative_path,
                url=f"/api/artifacts/{record.relative_path}",
            )
        ]
        replay_path = record.path.with_name(f"{record.path.stem}.replay.json")
        if replay_path.is_file():
            relative = self.relative_path(replay_path)
            links.append(
                ArtifactLink(kind="replay-trace", path=relative, url=f"/api/artifacts/{relative}")
            )
        return links

    def trajectory(self, record: ArtifactRecord) -> TrajectoryResponse:
        return self.trajectory_for_scenario(
            record.scenario,
            record.path,
            path_kind="generated" if record.artifact_type == "variant" else "recorded",
        )

    def trajectory_for_scenario(
        self, scenario: Scenario, path: Path, *, path_kind: str = "recorded"
    ) -> TrajectoryResponse:
        paths = [
            TrajectoryPath(
                actor_id=actor.actor_id,
                actor_type=actor.actor_type,
                path_kind=path_kind,
                states=[TrajectoryState(**state_to_dict(state)) for state in actor.trajectory],
            )
            for actor in scenario.actors
        ]
        replay_metrics: dict[str, ReplayMetricView] = {}
        replay_path = path.with_name(f"{path.stem}.replay.json")
        if replay_path.is_file():
            replay_trace = _replay_trace_from_json(replay_path)
            for actor in scenario.actors:
                replay_states = replay_trace.states_for(actor.actor_id)
                paths.append(
                    TrajectoryPath(
                        actor_id=actor.actor_id,
                        actor_type=actor.actor_type,
                        path_kind="replayed",
                        states=[TrajectoryState(**state_to_dict(state)) for state in replay_states],
                    )
                )
            replay_metrics = {
                actor_id: ReplayMetricView(
                    sample_count=metrics.sample_count,
                    alignment_method=metrics.alignment_method,
                    position_rmse_m=metrics.position_rmse_m,
                    final_displacement_m=metrics.final_displacement_m,
                    heading_mae_rad=metrics.heading_mae_rad,
                    speed_mae_mps=metrics.speed_mae_mps,
                )
                for actor_id, metrics in compute_scenario_replay_metrics(scenario, replay_trace).items()
            }
        return TrajectoryResponse(
            scenario_id=scenario.scenario_id,
            coordinate_frame=scenario.coordinate_frame,
            duration_s=scenario.duration_s,
            map_warning="OpenDRIVE output uses a local template approximation; it is not lossless map conversion.",
            paths=paths,
            replay_metrics=replay_metrics,
        )


def _actor_summary(actor: Actor) -> ActorSummary:
    return ActorSummary(
        actor_id=actor.actor_id,
        actor_type=actor.actor_type,
        sample_count=len(actor.trajectory),
        length_m=actor.length_m,
        width_m=actor.width_m,
    )


def _replay_trace_from_json(path: Path) -> ReplayTrace:
    payload = json.loads(path.read_text(encoding="utf-8"))
    states = tuple(
        ReplayState(actor_id=item["actor_id"], state=__state_from_payload(item["state"]))
        for item in payload["states"]
    )
    return ReplayTrace(states=states)


def __state_from_payload(payload: dict[str, Any]):
    from real2scenario import State

    return State(**payload)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
