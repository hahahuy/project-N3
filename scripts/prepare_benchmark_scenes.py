#!/usr/bin/env python3
"""Prepare private canonical artifacts for a provisional benchmark scene index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from r2s_web.config import WebSettings
from r2s_web.source_scenes import SourceSceneAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path.home() / "datasets" / "nuscenes")
    parser.add_argument("--dataset-version", default="v1.0-trainval")
    parser.add_argument("--scene-index", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--max-actors", type=int, default=3)
    args = parser.parse_args()

    index = json.loads(args.scene_index.expanduser().read_text(encoding="utf-8"))
    output_root = args.output_root.expanduser().resolve()
    settings = WebSettings(
        project_root=output_root,
        artifact_root=output_root / "artifacts",
        output_root=output_root / "reports",
        dataset_root=args.dataset_root.expanduser().resolve(),
        esmini_bin=None,
        esmini_dat2csv=None,
        dataset_version=args.dataset_version,
    )
    adapter = SourceSceneAdapter(settings)
    results = []
    for scene in index["scenes"]:
        imported = adapter.import_scene(
            scene["scene_token"],
            max_actors=args.max_actors,
        )
        results.append({
            "scene_id": scene["name"],
            "scene_token": scene["scene_token"],
            "scenario_id": imported.scenario_id,
            "selected_actor_count": len(imported.selected_actor_ids),
            "state_count": sum(actor.sample_count for actor in imported.scenario.actors),
            "artifact": imported.artifact.path,
            "status": "prepared",
        })
    run_card = {
        "run_card_version": "benchmark-preparation-v1",
        "selection_version": index["selection_version"],
        "selection_status": index["selection_status"],
        "dataset": index["dataset"],
        "scenes": results,
        "simulator": "none",
        "evidence_class": "nuscenes_local",
        "artifact_visibility": "local_private",
        "runtime_status": "prepared_only",
        "scientific_status": "PROVISIONAL",
    }
    output = output_root / "benchmark-preparation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(run_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
