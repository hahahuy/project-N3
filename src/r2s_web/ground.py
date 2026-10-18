"""Survey-grade ground layers (sidewalk, crossing context) for the WASM preview.

Renders nuScenes map-expansion polygons for a scenario's actor bounding box
and returns them already moved into the scenario's local road-aligned frame,
so the browser draws them with the same transform as the replay trajectories.
Display-only: nothing here feeds metrics, gates or reports.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import threading
from collections import OrderedDict
from pathlib import Path

from real2scenario import RoadAlignedTransform, Scenario, State

from .config import WebSettings
from .source_scenes import metadata_cache_dir, resolve_scene_map_name


logger = logging.getLogger(__name__)

GROUND_CONTRACT_VERSION = "ground-layers-v1"
GROUND_LAYERS = ("drivable_area", "walkway", "ped_crossing", "carpark_area")
GROUND_MARGIN_M = 40.0

FULL_MAP_CONTRACT_VERSION = "ground-full-map-v1"
# Hot-map entries kept in memory in front of the on-disk artifact. The previous
# cache was an unbounded dict keyed by (map, transform), which grew for the
# lifetime of the process and duplicated the whole map per API worker.
_FULL_MAP_LRU_ENTRIES = 4


class GroundService:
    """Serve local-frame map polygons for one recorded scenario."""

    def __init__(self, settings: WebSettings):
        self._settings = settings
        self._full_cache: OrderedDict[tuple[str, str, str, str], dict[str, object]] = OrderedDict()
        self._full_cache_lock = threading.Lock()
        self._build_locks: dict[tuple[str, str, str, str], threading.Lock] = {}

    def full_layers(self, scenario: Scenario) -> dict[str, object]:
        """Return full-scene map geometry transformed once into local coordinates."""
        provenance = scenario.provenance
        transform = RoadAlignedTransform.from_provenance(provenance)
        map_name = resolve_scene_map_name(provenance["source_scene_token"], self._settings)
        signature = self._dataset_signature(map_name)
        key = (map_name, str(transform.origin_x_m), str(transform.origin_y_m), f"{transform.heading_rad}:{signature}")
        with self._full_cache_lock:
            cached = self._full_cache.get(key)
            if cached is not None:
                self._full_cache.move_to_end(key)
                return cached

        # One builder per key, so a burst of requests for the same map waits for
        # a single build instead of each paying the full extraction cost.
        with self._full_cache_lock:
            build_lock = self._build_locks.setdefault(key, threading.Lock())

        with build_lock:
            with self._full_cache_lock:
                cached = self._full_cache.get(key)
                if cached is not None:
                    self._full_cache.move_to_end(key)
                    return cached
            artifact = self._read_artifact(map_name, transform, signature)
            if artifact is None:
                artifact = self._build_full_layers(scenario, map_name, transform)
                self._write_artifact(map_name, transform, signature, artifact)

        with self._full_cache_lock:
            self._full_cache[key] = artifact
            self._full_cache.move_to_end(key)
            while len(self._full_cache) > _FULL_MAP_LRU_ENTRIES:
                self._full_cache.popitem(last=False)
        return artifact

    def _dataset_signature(self, map_name: str) -> str:
        """Fingerprint the map source so stale artifacts regenerate, never reuse.

        Geometry comes from the devkit's ``map/`` expansion files rather than the
        metadata tables, so those files are the true dependency. A missing map
        directory yields a stable sentinel instead of an exception; the build
        below fails loudly on its own if the dataset is genuinely unusable.
        """
        if self._settings.dataset_root is None:
            return "no-dataset"
        # nuScenes ships map-expansion JSON under "maps/" (plural), next to
        # samples/ and sweeps/. Hashing a missing directory would collapse to
        # the empty-string digest and silently disable invalidation.
        map_root = Path(self._settings.dataset_root) / "maps"
        digest = hashlib.sha256()
        try:
            for path in sorted(map_root.rglob("*")):
                if path.is_file():
                    stat = path.stat()
                    digest.update(f"{path.relative_to(map_root)}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
        except OSError:
            return "unreadable"
        if not digest.hexdigest() or digest.hexdigest() == hashlib.sha256().hexdigest():
            return "missing-map-expansion"
        return digest.hexdigest()[:16]

    def _artifact_path(self, map_name: str, transform: RoadAlignedTransform, signature: str) -> Path:
        """Locate the versioned compressed artifact for one map and transform."""
        transform_hash = hashlib.sha256(
            f"{transform.origin_x_m:.6f}|{transform.origin_y_m:.6f}|{transform.heading_rad:.9f}".encode()
        ).hexdigest()[:16]
        version = self._settings.dataset_version or "unknown"
        return (
            metadata_cache_dir()
            / "map-cache"
            / f"map-{version}-{map_name}-{transform_hash}-{signature}-full-map-v1.json.gz"
        )

    def _read_artifact(
        self, map_name: str, transform: RoadAlignedTransform, signature: str
    ) -> dict[str, object] | None:
        path = self._artifact_path(map_name, transform, signature)
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, EOFError):
            return None
        # The signature is in the filename, so a match already implies the right
        # dataset. Re-check the recorded provenance too: a renamed or hand-edited
        # artifact must not be trusted.
        if not isinstance(payload, dict):
            return None
        if payload.get("contract_version") != FULL_MAP_CONTRACT_VERSION:
            return None
        if payload.get("map_name") != map_name or payload.get("source_signature") != signature:
            return None
        if not isinstance(payload.get("layers"), dict):
            return None
        # Artifact provenance is bookkeeping for the cache, not part of the
        # preview contract. Strip it so a cache hit returns exactly what a cold
        # build returns; otherwise the response silently changes shape the
        # first time a restart reuses the artifact.
        payload.pop("source_signature", None)
        payload.pop("transform_provenance", None)
        return payload

    def _write_artifact(
        self,
        map_name: str,
        transform: RoadAlignedTransform,
        signature: str,
        artifact: dict[str, object],
    ) -> None:
        path = self._artifact_path(map_name, transform, signature)
        payload = dict(artifact)
        payload["source_signature"] = signature
        payload["transform_provenance"] = {
            "origin_x_m": transform.origin_x_m,
            "origin_y_m": transform.origin_y_m,
            "heading_rad": transform.heading_rad,
        }
        temp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write to a temp file in the same directory, then replace, so a
            # reader never observes a partially written artifact.
            with gzip.open(temp, "wt", encoding="utf-8") as handle:
                json.dump(payload, handle)
            os.replace(temp, path)
        except OSError as error:
            # A read-only or full cache volume must not break the preview, but
            # it must not fail silently either: the next restart pays the full
            # build again. Surface it once per miss.
            logger.warning("full-map artifact not persisted for %s: %s", map_name, error)
            try:
                temp.unlink()
            except OSError:
                pass

    def _build_full_layers(
        self, scenario: Scenario, map_name: str, transform: RoadAlignedTransform
    ) -> dict[str, object]:
        if self._settings.dataset_root is None:
            raise ValueError("No local nuScenes dataset is configured.")
        try:
            from nuscenes.map_expansion.map_api import NuScenesMap
            from real2scenario import MAP_LAYERS, native_map_records
        except ImportError as error:
            raise RuntimeError("nuscenes-devkit is required for full map layers.") from error
        api = NuScenesMap(dataroot=str(self._settings.dataset_root), map_name=map_name)
        layers: dict[str, list[dict[str, object]]] = {}
        for layer in MAP_LAYERS:
            output = []
            token_field = "polygon_token" if layer in {"road_segment", "road_block", "ped_crossing", "drivable_area"} else "line_token"
            extractor = api.extract_polygon if token_field == "polygon_token" else api.extract_line
            for record in native_map_records(api, layer):
                token = record.get(token_field)
                if not token:
                    continue
                geometry = extractor(token)
                coordinates = []
                if hasattr(geometry, "exterior"):
                    coordinates = [[_to_local((x, y), transform, (0.0, 0.0)) for x, y, *_ in geometry.exterior.coords]]
                elif hasattr(geometry, "coords"):
                    coordinates = [[_to_local((x, y), transform, (0.0, 0.0)) for x, y, *_ in geometry.coords]]
                elif hasattr(geometry, "geoms"):
                    coordinates = [[_to_local((x, y), transform, (0.0, 0.0)) for x, y, *_ in item.exterior.coords] for item in geometry.geoms if hasattr(item, "exterior")]
                if coordinates:
                    output.append({"token": record.get("token"), "geometry": coordinates})
            layers[layer] = output
        return {"contract_version": FULL_MAP_CONTRACT_VERSION, "frame": "local_road_aligned", "map_name": map_name, "layers": layers, "artifact_visibility": "local_private"}

    def layers(self, scenario: Scenario) -> dict[str, object]:
        provenance = scenario.provenance
        if "source_scene_token" not in provenance:
            raise KeyError("ground layers require a recorded source scene")
        transform = RoadAlignedTransform.from_provenance(provenance)
        map_name = resolve_scene_map_name(provenance["source_scene_token"], self._settings)
        if self._settings.dataset_root is None:
            raise ValueError("No local nuScenes dataset is configured.")
        try:
            from nuscenes.map_expansion.map_api import NuScenesMap
        except ImportError as error:
            raise RuntimeError("nuscenes-devkit is required for ground layers.") from error
        api = NuScenesMap(dataroot=str(self._settings.dataset_root), map_name=map_name)
        center_x, center_y, size_m = _global_patch_box(scenario, transform)
        out_layers = []
        for layer in GROUND_LAYERS:
            polygons = []
            for _name, geometries in api.get_map_geom(
                (center_x, center_y, size_m, size_m), 0, [layer]
            ):
                for geometry in _flatten(geometries):
                    exterior = [list(point) for point in geometry.exterior.coords]
                    holes = [[list(point) for point in ring.coords] for ring in geometry.interiors]
                    polygons.append(
                        {
                            "exterior": [
                                _to_local(point, transform, (center_x, center_y)) for point in exterior
                            ],
                            "holes": [
                                [_to_local(point, transform, (center_x, center_y)) for point in ring]
                                for ring in holes
                            ],
                        }
                    )
            out_layers.append({"name": layer, "polygons": polygons})
        return {
            "contract_version": GROUND_CONTRACT_VERSION,
            "frame": "local_road_aligned",
            "map_name": map_name,
            "bbox_margin_m": GROUND_MARGIN_M,
            "layers": out_layers,
        }


def _global_patch_box(scenario: Scenario, transform: RoadAlignedTransform) -> tuple[float, float, float]:
    """Actor bbox mapped back to the map frame, plus margin (mask API frame)."""
    corners = []
    for actor in scenario.actors:
        xs = [state.x_m for state in actor.trajectory]
        ys = [state.y_m for state in actor.trajectory]
        corners.extend([(min(xs), min(ys)), (max(xs), max(ys))])
    global_corners = [
        _to_source(point, transform) for point in corners
    ]
    gx = [point[0] for point in global_corners]
    gy = [point[1] for point in global_corners]
    size_m = max(max(gx) - min(gx), max(gy) - min(gy)) + 2 * GROUND_MARGIN_M
    return ((min(gx) + max(gx)) / 2, (min(gy) + max(gy)) / 2, size_m)


def _to_source(point: tuple[float, float], transform: RoadAlignedTransform) -> tuple[float, float]:
    state = transform.to_source_state(State(time_s=0.0, x_m=point[0], y_m=point[1], yaw_rad=0.0, speed_mps=0.0))
    return (state.x_m, state.y_m)


def _to_local(
    point: list[float], transform: RoadAlignedTransform, center: tuple[float, float]
) -> list[float]:
    """Move one patch vertex into the scenario local frame.

    devkit geometries come back patch-relative (offsets from the patch center,
    not map-global coordinates) with patch_angle fixed at 0, so rebase onto
    the center first, then apply the exact trajectory transform. Same math as
    the replay path — single source of truth, no parallel convention.
    """
    state = transform.to_local_state(
        State(
            time_s=0.0,
            x_m=center[0] + float(point[0]),
            y_m=center[1] + float(point[1]),
            yaw_rad=0.0,
            speed_mps=0.0,
        )
    )
    return [state.x_m, state.y_m]


def _flatten(geometries):
    """Split Polygon/MultiPolygon mixes into plain polygons."""
    from shapely.geometry import MultiPolygon, Polygon

    flat = []
    for geometry in geometries:
        if isinstance(geometry, Polygon):
            flat.append(geometry)
        elif isinstance(geometry, MultiPolygon):
            flat.extend(geometry.geoms)
    return flat
