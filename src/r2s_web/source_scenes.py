"""Local nuScenes scene discovery and canonical artifact import."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any

from real2scenario import (
    MetadataIndex,
    RoadAlignedTransform,
    SelectionConfig,
    SourceWindow,
    artifact_to_json,
    baseline_artifact_to_dict,
    default_cache_dir,
    extract_scenario,
    select_interaction_actors,
    transform_to_local_road_aligned,
)

from .config import WebSettings
from .schemas import ActorSummary, ArtifactLink, ScenarioSummary, SourceScene, SourceSceneImportResponse


_INDEX_CACHE: dict[tuple[str, str, str], MetadataIndex] = {}
_INDEX_CACHE_LOCK = threading.RLock()


def metadata_cache_dir() -> Path:
    """Return the local metadata cache directory for scene import."""
    configured = os.environ.get("R2S_METADATA_CACHE")
    return Path(configured).expanduser() if configured else default_cache_dir()


def shared_metadata_index(settings: WebSettings) -> MetadataIndex:
    """Return a process-shared metadata index for the configured dataset.

    Scene discovery and import previously rescanned the large nuScenes
    metadata tables on every call. The index streams them once into a local
    private cache and is reused for the remaining calls in this process.
    """
    if settings.dataset_root is None:
        raise ValueError("No local nuScenes dataset is configured.")
    cache_dir = metadata_cache_dir()
    key = (str(Path(settings.dataset_root).resolve()), settings.dataset_version, str(cache_dir))
    with _INDEX_CACHE_LOCK:
        index = _INDEX_CACHE.get(key)
        if index is None:
            index = MetadataIndex(settings.dataset_root, settings.dataset_version, cache_dir=cache_dir)
            _INDEX_CACHE[key] = index
        return index


class SourceSceneAdapter:
    """Read the local dataset metadata without importing the nuScenes devkit."""

    def __init__(self, settings: WebSettings):
        self.settings = settings

    def discover(self) -> tuple[SourceScene, ...]:
        if self._metadata_path() is None:
            return ()
        index = shared_metadata_index(self.settings)
        return tuple(_source_scene(index, record) for record in index.scene_records())

    def import_scene(
        self,
        scene_token: str,
        *,
        start_sample_token: str | None = None,
        end_sample_token: str | None = None,
        max_distance_m: float = 30.0,
        max_ttc_s: float = 5.0,
        max_actors: int = 3,
    ) -> SourceSceneImportResponse:
        if self._metadata_path() is None:
            raise ValueError("Configured nuScenes metadata directory does not exist.")
        index = shared_metadata_index(self.settings)
        try:
            record = index.scene(scene_token)
        except KeyError:
            record = None
        if record is None:
            raise KeyError(f"Source scene {scene_token!r} was not found.")
        scene = _source_scene(index, record)
        vehicle_tokens = index.instance_tokens(scene_token)
        window = SourceWindow(
            scene_token,
            start_sample_token or scene.first_sample_token,
            end_sample_token or scene.last_sample_token,
        )
        source = extract_scenario(
            self.settings.dataset_root,
            window,
            vehicle_tokens,
            version=self.settings.dataset_version,
            tables=index.tables_for_scenes([scene_token]),
        )
        selected = select_interaction_actors(
            source,
            SelectionConfig(
                max_distance_m=max_distance_m,
                max_ttc_s=max_ttc_s,
                max_actors=max_actors,
            ),
        )
        if len(selected.actors) < 2:
            raise ValueError(
                "No vehicle interaction actors matched the configured distance/TTC thresholds."
            )
        ego_start = next(
            actor for actor in selected.actors if actor.actor_id == selected.ego_actor_id
        ).trajectory[0]
        local = transform_to_local_road_aligned(
            selected,
            RoadAlignedTransform(
                origin_x_m=ego_start.x_m,
                origin_y_m=ego_start.y_m,
                heading_rad=ego_start.yaw_rad,
            ),
        )
        output_path = self.settings.artifact_root / "nuscenes" / f"{_slug(scene.name)}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            artifact_to_json(baseline_artifact_to_dict(local)), encoding="utf-8"
        )
        return SourceSceneImportResponse(
            scene=scene,
            scenario_id=local.scenario_id,
            selected_actor_ids=[actor.actor_id for actor in local.actors if actor.actor_id != "ego"],
            artifact=ArtifactLink(
                kind="canonical-json",
                path=output_path.resolve().relative_to(self.settings.project_root).as_posix(),
                url=f"/api/artifacts/{output_path.resolve().relative_to(self.settings.project_root).as_posix()}",
            ),
            scenario=ScenarioSummary(
                scenario_id=local.scenario_id,
                parent_scenario_id=None,
                artifact_type="baseline",
                duration_s=local.duration_s,
                coordinate_frame=local.coordinate_frame,
                actors=[
                    ActorSummary(
                        actor_id=actor.actor_id,
                        actor_type=actor.actor_type,
                        sample_count=len(actor.trajectory),
                        length_m=actor.length_m,
                        width_m=actor.width_m,
                    )
                    for actor in local.actors
                ],
                provenance=dict(local.provenance),
                available_artifacts=[],
            ),
        )

    def _metadata_path(self) -> Path | None:
        if self.settings.dataset_root is None:
            return None
        path = self.settings.dataset_root / self.settings.dataset_version
        # A mounted release directory can exist while its metadata tables are
        # incomplete. Treat that state as unavailable so settings/health remain
        # fail-closed instead of surfacing a 500 from MetadataIndex.
        return path if (path / "scene.json").is_file() else None


def _source_scene(index: MetadataIndex, record: dict[str, Any]) -> SourceScene:
    scene_token = str(record.get("token", ""))
    return SourceScene(
        scene_token=scene_token,
        name=str(record.get("name", scene_token)),
        description=str(record.get("description", "")),
        sample_count=len(index.sample_tokens(scene_token)),
        first_sample_token=str(record["first_sample_token"]),
        last_sample_token=str(record["last_sample_token"]),
        vehicle_candidate_count=len(index.instance_tokens(scene_token)),
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "scene"
