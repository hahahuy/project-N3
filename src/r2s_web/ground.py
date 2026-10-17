"""Survey-grade ground layers (sidewalk, crossing context) for the WASM preview.

Renders nuScenes map-expansion polygons for a scenario's actor bounding box
and returns them already moved into the scenario's local road-aligned frame,
so the browser draws them with the same transform as the replay trajectories.
Display-only: nothing here feeds metrics, gates or reports.
"""

from __future__ import annotations

from real2scenario import RoadAlignedTransform, Scenario, State

from .config import WebSettings
from .source_scenes import resolve_scene_map_name


GROUND_CONTRACT_VERSION = "ground-layers-v1"
GROUND_LAYERS = ("drivable_area", "walkway", "ped_crossing", "carpark_area")
GROUND_MARGIN_M = 40.0


class GroundService:
    """Serve local-frame map polygons for one recorded scenario."""

    def __init__(self, settings: WebSettings):
        self._settings = settings
        self._full_cache: dict[tuple[str, str, str, str], dict[str, object]] = {}

    def full_layers(self, scenario: Scenario) -> dict[str, object]:
        """Return full-scene map geometry transformed once into local coordinates."""
        provenance = scenario.provenance
        transform = RoadAlignedTransform.from_provenance(provenance)
        map_name = resolve_scene_map_name(provenance["source_scene_token"], self._settings)
        key = (map_name, str(transform.origin_x_m), str(transform.origin_y_m), str(transform.heading_rad))
        cached = self._full_cache.get(key)
        if cached is not None:
            return cached
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
        result = {"contract_version": "ground-full-map-v1", "frame": "local_road_aligned", "map_name": map_name, "layers": layers, "artifact_visibility": "local_private"}
        self._full_cache[key] = result
        return result

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
