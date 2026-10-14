"""Prepare a private, owner-reviewable CP1 scene corridor bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from real2scenario import SelectionConfig, SourceWindow, extract_scenario, select_interaction_actors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=Path.home() / "datasets" / "nuscenes")
    parser.add_argument("--dataset-version", default="v1.0-trainval")
    parser.add_argument("--scene", default="scene-0061")
    parser.add_argument("--map-name", default="singapore-onenorth")
    parser.add_argument("--output", type=Path, default=Path.home() / "cp1-evidence-review")
    parser.add_argument("--buffer-m", type=float, default=40.0)
    args = parser.parse_args()
    if not 30.0 <= args.buffer_m <= 50.0:
        parser.error("--buffer-m must be between 30 and 50")

    metadata = args.dataset_root / args.dataset_version
    scenes = _load(metadata / "scene.json")
    scene = _one(scenes, lambda row: row.get("name") == args.scene, f"scene {args.scene!r}")
    samples = {row["token"]: row for row in _load(metadata / "sample.json")}
    annotations = _load(metadata / "sample_annotation.json")
    instances = {row["token"]: row for row in _load(metadata / "instance.json")}
    categories = {row["token"]: row["name"] for row in _load(metadata / "category.json")}
    sample_tokens = _sample_chain(scene, samples)
    sample_set = set(sample_tokens)
    vehicle_tokens = tuple(sorted({
        annotation["instance_token"]
        for annotation in annotations
        if annotation.get("sample_token") in sample_set
        and categories.get(instances.get(annotation["instance_token"], {}).get("category_token", ""), "").startswith("vehicle.")
    }))
    source = extract_scenario(
        args.dataset_root,
        SourceWindow(scene["token"], scene["first_sample_token"], scene["last_sample_token"]),
        vehicle_tokens,
        version=args.dataset_version,
    )
    selected = select_interaction_actors(source, SelectionConfig())
    decisions = json.loads(selected.provenance["interaction_selection_decisions"])
    decision_by_actor = {item["actor_id"]: item for item in decisions}
    selected_ids = [actor.actor_id for actor in selected.actors]
    output = args.output.expanduser().resolve()
    for directory in (output, output / "baseline", output / "review", output / "exploratory"):
        directory.mkdir(parents=True, exist_ok=True)

    map_path = args.dataset_root / "maps" / "expansion" / f"{args.map_name}.json"
    run_id = f"{args.scene}-baseline-{args.buffer_m:g}m-line-v1"
    inventory = {
        "run_id": run_id,
        "scene": {"name": args.scene, "token": scene["token"], "first_sample_token": scene["first_sample_token"], "last_sample_token": scene["last_sample_token"], "sample_count": len(sample_tokens), "log_token": scene.get("log_token")},
        "dataset_version": args.dataset_version,
        "actors": [_actor_inventory(actor, decision_by_actor, selected_ids) for actor in source.actors],
        "selection": {"version": selected.provenance.get("interaction_selection_version"), "config": json.loads(selected.provenance["interaction_selection_config"]), "selected_actor_ids_including_ego": selected_ids, "decisions": decisions},
    }
    _write_json(output / "baseline" / "actor-inventory.json", inventory)
    _write_json(output / "baseline" / "scene-identity.json", {"scene": scene, "sample_tokens": sample_tokens, "map_name": args.map_name, "map_path": str(map_path), "map_sha256": _sha256(map_path), "dataset_version": args.dataset_version})
    run_card = "\n".join([
        f"run_id: {run_id}", "parent_baseline_run: null", f"git_revision: {_git_revision(Path(__file__).resolve().parents[1])}",
        f"dataset_root: {args.dataset_root}", f"dataset_version: {args.dataset_version}", f"map_name: {args.map_name}", f"map_sha256: {_sha256(map_path)}",
        f"scene_name: {args.scene}", f"scene_token: {scene['token']}", f"source_window: {scene['first_sample_token']}:{scene['last_sample_token']}",
        f"corridor_buffer_m: {args.buffer_m}", "boundary_policy: intersect_closed_trajectory_buffer_centerline_selection", "topology_closure: one_hop_incident_connectivity",
        "geometry_mode: line", "resolution_m: 5.0", "road_match_distance_m: 0.5", "road_match_heading_rad: 0.2",
        "actor_selection_method: interaction-selection-v1", f"selected_actor_ids: {json.dumps(selected_ids)}", "width_source: polygon-derived", "dimension_source: annotation-or-unsupported", "reviewer: \"\"", f"review_timestamp: {datetime.now(timezone.utc).isoformat()}", "status: diagnostic/provisional", "",
    ])
    (output / "baseline" / "run-card.yaml").write_text(run_card, encoding="utf-8")
    (output / "review" / "README.md").write_text(_review_readme(output, inventory), encoding="utf-8")
    (output / "review" / "state-review.csv").write_text("actor_id,state_index,source_record_token,classification,review_note,reviewer\n", encoding="utf-8")
    (output / "review" / "review-summary.md").write_text(_summary_template(run_id), encoding="utf-8")
    print(f"Created private CP1 review bundle: {output}")
    print(f"Scene: {args.scene} ({scene['token']})")
    print(f"Samples: {len(sample_tokens)}; vehicle candidates: {len(vehicle_tokens)}")
    print(f"Selected actors including ego: {', '.join(selected_ids)}")
    print(f"Review instructions: {output / 'review' / 'README.md'}")
    return 0


def _actor_inventory(actor, decisions, selected_ids):
    decision = decisions.get(actor.actor_id, {"decision": "selected" if actor.actor_id in selected_ids else "not-evaluated", "reason": "ego" if actor.actor_id == "ego" else "not-evaluated"})
    return {"actor_id": actor.actor_id, "actor_type": actor.actor_type, "state_count": len(actor.trajectory), "first_time_s": actor.trajectory[0].time_s, "last_time_s": actor.trajectory[-1].time_s, "length_m": actor.length_m, "width_m": actor.width_m, "automatic_decision": decision.get("decision"), "automatic_decision_reason": decision.get("reason"), "minimum_distance_m": decision.get("minimum_distance_m"), "minimum_ttc_s": decision.get("minimum_ttc_s"), "source_record_tokens": [state.source_record_token for state in actor.trajectory if state.source_record_token]}


def _review_readme(output, inventory):
    selected = inventory["selection"]["selected_actor_ids_including_ego"]
    return f"""# CP1 Manual Review Bundle

1. Open `../baseline/run-card.yaml` and fill in your name.
2. Verify `../baseline/scene-identity.json`.
3. Review every candidate in `../baseline/actor-inventory.json`.
4. Freeze the selected actors: `{', '.join(selected)}`.
5. Create private overlays showing actors, centerlines, polygons, state indexes and frame axes.
6. Add one row per state to `state-review.csv`.
7. Fill `dimension-review.json` and keep ego unsupported unless an approved envelope exists.
8. Fill `review-summary.md` before creating any exploratory actor run.

Frozen baseline: 40 m corridor, line mode, 5 m resolution, 0.5 m distance,
0.2 rad heading. Do not delete failures, guess dimensions, reverse lanes only
for failing actors, or replace the baseline with a favorable selection.

Keep all outputs under `{output}` and do not copy raw nuScenes data.
"""


def _summary_template(run_id):
    return f"""# Scene-0061 Corridor Manual Review\n\nBaseline run: `{run_id}`\n\n## Baseline\n- Selected actors:\n- States:\n- Raw match rate:\n- XODR hash:\n\n## Actor Decisions\n| Actor | Decision | Evidence | Impact |\n|---|---|---|---|\n\n## State Failure Classes\n| Class | Count | Notes |\n|---|---:|---|\n\n## Direction Review\n- Reverse candidates:\n- Evidence strength:\n- Production policy changed: no\n\n## Occupancy Review\n- Occupied:\n- Outside:\n- Unsupported:\n- Width source:\n- Dimension source:\n\n## Decision\n- Baseline retained: yes\n- CP1 corridor acceptance: not claimed\n- Next technical action:\n\n## Non-claims\n- No G3 acceptance.\n- No CARLA compatibility.\n- No CP2/same-XOSC claim.\n"""


def _sample_chain(scene, samples):
    result = []
    current = scene["first_sample_token"]
    while current:
        result.append(current)
        if current == scene["last_sample_token"]:
            return result
        current = samples[current]["next"]
    raise ValueError("scene sample chain did not reach last_sample_token")


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _one(rows, predicate, label):
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {label}; found {len(matches)}.")
    return matches[0]


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision(root):
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
