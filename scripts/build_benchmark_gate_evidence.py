#!/usr/bin/env python3
"""Build CP1 lane road-match evidence for benchmark candidates (G3 input).

For every scene of a completed benchmark run this script builds the declared
scene-local corridor around the parent actor paths, expresses the corridor
centerlines in the same local road-aligned frame as the generated candidates,
and runs the existing lane road-match diagnostic per candidate. The result is
written as ``lane-road-match-evidence-v1`` records in the gate-evidence format
consumed by ``scripts/run_benchmark_scenes.py --gate-evidence``.

The corridor contract, matcher tolerances, provisional 95% reference and the
CP1 actor scope are unchanged. Nothing here repairs a match, reinterprets ground
truth or selects lanes to raise a rate; every candidate is measured, including
the candidates that fail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from r2s_web.config import WebSettings
from r2s_web.source_scenes import SourceSceneAdapter, shared_metadata_index
from real2scenario import (
    LaneCenterlinePose,
    LaneCenterlineRecord,
    LaneRoadMatchConfig,
    RoadAlignedTransform,
    SourceWindow,
    State,
    build_scene_local_corridor,
    diagnose_lane_road_match,
    extract_scenario,
    lane_centerlines_from_opendrive,
    lane_road_match_evidence_from_report,
    lane_road_match_evidence_to_dict,
    artifact_from_json,
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

    payload: dict[str, dict[str, object]] = {}
    summaries: list[dict[str, object]] = []
    for scene in scenes:
        scene_name = scene["name"]
        run_record = _run_record(run_root, scene_name)
        if run_record is None:
            summaries.append({"scene_id": scene_name, "status": "no-run-artifacts"})
            continue
        scenario_id = str(run_record["scenario_id"])
        parent, transform = _parent_scenario(settings, metadata_index, source_adapter, scene, args)
        corridor_path = corridor_root / f"{scene_name}-corridor.xodr"
        corridor = build_scene_local_corridor(
            settings.dataset_root,
            parent,
            output_path=corridor_path,
            map_name=args.map_name,
            buffer_m=args.buffer_m,
            resolution_m=args.resolution_m,
            selected_actor_ids=tuple(actor.actor_id for actor in parent.actors),
        )
        lanes = tuple(
            _to_local_lane(lane, transform)
            for lane in lane_centerlines_from_opendrive(
                corridor_path.read_text(encoding="utf-8")
            )
        )

        evidence: dict[str, object] = {}
        candidates: list[dict[str, object]] = []
        for variant_path, variant_id in _candidate_artifacts(
            run_root, str(run_record["run_id"]), scenario_id
        ):
            variant, _parent_id, _config = artifact_from_json(
                variant_path.read_text(encoding="utf-8")
            )
            report = diagnose_lane_road_match(
                variant,
                lanes,
                lane_coordinate_frame=variant.coordinate_frame,
                actor_ids=tuple(actor.actor_id for actor in variant.actors),
            )
            evidence[variant_id] = lane_road_match_evidence_to_dict(
                lane_road_match_evidence_from_report(report)
            )
            candidates.append(
                {
                    "variant_id": variant_id,
                    "state_count": report.overall.state_count,
                    "matched_state_count": report.overall.matched_state_count,
                    "raw_match_rate": report.overall.raw_match_rate,
                    "provisional_95_status": report.overall.provisional_95_status,
                    "per_actor_raw_match_rate": {
                        item.actor_id: item.summary.raw_match_rate for item in report.per_actor
                    },
                }
            )
        if evidence:
            payload[scene_name] = {"lane_match_evidence": evidence}
        summaries.append(
            {
                "scene_id": scene_name,
                "status": "evidence-built" if evidence else "no-candidates",
                "scenario_id": scenario_id,
                "run_id": run_record["run_id"],
                "selected_actor_ids": [actor.actor_id for actor in parent.actors],
                "corridor": {
                    "selected_lane_count": len(corridor.get("selected_tokens", ())),
                    "road_count": corridor.get("road_count"),
                    "junction_count": corridor.get("junction_count"),
                    "buffer_m": args.buffer_m,
                    "map_name": args.map_name,
                },
                "lane_count_in_local_frame": len(lanes),
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )

    run_card = {
        "gate_evidence_version": "benchmark-gate-evidence-v1",
        "source": "cp1_scene_local_corridor_lane_road_match",
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
        "matcher": {
            "algorithm_version": "lane-road-match-v1",
            "max_distance_m": LaneRoadMatchConfig().max_distance_m,
            "max_heading_error_rad": LaneRoadMatchConfig().max_heading_error_rad,
        },
        "scenes": summaries,
    }
    if args.dry_run:
        print(json.dumps(run_card, indent=2, sort_keys=True))
        return 0
    evidence_path = evidence_root / "gate-evidence.json"
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (evidence_root / "gate-evidence-run-card.json").write_text(
        json.dumps(run_card, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(evidence_path)
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the run card without writing gate evidence.",
    )
    return parser.parse_args()


def _parent_scenario(settings, metadata_index, source_adapter, scene, args):
    """Return the parent scenario in global coordinates and its local transform."""
    imported = source_adapter.import_scene(
        scene["scene_token"], max_actors=args.max_actors
    )
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
    ego = next(
        actor for actor in scenario.actors if actor.actor_id == scenario.ego_actor_id
    )
    start = ego.trajectory[0]
    return scenario, RoadAlignedTransform(
        origin_x_m=start.x_m, origin_y_m=start.y_m, heading_rad=start.yaw_rad
    )


def _to_local_lane(lane: LaneCenterlineRecord, transform: RoadAlignedTransform):
    """Express one corridor centerline in the candidates' local road-aligned frame."""
    poses = tuple(
        _local_pose(pose, transform) for pose in lane.poses
    )
    return LaneCenterlineRecord(
        lane.lane_id,
        poses,
        source_id=lane.source_id,
        predecessor_ids=lane.predecessor_ids,
        successor_ids=lane.successor_ids,
    )


def _local_pose(pose: LaneCenterlinePose, transform: RoadAlignedTransform) -> LaneCenterlinePose:
    local = transform.to_local_state(
        State(time_s=0.0, x_m=pose.x_m, y_m=pose.y_m, yaw_rad=pose.yaw_rad, speed_mps=0.0)
    )
    return LaneCenterlinePose(local.x_m, local.y_m, local.yaw_rad)


def _run_record(run_root: Path, scene_name: str) -> dict | None:
    """Return the run card entry that produced this scene's candidates."""
    run_card = run_root / "benchmark-run.json"
    if not run_card.is_file():
        return None
    payload = json.loads(run_card.read_text(encoding="utf-8"))
    for scene in payload.get("scenes", []):
        if scene.get("scene_id") == scene_name:
            return scene
    return None


def _candidate_artifacts(run_root: Path, run_id: str, scenario_id: str) -> list[tuple[Path, str]]:
    """Return only the candidate artifacts produced by this scene's recorded run."""
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
