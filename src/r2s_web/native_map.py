"""Local-private native nuScenes map query service."""

from __future__ import annotations

from typing import Any

from real2scenario import native_map_patch, road_ahead_query
from real2scenario import MAP_LAYERS, native_map_records

from .config import WebSettings

SUPPORTED_MAP_NAMES = {
    "boston-seaport",
    "singapore-hollandvillage",
    "singapore-onenorth",
    "singapore-queenstown",
}


class NativeMapService:
    """Lazily load the official map API and expose only read-only queries."""

    def __init__(self, settings: WebSettings):
        self.settings = settings
        self._apis: dict[str, Any] = {}

    def capability(self, map_name: str = "singapore-onenorth") -> dict[str, object]:
        if map_name not in SUPPORTED_MAP_NAMES:
            return {
                "available": False,
                "unavailable_reason": f"unsupported_map_name:{map_name}",
                "map_name": map_name,
            }
        if self.settings.dataset_root is None:
            return {"available": False, "unavailable_reason": "dataset_not_configured", "map_name": map_name}
        map_root = self.settings.dataset_root / "maps" / "expansion"
        if not map_root.is_dir():
            return {"available": False, "unavailable_reason": "map_expansion_not_available", "map_name": map_name}
        try:
            self._map_api(map_name)
        except (AssertionError, ImportError, OSError, RuntimeError, ValueError) as error:
            return {"available": False, "unavailable_reason": f"native_map_unavailable:{type(error).__name__}", "map_name": map_name}
        return {"available": True, "unavailable_reason": None, "map_name": map_name, "source": "nuscenes-devkit", "artifact_visibility": "local_private"}

    def patch(self, map_name: str, patch: tuple[float, float, float, float], layers: list[str]) -> dict[str, object]:
        api = self._map_api(map_name)
        return native_map_patch(api, patch, layers)

    def road_ahead(self, map_name: str, x_m: float, y_m: float) -> dict[str, object]:
        return road_ahead_query(self._map_api(map_name), x_m, y_m)

    def layers(self, map_name: str) -> dict[str, object]:
        api = self._map_api(map_name)
        return {
            "version": "nuscenes-native-map-query-v1",
            "status": "available",
            "map_name": map_name,
            "layers": {layer: [_record_with_geometry(api, layer, record) for record in native_map_records(api, layer)] for layer in MAP_LAYERS},
            "artifact_visibility": "local_private",
        }

    def _map_api(self, map_name: str) -> Any:
        if map_name not in self._apis:
            try:
                from nuscenes.map_expansion.map_api import NuScenesMap
            except ImportError as error:
                raise RuntimeError("nuscenes-devkit is required for native map queries") from error
            if self.settings.dataset_root is None:
                raise RuntimeError("dataset_not_configured")
            try:
                self._apis[map_name] = NuScenesMap(dataroot=str(self.settings.dataset_root), map_name=map_name)
            except AssertionError as error:
                raise ValueError(f"unsupported_map_name:{map_name}") from error
        return self._apis[map_name]


def _record_with_geometry(api: Any, layer: str, record: dict[str, object]) -> dict[str, object]:
    """Add only geometry extracted from the official devkit record."""
    result = dict(record)
    token_field = "polygon_token" if layer in {"road_segment", "road_block", "ped_crossing", "drivable_area"} else "line_token"
    token = result.get(token_field)
    extractor = getattr(api, "extract_polygon" if token_field == "polygon_token" else "extract_line", None)
    if token and extractor is not None:
        try:
            geometry = extractor(token)
            result["geometry"] = _geometry_coordinates(geometry)
        except (AttributeError, TypeError, ValueError):
            result["geometry_status"] = "unavailable"
    return result


def _geometry_coordinates(geometry: Any) -> list[list[float]]:
    if getattr(geometry, "is_empty", True):
        return []
    if hasattr(geometry, "exterior"):
        return [[float(x), float(y)] for x, y, *_ in geometry.exterior.coords]
    if hasattr(geometry, "coords"):
        return [[float(x), float(y)] for x, y, *_ in geometry.coords]
    if hasattr(geometry, "geoms"):
        output: list[list[float]] = []
        for item in geometry.geoms:
            output.extend(_geometry_coordinates(item))
        return output
    return []
