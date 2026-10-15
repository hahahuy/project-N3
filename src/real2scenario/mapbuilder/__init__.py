"""CP1 OpenDRIVE subset and map-builder metadata contracts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from dataclasses import dataclass
from typing import Literal
from xml.etree import ElementTree as ET


MAP_BUILDER_VERSION = "map-builder-v1"
OPENDRIVE_SUBSET_VERSION = "r2s-odr-subset-v1"
GEOMETRY_FITTER_VERSION = "line-arc-greedy-v1"
CONTINUITY_VERSION = "connectivity-continuity-v1"
CENTERLINE_REPAIR_VERSION = "centerline-repair-v1"
LANE_WIDTH_ESTIMATOR_VERSION = "polygon-cross-section-median-v1"
MIN_CENTERLINE_SEGMENT_M = 1e-6


@dataclass(frozen=True, slots=True)
class GeometrySegment:
    kind: Literal["line", "arc"]
    start_index: int
    end_index: int
    s: float
    x: float
    y: float
    hdg: float
    length: float
    curvature: float | None
    max_residual_m: float


def fit_line_arc_geometry(
    poses: list[tuple[float, float, float]],
    *,
    tolerance_m: float = 0.05,
    min_arc_points: int = 3,
) -> tuple[GeometrySegment, ...]:
    """Fit deterministic line/constant-curvature segments to XY poses."""
    if tolerance_m <= 0 or min_arc_points < 3:
        raise ValueError("tolerance_m must be positive and min_arc_points must be at least 3.")
    if any(not all(math.isfinite(value) for value in pose) for pose in poses):
        raise ValueError("Geometry poses must contain finite values.")
    if len(poses) < 2:
        return ()
    segments: list[GeometrySegment] = []
    start = 0
    s = 0.0
    while start < len(poses) - 1:
        best = None
        for end in range(len(poses) - 1, start, -1):
            candidate = _choose_candidate(
                _line_candidate(poses, start, end, s, tolerance_m),
                _arc_candidate(poses, start, end, s, tolerance_m, min_arc_points),
            )
            if candidate is not None:
                best = candidate
                break
        if best is None:
            best = _line_candidate(poses, start, start + 1, s, float("inf"))
        segments.append(best)
        s += best.length
        start = best.end_index
    return tuple(segments)


def stable_road_id(source_lane_token: str) -> str:
    if not source_lane_token:
        raise ValueError("source_lane_token must not be empty.")
    return "r-" + hashlib.sha256(source_lane_token.encode("utf-8")).hexdigest()[:16]


def build_map_manifest(
    *, source_map_token: str, location: str, xodr_sha256: str, git_revision: str
) -> dict[str, str]:
    if not all((source_map_token, location, xodr_sha256, git_revision)):
        raise ValueError("map manifest identity fields must not be empty.")
    return {
        "map_builder_version": MAP_BUILDER_VERSION,
        "opendrive_version": "1.6",
        "opendrive_subset_version": OPENDRIVE_SUBSET_VERSION,
        "source_map_token": source_map_token,
        "location": location,
        "xodr_sha256": xodr_sha256,
        "git_revision": git_revision,
        "artifact_visibility": "local_private",
    }


def analyze_connectivity_continuity(
    dataset_root: str | Path,
    *,
    map_name: str = "singapore-onenorth",
    resolution_m: float = 5.0,
    position_tolerance_m: float = 0.5,
    heading_tolerance_rad: float = 0.2,
) -> dict[str, object]:
    """Report raw connectivity join gaps without changing emitted OpenDRIVE."""
    if resolution_m <= 0 or position_tolerance_m < 0 or heading_tolerance_rad < 0:
        raise ValueError("Continuity resolution must be positive and tolerances non-negative.")
    map_api = _load_nuscenes_map(dataset_root, map_name)
    records = list(map_api.lane) + list(map_api.lane_connector)
    tokens = sorted(record["token"] for record in records)
    paths = map_api.discretize_lanes(tokens, resolution_m)
    connectivity = getattr(map_api, "connectivity", {})
    edges = sorted(
        (source, target)
        for source in tokens
        for target in sorted((connectivity.get(source) or {}).get("outgoing", []))
    )
    failures: list[dict[str, object]] = []
    position_gaps: list[float] = []
    heading_gaps: list[float] = []
    edge_status_counts = {"pass": 0, "fail": 0, "unsupported": 0}
    asymmetric = 0
    missing_geometry = 0
    for source, target in edges:
        target_connectivity = connectivity.get(target) or {}
        source_path = paths.get(source, [])
        target_path = paths.get(target, [])
        if len(source_path) < 2 or len(target_path) < 2:
            missing_geometry += 1
            edge_status_counts["unsupported"] += 1
            failures.append({"source_token": source, "target_token": target, "reason": "missing_geometry"})
            continue
        reciprocal = source in (target_connectivity.get("incoming", []) or [])
        source_end = source_path[-1]
        target_start = target_path[0]
        position_gap = math.hypot(source_end[0] - target_start[0], source_end[1] - target_start[1])
        heading_gap = abs(_wrap_angle(source_end[2] - target_start[2]))
        position_gaps.append(position_gap)
        heading_gaps.append(heading_gap)
        reasons = []
        if not reciprocal:
            asymmetric += 1
            reasons.append("asymmetric_connectivity")
        if position_gap > position_tolerance_m:
            reasons.append("position_gap_exceeds_tolerance")
        if heading_gap > heading_tolerance_rad:
            reasons.append("heading_gap_exceeds_tolerance")
        if reasons:
            edge_status_counts["fail"] += 1
            failures.append({"source_token": source, "target_token": target, "position_gap_m": position_gap,
                             "heading_gap_rad": heading_gap, "reason": ";".join(reasons)})
        else:
            edge_status_counts["pass"] += 1
    return {
        "continuity_version": CONTINUITY_VERSION,
        "map_name": map_name,
        "resolution_m": resolution_m,
        "position_tolerance_m": position_tolerance_m,
        "heading_tolerance_rad": heading_tolerance_rad,
        "edge_count": len(edges),
        "checked_edge_count": edge_status_counts["pass"] + edge_status_counts["fail"],
        "missing_geometry_edges": missing_geometry,
        "asymmetric_connectivity_edges": asymmetric,
        "edge_status_counts": edge_status_counts,
        "position_gap_m": _distribution_summary(position_gaps),
        "heading_gap_rad": _distribution_summary(heading_gaps),
        "failures": failures,
        "status": "diagnostic",
        "artifact_visibility": "local_private",
    }


def validate_lane_topology(
    connectivity: dict[str, dict[str, list[str]]],
    paths: dict[str, list[tuple[float, float, float]]],
    selected_ids: set[str] | None = None,
    *,
    endpoint_tolerance_m: float = 20.0,
    heading_tolerance_rad: float = math.pi / 2,
) -> dict[str, object]:
    """Validate explicit directed source links without inferring replacements."""
    selected = set(paths) if selected_ids is None else set(selected_ids)
    failures: list[dict[str, object]] = []
    checked = 0
    for source in sorted(selected):
        relation = connectivity.get(source) or {}
        for target in sorted(set(relation.get("outgoing", [])) & selected):
            checked += 1
            target_relation = connectivity.get(target) or {}
            source_path, target_path = paths.get(source, []), paths.get(target, [])
            reasons: list[str] = []
            if source not in set(target_relation.get("incoming", [])):
                reasons.append("reciprocal_link_missing")
            if len(source_path) < 2 or len(target_path) < 2:
                reasons.append("invalid_link_geometry")
            else:
                position_gap = math.hypot(source_path[-1][0] - target_path[0][0], source_path[-1][1] - target_path[0][1])
                heading_gap = abs(_wrap_angle(source_path[-1][2] - target_path[0][2]))
                if position_gap > endpoint_tolerance_m:
                    reasons.append("endpoint_gap")
                if heading_gap > heading_tolerance_rad:
                    reasons.append("heading_discontinuity")
            if reasons:
                failures.append({"source_id": source, "target_id": target, "classification": "missing_source_link" if "reciprocal_link_missing" in reasons else "builder_link_bug", "reasons": reasons})
    return {
        "validation_version": "lane-topology-validation-v1",
        "selected_count": len(selected),
        "checked_link_count": checked,
        "failure_count": len(failures),
        "failures": failures,
        "status": "diagnostic",
    }


def _distribution_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"max": None, "mean": None, "p95": None}
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(0.95 * len(ordered)) - 1))
    return {"max": max(ordered), "mean": sum(ordered) / len(ordered), "p95": ordered[index]}


def validate_opendrive_subset(xml_text: str) -> None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise ValueError(f"invalid OpenDRIVE XML: {error}") from error
    if root.tag != "OpenDRIVE":
        raise ValueError("OpenDRIVE root is required.")
    unsupported = {"signals", "objects", "railroad", "superelevation"}
    found = unsupported.intersection(element.tag for element in root.iter())
    if found:
        raise ValueError(f"unsupported OpenDRIVE feature: {sorted(found)[0]}")


def build_opendrive_from_nuscenes(
    dataset_root: str | Path,
    *,
    map_name: str = "singapore-onenorth",
    output_path: str | Path,
    resolution_m: float = 5.0,
    fallback_width_m: float = 3.5,
    geometry_mode: Literal["line", "line_arc"] = "line",
    arc_tolerance_m: float = 0.05,
    selected_tokens: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Build a local/private OpenDRIVE subset from nuScenes map expansion."""
    if geometry_mode not in {"line", "line_arc"}:
        raise ValueError("geometry_mode must be 'line' or 'line_arc'.")
    if resolution_m <= 0 or fallback_width_m <= 0 or arc_tolerance_m <= 0:
        raise ValueError("resolution_m and fallback_width_m must be positive.")
    map_api = _load_nuscenes_map(dataset_root, map_name)
    records = list(map_api.lane) + list(map_api.lane_connector)
    if selected_tokens is not None:
        selected = set(selected_tokens)
        records = [record for record in records if record["token"] in selected]
        if not records:
            raise ValueError("selected_tokens must contain at least one emitted map record.")
    token_to_record = {record["token"]: record for record in records}
    raw_paths = map_api.discretize_lanes(list(token_to_record), resolution_m)
    paths, repair_report = repair_centerline_paths(raw_paths)
    topology_report = validate_lane_topology(
        getattr(map_api, "connectivity", {}), paths, set(token_to_record)
    )
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", {"revMajor": "1", "revMinor": "6", "name": map_name})
    road_ids: dict[str, str] = {}
    geometry_status: dict[str, str] = {}
    fitted_segments: list[GeometrySegment] = []
    lane_width_sources: dict[str, str] = {}
    connector_tokens = {record["token"] for record in getattr(map_api, "lane_connector", [])}
    junction_specs: dict[str, dict[str, object]] = {}
    for record in records:
        token = record["token"]
        poses = paths.get(token, [])
        if len(poses) < 2:
            geometry_status[token] = "unsupported"
            continue
        road_id = stable_road_id(token)
        road_ids[token] = road_id
        segments = None
        if geometry_mode == "line_arc":
            segments = fit_line_arc_geometry(poses, tolerance_m=arc_tolerance_m)
            if not segments:
                geometry_status[token] = "unsupported"
                continue
            length = sum(segment.length for segment in segments)
        else:
            length = _path_length(poses)
        connectivity = getattr(map_api, "connectivity", {}).get(token)
        junction = stable_junction_id(connectivity) if token in connector_tokens and connectivity else "-1"
        road = ET.SubElement(root, "road", {"name": token, "id": road_id, "length": _number(length), "junction": junction})
        plan = ET.SubElement(road, "planView")
        if segments is None:
            _append_line_geometry(plan, poses)
        else:
            _append_fitted_geometry(plan, segments)
            fitted_segments.extend(segments)
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", {"s": "0", "a": "0", "b": "0", "c": "0", "d": "0"})
        section = ET.SubElement(lanes, "laneSection", {"s": "0"})
        ET.SubElement(section, "left")
        center = ET.SubElement(section, "center")
        ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
        right = ET.SubElement(section, "right")
        lane = ET.SubElement(right, "lane", {"id": "-1", "type": "driving", "level": "false"})
        width, width_source = _lane_width(map_api, record, poses, fallback_width_m)
        ET.SubElement(lane, "width", {"sOffset": "0", "a": _number(width), "b": "0", "c": "0", "d": "0"})
        lane_width_sources[token] = width_source
        geometry_status[token] = "approximated_line_segments" if segments is None else "fitted_line_arc_segments"
        if token in connector_tokens and connectivity:
            junction_specs[junction] = {"connector": token, "incoming": list(connectivity.get("incoming", [])), "outgoing": list(connectivity.get("outgoing", []))}
    for road in root.findall("road"):
        _append_links(road, road.attrib["name"], map_api, road_ids)
    _append_junctions(root, junction_specs, road_ids)
    ET.indent(root, space="  ")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    manifest = {
        "map_builder_version": MAP_BUILDER_VERSION,
        "opendrive_version": "1.6",
        "opendrive_subset_version": OPENDRIVE_SUBSET_VERSION,
        "map_name": map_name,
        "road_count": len(road_ids),
        "unsupported_geometry_count": sum(status == "unsupported" for status in geometry_status.values()),
        "geometry_status_counts": {status: sum(value == status for value in geometry_status.values()) for status in sorted(set(geometry_status.values()))},
        "geometry_mode": geometry_mode,
        "geometry_fitter_version": GEOMETRY_FITTER_VERSION if geometry_mode == "line_arc" else None,
        "residual_statistics": None if geometry_mode == "line" else _residual_statistics(fitted_segments),
        "resolution_m": resolution_m,
        "lane_width_source": "polygon_cross_section_median" if any(value == LANE_WIDTH_ESTIMATOR_VERSION for value in lane_width_sources.values()) else ("polygon_area_over_centerline" if any(value == "polygon" for value in lane_width_sources.values()) else "fallback_constant"),
        "fallback_width_m": fallback_width_m,
        "lane_width_source_counts": {source: sum(value == source for value in lane_width_sources.values()) for source in sorted(set(lane_width_sources.values()))},
        "junction_count": len(junction_specs),
        "artifact_visibility": "local_private",
        "geometry_status": geometry_status,
        "centerline_repair_version": CENTERLINE_REPAIR_VERSION,
        "centerline_repair": repair_report,
        "topology_validation": topology_report,
    }
    return manifest


def build_scene_local_corridor(
    dataset_root: str | Path,
    scenario,
    *,
    output_path: str | Path,
    map_name: str = "singapore-onenorth",
    buffer_m: float = 40.0,
    resolution_m: float = 5.0,
    selected_actor_ids: tuple[str, ...] | None = None,
    geometry_mode: Literal["line", "line_arc"] = "line",
) -> dict[str, object]:
    """Build a private, one-hop-closed corridor around selected actor paths."""
    if not 30.0 <= buffer_m <= 50.0:
        raise ValueError("Corridor buffer_m must be between 30 and 50 metres.")
    if scenario.coordinate_frame != "nuscenes_global":
        raise ValueError("Scene-local corridor currently requires nuscenes_global coordinates.")
    actor_ids = tuple(actor.actor_id for actor in scenario.actors) if selected_actor_ids is None else selected_actor_ids
    if not actor_ids or len(set(actor_ids)) != len(actor_ids):
        raise ValueError("Corridor actor IDs must be non-empty and unique.")
    actors = {actor.actor_id: actor for actor in scenario.actors}
    if any(actor_id not in actors for actor_id in actor_ids):
        raise ValueError("Corridor actor IDs must identify scenario actors.")
    map_api = _load_nuscenes_map(dataset_root, map_name)
    records = list(map_api.lane) + list(map_api.lane_connector)
    raw_paths = map_api.discretize_lanes(sorted(record["token"] for record in records), resolution_m)
    paths, repair_report = repair_centerline_paths(raw_paths)
    trajectory_points = [(state.x_m, state.y_m) for actor_id in actor_ids for state in actors[actor_id].trajectory]
    initial = []
    for record in records:
        token = record["token"]
        if any(_minimum_point_distance(path_pose, trajectory_points) <= buffer_m for path_pose in paths.get(token, ())):
            initial.append(token)
    if not initial:
        raise ValueError("No lane or connector centerline intersects the corridor buffer.")
    closure = set(initial)
    connectivity = getattr(map_api, "connectivity", {})
    for token in initial:
        relation = connectivity.get(token) or {}
        closure.update(target for target in relation.get("incoming", []) + relation.get("outgoing", []) if target in paths)
    selected = tuple(sorted(closure))
    if not selected:
        raise ValueError("Corridor topology closure selected no map records.")
    manifest = build_opendrive_from_nuscenes(
        dataset_root, map_name=map_name, output_path=output_path, resolution_m=resolution_m,
        geometry_mode=geometry_mode, selected_tokens=selected,
    )
    manifest.update({
        "manifest_version": "cp1-scene-corridor-v1",
        "map_reconstruction_mode": "local_nuscenes_corridor",
        "source_scene_id": scenario.provenance.get("source_scene_token", scenario.scenario_id),
        "source_scenario_id": scenario.scenario_id,
        "crop_mode": "trajectory_corridor",
        "buffer_m": buffer_m,
        "boundary_policy": "intersect_closed_trajectory_buffer_centerline_selection",
        "topology_closure": "one_hop_incident_connectivity",
        "recursive_expansion": False,
        "selected_actor_ids": list(actor_ids),
        "initial_selected_tokens": sorted(initial),
        "closure_added_tokens": sorted(set(selected) - set(initial)),
        "selected_tokens": list(selected),
        "artifact_visibility": "local_private",
        "centerline_repair_version": CENTERLINE_REPAIR_VERSION,
        "centerline_repair": repair_report,
    })
    return manifest


def _minimum_point_distance(pose, points):
    return min(math.hypot(pose[0] - point[0], pose[1] - point[1]) for point in points)


def repair_centerline_paths(paths: dict[str, list[tuple[float, float, float]]]):
    """Remove consecutive duplicate XY samples without hiding source records.

    A path with fewer than two distinct samples is explicitly excluded from
    emitted geometry and retained in the repair report with its source ID.
    """
    repaired: dict[str, list[tuple[float, float, float]]] = {}
    repaired_ids: list[str] = []
    excluded: list[dict[str, object]] = []
    before_segments = 0
    after_segments = 0
    for source_id in sorted(paths):
        raw = list(paths[source_id])
        before_segments += max(0, len(raw) - 1)
        normalized: list[tuple[float, float, float]] = []
        removed = 0
        for pose in raw:
            if not normalized or math.hypot(pose[0] - normalized[-1][0], pose[1] - normalized[-1][1]) >= MIN_CENTERLINE_SEGMENT_M:
                normalized.append(pose)
            else:
                removed += 1
        if len(normalized) < 2 or _path_length(normalized) < MIN_CENTERLINE_SEGMENT_M:
            excluded.append({
                "source_id": source_id,
                "reason": "collapsed_centerline_after_duplicate_filter",
                "input_pose_count": len(raw),
                "remaining_pose_count": len(normalized),
            })
            continue
        repaired[source_id] = normalized
        after_segments += len(normalized) - 1
        if removed:
            repaired_ids.append(source_id)
    return repaired, {
        "version": CENTERLINE_REPAIR_VERSION,
        "minimum_segment_m": MIN_CENTERLINE_SEGMENT_M,
        "records_inspected": len(paths),
        "records_repaired": len(repaired_ids),
        "repaired_source_ids": repaired_ids,
        "records_excluded": len(excluded),
        "excluded": excluded,
        "before_segment_count": before_segments,
        "after_segment_count": after_segments,
    }


def _load_nuscenes_map(dataset_root: str | Path, map_name: str) -> object:
    try:
        from nuscenes.map_expansion.map_api import NuScenesMap
    except ImportError as error:
        raise RuntimeError("nuscenes-devkit is required for the map builder.") from error
    return NuScenesMap(dataroot=str(dataset_root), map_name=map_name)


def _lane_width(map_api, record, poses, fallback_width_m):
    polygon_token = record.get("polygon_token")
    extractor = getattr(map_api, "extract_polygon", None)
    if polygon_token and extractor is not None:
        try:
            polygon = extractor(polygon_token)
            width = _median_polygon_cross_section(polygon, poses)
            if width is not None:
                return width, LANE_WIDTH_ESTIMATOR_VERSION
            area = float(getattr(polygon, "area"))
            length = _path_length(poses)
            if math.isfinite(area) and area > 0 and length > 0:
                width = area / length
                if math.isfinite(width) and width > 0:
                    return width, "polygon"
        except (AttributeError, TypeError, ValueError):
            pass
    return fallback_width_m, "fallback"


def _median_polygon_cross_section(polygon, poses):
    """Estimate lane width from perpendicular polygon cross-sections."""
    try:
        from shapely.geometry import LineString

        boundary = polygon.boundary
    except (AttributeError, ImportError):
        return None
    widths: list[float] = []
    for x, y, heading in poses[:: max(1, len(poses) // 20)]:
        perpendicular = (-math.sin(heading), math.cos(heading))
        line = LineString(
            [
                (x - perpendicular[0] * 20.0, y - perpendicular[1] * 20.0),
                (x + perpendicular[0] * 20.0, y + perpendicular[1] * 20.0),
            ]
        )
        intersection = boundary.intersection(line)
        points = _geometry_points(intersection)
        if len(points) >= 2:
            distances = sorted(
                math.hypot(a[0] - x, a[1] - y) for a in points
            )
            width = distances[0] + distances[1]
            if math.isfinite(width) and width > 0:
                widths.append(width)
    if not widths:
        return None
    ordered = sorted(widths)
    return ordered[len(ordered) // 2]


def _geometry_points(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Point":
        return [(geometry.x, geometry.y)]
    if hasattr(geometry, "geoms"):
        points = []
        for item in geometry.geoms:
            points.extend(_geometry_points(item))
        return points
    return [(x, y) for x, y, *_ in geometry.coords]


def _append_junctions(root, specs, road_ids):
    for junction_id, spec in sorted(specs.items()):
        junction = ET.SubElement(root, "junction", {"id": junction_id, "name": junction_id})
        connector_id = road_ids.get(spec["connector"])
        if connector_id is None:
            continue
        connection_index = 0
        for incoming in sorted(spec["incoming"]):
            incoming_id = road_ids.get(incoming)
            if incoming_id is None:
                continue
            connection = ET.SubElement(junction, "connection", {"id": str(connection_index), "incomingRoad": incoming_id, "connectingRoad": connector_id, "contactPoint": "start"})
            ET.SubElement(connection, "laneLink", {"from": "-1", "to": "-1"})
            connection_index += 1


def stable_junction_id(connectivity: dict[str, list[str]]) -> str:
    values = sorted(connectivity.get("incoming", []) + connectivity.get("outgoing", []))
    return "j-" + hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:16]


def _append_line_geometry(parent: ET.Element, poses: list[tuple[float, float, float]]) -> None:
    s = 0.0
    for previous, current in zip(poses, poses[1:]):
        x, y, heading = previous
        length = math.hypot(current[0] - x, current[1] - y)
        if length <= 1e-9:
            continue
        geometry = ET.SubElement(parent, "geometry", {"s": _number(s), "x": _number(x), "y": _number(y), "hdg": _number(heading), "length": _number(length)})
        ET.SubElement(geometry, "line")
        s += length


def _append_fitted_geometry(parent: ET.Element, segments: tuple[GeometrySegment, ...]) -> None:
    for segment in segments:
        geometry = ET.SubElement(parent, "geometry", {
            "s": _number(segment.s), "x": _number(segment.x), "y": _number(segment.y),
            "hdg": _number(segment.hdg), "length": _number(segment.length),
        })
        if segment.kind == "arc":
            ET.SubElement(geometry, "arc", {"curvature": _number(segment.curvature or 0.0)})
        else:
            ET.SubElement(geometry, "line")


def _residual_statistics(segments: list[GeometrySegment]) -> dict[str, object]:
    if not segments:
        return {
            "segment_count": 0,
            "line_segment_count": 0,
            "arc_segment_count": 0,
            "max_residual_m": None,
            "mean_residual_m": None,
            "p95_residual_m": None,
        }
    residuals = sorted(segment.max_residual_m for segment in segments)
    index = min(len(residuals) - 1, max(0, math.ceil(0.95 * len(residuals)) - 1))
    return {
        "segment_count": len(segments),
        "line_segment_count": sum(segment.kind == "line" for segment in segments),
        "arc_segment_count": sum(segment.kind == "arc" for segment in segments),
        "max_residual_m": max(residuals),
        "mean_residual_m": sum(residuals) / len(residuals),
        "p95_residual_m": residuals[index],
    }


def _line_candidate(poses, start, end, s, tolerance):
    x0, y0, heading = poses[start]
    x1, y1, _ = poses[end]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return None
    residual = max(abs(dy * (x - x0) - dx * (y - y0)) / length for x, y, _ in poses[start : end + 1])
    if residual > tolerance:
        return None
    return GeometrySegment("line", start, end, s, x0, y0, heading, length, None, residual)


def _arc_candidate(poses, start, end, s, tolerance, min_points):
    if end - start + 1 < min_points:
        return None
    x1, y1, h1 = poses[start]
    xm, ym, _ = poses[(start + end) // 2]
    x2, y2, _ = poses[end]
    determinant = 2 * (x1 * (ym - y2) + xm * (y2 - y1) + x2 * (y1 - ym))
    if abs(determinant) <= 1e-9:
        return None
    a = x1 * x1 + y1 * y1
    b = xm * xm + ym * ym
    c = x2 * x2 + y2 * y2
    cx = (a * (ym - y2) + b * (y2 - y1) + c * (y1 - ym)) / determinant
    cy = (a * (x2 - xm) + b * (x1 - x2) + c * (xm - x1)) / determinant
    radius = math.hypot(x1 - cx, y1 - cy)
    if radius <= 1e-9:
        return None
    angles = [math.atan2(y - cy, x - cx) for x, y, _ in poses[start : end + 1]]
    direction = _wrap_angle(angles[1] - angles[0])
    if abs(direction) <= 1e-9:
        return None
    signed_direction = 1.0 if direction > 0 else -1.0
    unwrapped = [angles[0]]
    for angle in angles[1:]:
        delta = _wrap_angle(angle - unwrapped[-1])
        if delta * signed_direction < -1e-6:
            return None
        unwrapped.append(unwrapped[-1] + delta)
    residual = max(abs(math.hypot(x - cx, y - cy) - radius) for x, y, _ in poses[start : end + 1])
    if residual > tolerance:
        return None
    sweep = abs(unwrapped[-1] - unwrapped[0])
    length = radius * sweep
    curvature = signed_direction / radius
    return GeometrySegment("arc", start, end, s, x1, y1, h1, length, curvature, residual)


def _choose_candidate(line, arc):
    if line is None:
        return arc
    if arc is None:
        return line
    return arc if arc.max_residual_m + 1e-6 < line.max_residual_m else line


def _same_xy(first, second):
    return math.hypot(first[0] - second[0], first[1] - second[1]) <= 1e-9


def _wrap_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def _append_links(road: ET.Element, token: str, map_api: object, road_ids: dict[str, str]) -> None:
    incoming = sorted(set(map_api.get_incoming_lane_ids(token) or []))
    outgoing = sorted(set(map_api.get_outgoing_lane_ids(token) or []))
    links = ET.SubElement(road, "link")
    if incoming and incoming[0] in road_ids:
        ET.SubElement(links, "predecessor", {"elementType": "road", "elementId": road_ids[incoming[0]], "contactPoint": "end"})
    if outgoing and outgoing[0] in road_ids:
        ET.SubElement(links, "successor", {"elementType": "road", "elementId": road_ids[outgoing[0]], "contactPoint": "start"})


def _path_length(poses: list[tuple[float, float, float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(poses, poses[1:]))


def _number(value: float) -> str:
    return format(value, ".17g")
