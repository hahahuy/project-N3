"""Local nuScenes scene discovery and canonical artifact import."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from real2scenario import (
    RoadAlignedTransform,
    SelectionConfig,
    SourceWindow,
    artifact_to_json,
    baseline_artifact_to_dict,
    extract_scenario,
    select_interaction_actors,
    transform_to_local_road_aligned,
)

from .config import WebSettings
from .schemas import ActorSummary, ArtifactLink, ScenarioSummary, SourceScene, SourceSceneImportResponse


class SourceSceneAdapter:
    """Read the local dataset metadata without importing the nuScenes devkit."""

    def __init__(self, settings: WebSettings):
        self.settings = settings

    def discover(self) -> tuple[SourceScene, ...]:
        metadata = self._metadata_path()
        if metadata is None:
            return ()
        scenes = _read_json_array(metadata / "scene.json")
        samples = {
            item["token"]: item for item in _read_json_array(metadata / "sample.json")
        }
        annotations = _read_json_array(metadata / "sample_annotation.json")
        instances = {
            item["token"]: item for item in _read_json_array(metadata / "instance.json")
        }
        categories = {
            item["token"]: item.get("name", "")
            for item in _read_json_array(metadata / "category.json")
        }
        result: list[SourceScene] = []
        for scene in scenes:
            sample_tokens = _scene_sample_tokens(scene, samples)
            observed_instances = {
                item["instance_token"]
                for item in annotations
                if item.get("sample_token") in sample_tokens
            }
            vehicle_tokens = tuple(
                token
                for token in sorted(observed_instances)
                if categories.get(instances.get(token, {}).get("category_token", ""), "").startswith(
                    "vehicle."
                )
            )
            result.append(
                SourceScene(
                    scene_token=scene["token"],
                    name=scene.get("name", scene["token"]),
                    description=scene.get("description", ""),
                    sample_count=len(sample_tokens),
                    first_sample_token=scene["first_sample_token"],
                    last_sample_token=scene["last_sample_token"],
                    vehicle_candidate_count=len(vehicle_tokens),
                )
            )
        return tuple(result)

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
        scene = next((item for item in self.discover() if item.scene_token == scene_token), None)
        if scene is None:
            raise KeyError(f"Source scene {scene_token!r} was not found.")
        if self.settings.dataset_root is None:
            raise ValueError("No local nuScenes dataset is configured.")
        metadata = self._metadata_path()
        if metadata is None:
            raise ValueError("Configured nuScenes metadata directory does not exist.")
        samples = {
            item["token"]: item for item in _read_json_array(metadata / "sample.json")
        }
        annotations = _read_json_array(metadata / "sample_annotation.json")
        instances = {
            item["token"]: item for item in _read_json_array(metadata / "instance.json")
        }
        categories = {
            item["token"]: item.get("name", "")
            for item in _read_json_array(metadata / "category.json")
        }
        sample_tokens = set(
            _scene_sample_tokens(
                {
                    "first_sample_token": scene.first_sample_token,
                    "last_sample_token": scene.last_sample_token,
                    "token": scene.scene_token,
                },
                samples,
            )
        )
        vehicle_tokens = tuple(
            token
            for token in sorted(
                {
                    item["instance_token"]
                    for item in annotations
                    if item.get("sample_token") in sample_tokens
                }
            )
            if categories.get(instances.get(token, {}).get("category_token", ""), "").startswith(
                "vehicle."
            )
        )
        window = SourceWindow(
            scene.scene_token,
            start_sample_token or scene.first_sample_token,
            end_sample_token or scene.last_sample_token,
        )
        source = extract_scenario(
            self.settings.dataset_root,
            window,
            vehicle_tokens,
            version=self.settings.dataset_version,
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
            scene=SourceScene(
                scene_token=scene.scene_token,
                name=scene.name,
                description=scene.description,
                sample_count=scene.sample_count,
                first_sample_token=scene.first_sample_token,
                last_sample_token=scene.last_sample_token,
                vehicle_candidate_count=scene.vehicle_candidate_count,
            ),
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
        return path if path.is_dir() else None


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read dataset metadata {path}: {error}.") from error
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"Dataset metadata {path} must contain a JSON array of objects.")
    return payload


def _scene_sample_tokens(scene: dict[str, Any], samples: dict[str, dict[str, Any]]) -> list[str]:
    tokens: list[str] = []
    current = scene["first_sample_token"]
    while current:
        sample = samples[current]
        tokens.append(current)
        if current == scene["last_sample_token"]:
            return tokens
        current = sample.get("next", "")
    raise ValueError(f"Scene {scene.get('token', '')!r} does not reach its last sample.")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "scene"
