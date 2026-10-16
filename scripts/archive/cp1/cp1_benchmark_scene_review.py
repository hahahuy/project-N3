#!/usr/bin/env python3
"""CP1 external review of benchmark scenes: references, footprints, topology.

For every scene of a prepared benchmark run this script produces the three
CP1 diagnostic families that were previously only available for scene-0061:

1. per-candidate lane reference attribution across the native nuScenes map, the
   canonical lane graph and the generated corridor OpenDRIVE;
2. per-candidate footprint/occupancy evidence with unsupported vehicle
   dimensions and lane-width sources kept explicitly separate;
3. per-scene corridor topology, junction emission and line/arc residual
   evidence for the generated OpenDRIVE.

Nothing here changes a matcher tolerance, a lane direction, a reference
convention, the actor scope or ground truth, and nothing is repaired to raise a
rate. Every candidate is measured and reported, including failing ones.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

from r2s_web.config import WebSettings
from r2s_web.source_scenes import SourceSceneAdapter, shared_metadata_index
from real2scenario import (
    LaneWidthRecord,
    RoadAlignedTransform,
    SourceWindow,
    State,
    build_lane_graph,
    build_scene_local_corridor,
    compare_lane_references,
    diagnose_lane_footprint_occupancy,
    diagnose_lane_road_match,
    extract_scenario,
    lane_centerlines_from_nuscenes,
    lane_centerlines_from_opendrive,
    lane_graph_from_opendrive,
    validate_opendrive_subset,
)


def main() -> int:
    args = _parse_args()
    index = json.loads(args.scene_index.expanduser().resolve().read_text(encoding="utf-8"))
    run_root = args.run_root.expanduser().resolve()
    evidence_root = args.evidence_root.expanduser().resolve()
    corridor_root = evidence_root / "corridors"
    corridor_root.mkdir(parents=True, exist_ok=True)

    settings = WebSettings(
        project_root=evidence_root,
        artifact_root=evidence_root / "artifacts",
        output_root=evidence_root / "outputs",
        dataset_root=args.dataset_root.expanduser().resolve(),
        esmini_bin=None,
        esmini_dat2csv=None,
        dataset_version=args.dataset_version,
    )
    source_adapter = SourceSceneAdapter(settings)
    metadata_index = shared_metadata_index(settings)

    scenes = index["scenes"]
    if args.limit_scenes:
        scenes = scenes[: args.limit_scenes]

    scene_reports: list[dict[str, object]] = []
    for scene in scenes:
        scene_name = scene["name"]
        run_record = _run_record(run_root, scene_name)
        if run_record is None:
            scene_reports.append({"scene_id": scene_name, "status": "no-run-artifacts"})
            continue
        scenario_id = str(run_record["scenario_id"])
        parent, transform = _parent_scenario(settings, metadata_index, source_adapter, scene, args)
        topology = _scene_topology(
            settings, parent, scene_name, corridor_root, args, evidence_root
        )
        references = _references(settings, parent, transform, topology, args)
        candidates = _candidates(
            run_root, str(run_record["run_id"]), scenario_id, references, transform, topology
        )
        scene_reports.append(
            {
                "scene_id": scene_name,
                "status": "reviewed",
                "scenario_id": scenario_id,
                "run_id": run_record["run_id"],
                "selected_actor_ids": [actor.actor_id for actor in parent.actors],
                "topology": topology["summary"],
                "reference_attribution": _attribution_summary(references, candidates),
                "footprint_occupancy": _footprint_summary(candidates),
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )

    run_card = {
        "review_version": "cp1-benchmark-scene-review-v1",
        "scientific_status": "PROVISIONAL",
        "diagnostic_status": "diagnostic",
        "artifact_visibility": "local_private",
        "git_revision": _git_revision(),
        "corridor_contract": {
            "crop_mode": "trajectory_corridor",
            "boundary_policy": "intersect_closed_trajectory_buffer_centerline_selection",
            "buffer_m": args.buffer_m,
            "resolution_m": args.resolution_m,
            "map_name": args.map_name,
        },
        "references": [
            "native_nuscenes",
            "canonical_lane_graph",
            "generated_corridor_xodr",
            "corridor_centerlines_unnormalized",
        ],
        "scenes": scene_reports,
    }
    if args.dry_run:
        print(json.dumps(run_card, indent=2, sort_keys=True))
        return 0
    destination = evidence_root / "cp1-scene-review.json"
    destination.write_text(json.dumps(run_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(destination)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/mnt/backup/nuscenes"))
    parser.add_argument("--dataset-version", default="v1.0-trainval")
    parser.add_argument("--scene-index", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--map-name", default="singapore-onenorth")
    parser.add_argument("--buffer-m", type=float, default=40.0)
    parser.add_argument("--resolution-m", type=float, default=5.0)
    parser.add_argument("--max-actors", type=int, default=3)
    parser.add_argument("--limit-scenes", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _scene_topology(settings, parent, scene_name, corridor_root, args, evidence_root) -> dict:
    """Build line and line/arc corridors and report topology, junctions, residuals."""
    output = {
        "summary": {"scene_id": scene_name},
        "corridor_path": None,
        "line": {},
        "line_arc": {},
        "subset_validation": {},
        "lane_widths": (),
        "references": {},
    }
    line_path = corridor_root / f"{scene_name}-corridor.xodr"
    line_manifest = build_scene_local_corridor(
        settings.dataset_root,
        parent,
        output_path=line_path,
        map_name=args.map_name,
        buffer_m=args.buffer_m,
        resolution_m=args.resolution_m,
        selected_actor_ids=tuple(actor.actor_id for actor in parent.actors),
    )
    output["corridor_path"] = line_path.as_posix()
    arc_path = corridor_root / f"{scene_name}-corridor-line-arc.xodr"
    arc_manifest = build_scene_local_corridor(
        settings.dataset_root,
        parent,
        output_path=arc_path,
        map_name=args.map_name,
        buffer_m=args.buffer_m,
        resolution_m=args.resolution_m,
        selected_actor_ids=tuple(actor.actor_id for actor in parent.actors),
        geometry_mode="line_arc",
    )
    line_xodr = line_path.read_text(encoding="utf-8")
    arc_xodr = arc_path.read_text(encoding="utf-8")
    try:
        validate_opendrive_subset(line_xodr)
        output["subset_validation"] = {"valid": True, "failures": []}
    except ValueError as error:
        output["subset_validation"] = {"valid": False, "failures": [str(error)]}
    output["line"] = _corridor_view(line_manifest, line_xodr)
    output["line_arc"] = _corridor_view(arc_manifest, arc_xodr)
    output["summary"] = {
        "scene_id": scene_name,
        "selected_lane_count": len(line_manifest.get("selected_tokens", ())),
        "road_count": line_manifest.get("road_count"),
        "junction_count": line_manifest.get("junction_count"),
        "closure_edge_count": line_manifest.get("closure_edge_count"),
        "closure_boundary_edges": line_manifest.get("closure_boundary_edges"),
        "lane_width_source": line_manifest.get("lane_width_source"),
        "lane_width_source_counts": line_manifest.get("lane_width_source_counts"),
        "geometry_mode": line_manifest.get("geometry_mode"),
        "line_arc_residual_statistics": arc_manifest.get("residual_statistics"),
        "subset_valid": output["subset_validation"].get("valid"),
        "subset_failures": output["subset_validation"].get("failures"),
        "dangling_junction_references": _dangling_references(line_xodr),
        "dangling_road_links": _dangling_links(line_xodr),
    }
    widths = _lane_widths(line_xodr)
    output["lane_widths"] = widths
    output["references"] = {
        "native": lane_centerlines_from_nuscenes(
            str(settings.dataset_root),
            map_name=args.map_name,
            selected_tokens=tuple(line_manifest.get("selected_tokens", ())),
            resolution_m=args.resolution_m,
        ),
        "corridor": lane_centerlines_from_opendrive(line_xodr),
        "corridor_normalized": build_lane_graph(
            lane_centerlines_from_opendrive(line_xodr)
        ),
        "native_normalized": build_lane_graph(
            lane_centerlines_from_nuscenes(
                str(settings.dataset_root),
                map_name=args.map_name,
                selected_tokens=tuple(line_manifest.get("selected_tokens", ())),
                resolution_m=args.resolution_m,
            )
        ),
    }
    return output


def _references(settings, parent, transform, topology, args):
    """Return explicit lane references in the candidates' local road-aligned frame.

    Every reference is expressed in the same frame as the generated candidates so
    the comparison measures reference semantics rather than a frame mismatch.
    """
    native = tuple(_to_local_lane(lane, transform) for lane in topology["references"]["native"])
    corridor = tuple(
        _to_local_lane(lane, transform) for lane in topology["references"]["corridor"]
    )
    return {
        "native_nuscenes": build_lane_graph(native),
        "canonical_lane_graph": build_lane_graph(native),
        "generated_corridor_xodr": build_lane_graph(corridor),
        "corridor_centerlines_unnormalized": build_lane_graph(corridor),
        "corridor_centerlines": corridor,
    }


def _candidates(run_root, run_id, scenario_id, references, transform, topology):
    """Measure reference attribution and footprint occupancy per candidate."""
    from real2scenario import artifact_from_json

    local_corridor = references["corridor_centerlines"]
    widths = topology["lane_widths"]
    results = []
    for path, variant_id in _candidate_artifacts(run_root, run_id, scenario_id):
        variant, _parent_id, _config = artifact_from_json(path.read_text(encoding="utf-8"))
        actor_ids = tuple(actor.actor_id for actor in variant.actors)
        comparison = compare_lane_references(
            variant,
            (
                ("native_nuscenes", references["native_nuscenes"]),
                ("canonical_lane_graph", references["canonical_lane_graph"]),
                ("generated_corridor_xodr", references["generated_corridor_xodr"]),
                ("corridor_centerlines_unnormalized", references["corridor_centerlines_unnormalized"]),
            ),
            actor_ids=actor_ids,
        )
        corridor_match = diagnose_lane_road_match(
            variant,
            local_corridor,
            lane_coordinate_frame=variant.coordinate_frame,
            actor_ids=actor_ids,
        )
        occupancy = diagnose_lane_footprint_occupancy(
            variant,
            local_corridor,
            tuple(
                LaneWidthRecord(width.lane_id, width.width_m, width.source)
                for width in widths
            ),
            lane_coordinate_frame=variant.coordinate_frame,
            actor_ids=actor_ids,
        )
        results.append(
            {
                "variant_id": variant_id,
                "reference_summaries": [_reference_view(summary) for summary in comparison.summaries],
                "corridor_match": {
                    "state_count": corridor_match.overall.state_count,
                    "matched_state_count": corridor_match.overall.matched_state_count,
                    "raw_match_rate": corridor_match.overall.raw_match_rate,
                    "per_actor_raw_match_rate": {
                        item.actor_id: item.summary.raw_match_rate
                        for item in corridor_match.per_actor
                    },
                },
                "footprint_occupancy": _occupancy_view(occupancy, variant.actors),
            }
        )
    return results


def _reference_view(summary) -> dict:
    """Flatten one reference summary into explicit, separately reported counts."""
    return {
        "reference": summary.reference_name,
        "state_count": summary.state_count,
        "lane_semantically_valid": summary.lane_semantically_valid_count,
        "lane_centerline_offset_high": summary.lane_centerline_offset_high_count,
        "lane_polygon_outside": summary.lane_polygon_outside_count,
        "footprint_unsupported": summary.footprint_unsupported_count,
        "heading_conflict": summary.heading_conflict_count,
        "topology_invalid": summary.topology_invalid_count,
        "unmatched": summary.unmatched_count,
        "mean_lateral_error_m": summary.mean_lateral_error_m,
        "p95_lateral_error_m": summary.p95_lateral_error_m,
        "max_heading_error_rad": summary.max_heading_error_rad,
    }


REVIEW_REFERENCES = (
    "native_nuscenes",
    "canonical_lane_graph",
    "generated_corridor_xodr",
    "corridor_centerlines_unnormalized",
)


def _attribution_summary(references, candidates) -> dict:
    """Aggregate per-reference state classifications across candidates."""
    names = [name for name in REVIEW_REFERENCES if name in references]
    summary = {}
    for name in names:
        totals = {
            "reference_summaries": 0,
            "state_count": 0,
            "lane_semantically_valid": 0,
            "lane_centerline_offset_high": 0,
            "lane_polygon_outside": 0,
            "footprint_unsupported": 0,
            "heading_conflict": 0,
            "topology_invalid": 0,
            "unmatched": 0,
            "abs_lateral_offset_sum_m": 0.0,
        }
        for candidate in candidates:
            for entry in candidate["reference_summaries"]:
                if entry["reference"] != name:
                    continue
                totals["reference_summaries"] += 1
                totals["state_count"] += entry["state_count"]
                for key in (
                    "lane_semantically_valid",
                    "lane_centerline_offset_high",
                    "lane_polygon_outside",
                    "footprint_unsupported",
                    "heading_conflict",
                    "topology_invalid",
                    "unmatched",
                ):
                    totals[key] += entry[key]
                totals["abs_lateral_offset_sum_m"] += abs(entry["mean_lateral_error_m"] or 0.0)
        summary[name] = totals
    return summary


def _footprint_summary(candidates) -> dict:
    totals = {
        "state_count": 0,
        "occupied": 0,
        "outside": 0,
        "unsupported": 0,
        "reasons": {},
        "width_sources": {},
        "actors_without_dimensions": [],
    }
    for candidate in candidates:
        occupancy = candidate["footprint_occupancy"]
        totals["state_count"] += occupancy["state_count"]
        totals["occupied"] += occupancy["occupied"]
        totals["outside"] += occupancy["outside"]
        totals["unsupported"] += occupancy["unsupported"]
        for reason, count in occupancy["reasons"].items():
            totals["reasons"][reason] = totals["reasons"].get(reason, 0) + count
        for source, count in occupancy["width_sources"].items():
            totals["width_sources"][source] = totals["width_sources"].get(source, 0) + count
        totals["actors_without_dimensions"] = sorted(
            set(totals["actors_without_dimensions"]) | set(occupancy["actors_without_dimensions"])
        )
    return totals


def _occupancy_view(report, actors) -> dict:
    """Summarize occupancy while keeping unsupported dimensions explicit."""
    reasons: dict[str, int] = {}
    width_sources: dict[str, int] = {}
    occupied = outside = unsupported = 0
    dimensions_missing = {
        actor.actor_id
        for actor in actors
        if actor.width_m is None or actor.length_m is None
    }
    actors_without_dimensions: list[str] = []
    for state in report.states:
        source = state.lane_width_source or "unavailable"
        width_sources[source] = width_sources.get(source, 0) + 1
        reasons[state.reason or "unspecified"] = reasons.get(state.reason or "unspecified", 0) + 1
        if state.occupied is True:
            occupied += 1
        elif state.occupied is False:
            outside += 1
        else:
            unsupported += 1
        if state.actor_id in dimensions_missing:
            actors_without_dimensions.append(state.actor_id)
    return {
        "state_count": len(report.states),
        "occupied": occupied,
        "outside": outside,
        "unsupported": unsupported,
        "reasons": reasons,
        "width_sources": width_sources,
        "actors_without_dimensions": sorted(set(actors_without_dimensions)),
    }


def _corridor_view(manifest, xml_text) -> dict:
    return {
        "geometry_mode": manifest.get("geometry_mode"),
        "geometry_fitter_version": manifest.get("geometry_fitter_version"),
        "road_count": manifest.get("road_count"),
        "junction_count": manifest.get("junction_count"),
        "lane_width_source": manifest.get("lane_width_source"),
        "lane_width_source_counts": manifest.get("lane_width_source_counts"),
        "residual_statistics": manifest.get("residual_statistics"),
        "geometry_status_counts": _counts(manifest.get("geometry_status") or {}),
        "arc_geometry_elements": xml_text.count("<arc"),
    }


def _counts(values) -> dict:
    result: dict[str, int] = {}
    for value in values.values():
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _dangling_references(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    road_ids = {road.attrib["id"] for road in root.findall("road")}
    junction_ids = {junction.attrib["id"] for junction in root.findall("junction")}
    findings: list[str] = []
    for junction in root.findall("junction"):
        for connection in junction.findall("connection"):
            for link in ("incomingRoad", "connectingRoad"):
                element = connection.find(link)
                if element is not None and element.attrib.get("id") not in road_ids:
                    findings.append(f"junction {junction.attrib['id']}: {link} {element.attrib.get('id')}")
    for road in root.findall("road"):
        link = road.find("link")
        if link is None:
            continue
        for related in ("predecessor", "successor"):
            element = link.find(related)
            if element is None:
                continue
            if element.attrib.get("elementType") == "road" and element.attrib.get("elementId") not in road_ids:
                findings.append(f"road {road.attrib['id']}: {related} {element.attrib.get('elementId')}")
            if element.attrib.get("elementType") == "junction" and element.attrib.get("elementId") not in junction_ids:
                findings.append(f"road {road.attrib['id']}: {related} junction {element.attrib.get('elementId')}")
    return findings


def _dangling_links(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    road_ids = {road.attrib["id"] for road in root.findall("road")}
    findings: list[str] = []
    for road in root.findall("road"):
        link = road.find("link")
        if link is None:
            continue
        for related in ("predecessor", "successor"):
            element = link.find(related)
            if element is None or element.attrib.get("elementType") != "road":
                continue
            if element.attrib.get("elementId") not in road_ids:
                findings.append(f"road {road.attrib['id']}: {related} {element.attrib.get('elementId')}")
    return findings


def _lane_widths(xml_text: str) -> tuple[LaneWidthRecord, ...]:
    root = ET.fromstring(xml_text)
    widths = []
    for road in root.findall("road"):
        element = road.find("./lanes/laneSection/right/lane[@id='-1']/width")
        if element is None:
            continue
        value = element.attrib.get("a")
        if value is None:
            continue
        widths.append(
            LaneWidthRecord(road.attrib["id"], float(value), "generated_corridor_xodr")
        )
    return tuple(widths)


def _to_local_lane(lane, transform: RoadAlignedTransform):
    from real2scenario import LaneCenterlinePose, LaneCenterlineRecord

    poses = []
    for pose in lane.poses:
        local = transform.to_local_state(
            State(time_s=0.0, x_m=pose.x_m, y_m=pose.y_m, yaw_rad=pose.yaw_rad, speed_mps=0.0)
        )
        poses.append(LaneCenterlinePose(local.x_m, local.y_m, local.yaw_rad))
    return LaneCenterlineRecord(
        lane.lane_id,
        tuple(poses),
        source_id=lane.source_id,
        predecessor_ids=lane.predecessor_ids,
        successor_ids=lane.successor_ids,
    )


def _parent_scenario(settings, metadata_index, source_adapter, scene, args):
    imported = source_adapter.import_scene(scene["scene_token"], max_actors=args.max_actors)
    actor_tokens = tuple(
        actor_id.removeprefix("instance-") for actor_id in imported.selected_actor_ids
    )
    window = SourceWindow(
        scene["scene_token"], scene["first_sample_token"], scene["last_sample_token"]
    )
    scenario = extract_scenario(
        settings.dataset_root,
        window,
        actor_tokens,
        version=settings.dataset_version,
        tables=metadata_index.tables_for_scenes([scene["scene_token"]]),
    )
    ego = next(actor for actor in scenario.actors if actor.actor_id == scenario.ego_actor_id)
    start = ego.trajectory[0]
    return scenario, RoadAlignedTransform(
        origin_x_m=start.x_m, origin_y_m=start.y_m, heading_rad=start.yaw_rad
    )


def _run_record(run_root: Path, scene_name: str) -> dict | None:
    run_card = run_root / "benchmark-run.json"
    if not run_card.is_file():
        return None
    payload = json.loads(run_card.read_text(encoding="utf-8"))
    for scene in payload.get("scenes", []):
        if scene.get("scene_id") == scene_name:
            return scene
    return None


def _candidate_artifacts(run_root: Path, run_id: str, scenario_id: str) -> list[tuple[Path, str]]:
    return sorted(
        (path, path.parent.name)
        for path in (run_root / "runs" / run_id).glob(f"{scenario_id}--*/scenario.json")
    )


def _git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
