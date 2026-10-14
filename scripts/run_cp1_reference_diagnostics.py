#!/usr/bin/env python3
"""Run private CP1 actor-reference and direction diagnostics.

The output directory is intentionally outside the repository by default. JSON
serialization is limited to diagnostic summaries and per-state heading/error
records; callers remain responsible for the visibility policy of the evidence
root.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from real2scenario import (
    SourceWindow,
    analyze_actor_reference_sensitivity,
    classify_direction_counterfactuals,
    extract_scenario,
    lane_graph_from_nuscenes,
    lane_graph_from_opendrive,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path.home() / "cp1-evidence-corridor")
    parser.add_argument("--dataset-root", type=Path, default=Path.home() / "datasets" / "nuscenes")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = args.evidence_root.expanduser().resolve()
    manifest = _read_json(root / "corridor-manifest.json")
    output = (root / "semantic-follow-up") if args.output is None else args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    scenario = extract_scenario(
        args.dataset_root,
        SourceWindow(
            manifest["source_scene_token"],
            _source_window_tokens(manifest["source_scenario_id"])[0],
            _source_window_tokens(manifest["source_scenario_id"])[1],
        ),
        tuple(_raw_instance_token(actor_id) for actor_id in manifest["selected_actor_ids"] if actor_id != "ego"),
        version=manifest["dataset_version"],
    )
    native_graph, repair_report, topology_report = lane_graph_from_nuscenes(
        str(args.dataset_root),
        map_name=manifest["map_name"],
        selected_tokens=tuple(manifest["selected_tokens"]),
        resolution_m=float(manifest["resolution_m"]),
    )
    xodr_path = root / "scene-0061-corridor.xodr"
    xodr_graph = lane_graph_from_opendrive(xodr_path.read_text(encoding="utf-8"))
    references = (("native_nuscenes", native_graph), ("generated_xodr", xodr_graph))
    sensitivity = analyze_actor_reference_sensitivity(
        scenario, references, actor_ids=tuple(manifest["selected_actor_ids"]),
    )
    direction = classify_direction_counterfactuals(
        scenario, references, actor_ids=tuple(manifest["selected_actor_ids"]),
    )

    _write_json(output / "actor-reference-sensitivity.json", sensitivity)
    _write_json(output / "direction-counterfactual.json", direction)
    _write_json(output / "native-repair-topology.json", {"repair": repair_report, "topology": topology_report})
    _write_json(output / "run-card.json", {
        "diagnostic_versions": {
            "actor_reference": sensitivity.algorithm_version,
            "direction": direction.algorithm_version,
        },
        "dataset_root": str(args.dataset_root.expanduser().resolve()),
        "dataset_version": manifest["dataset_version"],
        "map_name": manifest["map_name"],
        "scene": manifest["source_scene_name"],
        "scenario_id": scenario.scenario_id,
        "selected_actor_ids": manifest["selected_actor_ids"],
        "selected_lane_count": len(native_graph.lanes),
        "xodr_lane_count": len(xodr_graph.lanes),
        "corridor_manifest_sha256": _sha256(root / "corridor-manifest.json"),
        "xodr_sha256": _sha256(xodr_path),
        "git_revision": _git_revision(),
        "artifact_visibility": "local_private",
    })
    _write_summary(output / "comparison-summary.md", sensitivity, direction, native_graph, xodr_graph)
    print(output)
    return 0


def _write_summary(path: Path, sensitivity, direction, native_graph, xodr_graph) -> None:
    counts: dict[str, dict[str, int]] = {}
    for state in direction.states:
        counts.setdefault(state.reference_name, {})[state.classification] = counts.setdefault(state.reference_name, {}).get(state.classification, 0) + 1
    lines = [
        "# CP1 Actor Reference and Direction Diagnostic Run",
        "",
        "Status: `DIAGNOSTIC`, `PROVISIONAL`, `LOCAL_PRIVATE`",
        "",
        f"- Native lanes: {len(native_graph.lanes)}",
        f"- Generated XODR lanes: {len(xodr_graph.lanes)}",
        "- Production lane direction was not changed.",
        "- Actor-specific corrections were not applied.",
        "",
        "## Direction Classifications",
        "",
        "| Reference | Classification | Count |",
        "|---|---|---:|",
    ]
    for reference_name in sorted(counts):
        for classification, count in sorted(counts[reference_name].items()):
            lines.append(f"| {reference_name} | {classification} | {count} |")
    lines.extend(("", "## Reference Sensitivity", "", "| Hypothesis | Reference | Actor | States | Supported | Mean lateral | P95 lateral |", "|---|---|---|---:|---:|---:|---:|"))
    for row in sensitivity.rows:
        mean = "n/a" if row.mean_lateral_error_m is None else f"{row.mean_lateral_error_m:.3f}"
        p95 = "n/a" if row.p95_lateral_error_m is None else f"{row.p95_lateral_error_m:.3f}"
        lines.append(f"| {row.hypothesis} | {row.reference_name} | {row.actor_id} | {row.state_count} | {row.supported_state_count} | {mean} m | {p95} m |")
    lines.extend(("", "These results are counterfactual diagnostics only. The immutable selected-corridor baseline remains `20/143 = 13.99%`.", ""))
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _source_window_tokens(scenario_id: str) -> tuple[str, str]:
    match = re.fullmatch(r"nuscenes-[0-9a-f]{32}-([0-9a-f]{32})-([0-9a-f]{32})", scenario_id)
    if match is None:
        raise ValueError(f"Unsupported nuScenes scenario ID: {scenario_id}")
    return match.group(1), match.group(2)


def _raw_instance_token(actor_id: str) -> str:
    return actor_id.removeprefix("instance-")


def _write_json(path: Path, value) -> None:
    payload = asdict(value) if is_dataclass(value) else value
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
