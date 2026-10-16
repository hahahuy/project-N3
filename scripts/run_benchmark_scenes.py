#!/usr/bin/env python3
"""Run a provisional multi-scene nuScenes benchmark and aggregate its reports.

This executes the existing local pipeline for each scene of a scene index:
canonical import, deterministic variant generation, feasibility validation,
OpenSCENARIO export, esmini replay and the CP4 gate set. The resulting
per-scene reports are aggregated with the ``benchmark-aggregate-v1`` contract.

All outputs stay local and private. ADE/FDE, G6/G7 and the benchmark status
remain ``PROVISIONAL``; this script creates engineering evidence, not a
scientific acceptance claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from r2s_web.adapter import ArtifactAdapter
from r2s_web.config import WebSettings
from r2s_web.jobs import BatchService
from r2s_web.schemas import BatchRequest, EventDeclarationRequest
from r2s_web.source_scenes import SourceSceneAdapter, shared_metadata_index
from real2scenario import (
    METADATA_INDEX_VERSION,
    build_reproducibility_manifest,
    manifest_to_json,
)
from real2scenario.benchmark import BenchmarkRun, aggregate_benchmark_runs, benchmark_aggregate_to_dict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/mnt/backup/nuscenes"))
    parser.add_argument("--dataset-version", default="v1.0-trainval")
    parser.add_argument("--scene-index", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--max-actors", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--speed-multipliers", type=float, nargs="+", default=[0.9, 1.0])
    parser.add_argument("--initial-gap-deltas-m", type=float, nargs="+", default=[-2.0, 0.0])
    parser.add_argument("--timing-offsets-s", type=float, nargs="+", default=[0.0, 0.5, 1.0])
    parser.add_argument("--no-replay", action="store_true", help="Skip esmini replay for the run.")
    parser.add_argument(
        "--gate-evidence",
        type=Path,
        default=None,
        help=(
            "Optional JSON file with per-scene CP4 gate evidence: "
            '{"<scene_id>": {"lane_match_evidence": {"<variant_id>": {...}}, '
            '"event_declaration": {...}}}.'
        ),
    )
    args = parser.parse_args()

    esmini_bin = os.environ.get("ESMINI_BIN")
    esmini_dat2csv = os.environ.get("ESMINI_DAT2CSV")
    replay_enabled = not args.no_replay
    if replay_enabled and not (esmini_bin and esmini_dat2csv):
        raise SystemExit(
            "Replay requires ESMINI_BIN and ESMINI_DAT2CSV; use --no-replay to skip it."
        )

    index_path = args.scene_index.expanduser().resolve()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    settings = WebSettings(
        project_root=output_root,
        artifact_root=output_root / "artifacts",
        output_root=output_root / "runs",
        dataset_root=args.dataset_root.expanduser().resolve(),
        esmini_bin=esmini_bin,
        esmini_dat2csv=esmini_dat2csv,
        dataset_version=args.dataset_version,
    )
    source_adapter = SourceSceneAdapter(settings)
    batch_service = BatchService(settings, ArtifactAdapter(settings))
    metadata_index = shared_metadata_index(settings)
    gate_evidence = (
        {}
        if args.gate_evidence is None
        else json.loads(args.gate_evidence.expanduser().resolve().read_text(encoding="utf-8"))
    )
    unknown_scenes = sorted(set(gate_evidence) - {scene["name"] for scene in index["scenes"]})
    if unknown_scenes:
        raise SystemExit(f"Gate evidence references unknown scenes: {', '.join(unknown_scenes)}")

    git_revision, working_tree_clean = _git_state()
    run_cards: list[dict[str, object]] = []
    benchmark_runs: list[BenchmarkRun] = []
    for scene in index["scenes"]:
        started = time.monotonic()
        imported = source_adapter.import_scene(
            scene["scene_token"], max_actors=args.max_actors
        )
        scene_evidence = gate_evidence.get(scene["name"], {})
        lane_match_evidence = scene_evidence.get("lane_match_evidence", {})
        event_declaration = scene_evidence.get("event_declaration")
        status = batch_service.create(
            BatchRequest(
                scenario_id=imported.scenario_id,
                generation_mode="grid",
                speed_multipliers=list(args.speed_multipliers),
                initial_gap_deltas_m=list(args.initial_gap_deltas_m),
                timing_offsets_s=list(args.timing_offsets_s),
                seed=args.seed,
                replay_enabled=replay_enabled,
                lane_match_evidence=dict(lane_match_evidence),
                event_declaration=(
                    None if event_declaration is None else EventDeclarationRequest(**event_declaration)
                ),
            )
        )
        record = batch_service.get(status.job_id)
        if record.aggregate is None:
            raise SystemExit(f"Scene {scene['name']} produced no aggregate report: {status.error}")
        benchmark_runs.append(
            BenchmarkRun(
                run_id=status.job_id,
                scene_id=scene["name"],
                evidence_class="nuscenes_local",
                simulator="esmini" if replay_enabled else "none",
                report=record.aggregate,
            )
        )
        run_cards.append(
            {
                "run_id": status.job_id,
                "scene_id": scene["name"],
                "scene_token": scene["scene_token"],
                "scenario_id": imported.scenario_id,
                "status": status.status,
                "error": status.error,
                "evidence_class": "nuscenes_local",
                "simulator": "esmini" if replay_enabled else "none",
                "artifact_visibility": "local_private",
                "scientific_status": "PROVISIONAL",
                "selected_actor_count": len(imported.selected_actor_ids),
                "counts": {
                    "generated": record.aggregate.generated,
                    "valid": record.aggregate.valid,
                    "invalid": record.aggregate.invalid,
                    "simulator_failed": record.aggregate.simulator_failed,
                },
                "replay_metric_aggregate": (
                    None
                    if record.replay_metric_aggregate is None
                    else _metric_aggregate_view(record.replay_metric_aggregate)
                ),
                "gate_funnel": record.gate_funnel,
                "generation": {
                    "mode": "grid",
                    "seed": args.seed,
                    "speed_multipliers": list(args.speed_multipliers),
                    "initial_gap_deltas_m": list(args.initial_gap_deltas_m),
                    "timing_offsets_s": list(args.timing_offsets_s),
                },
                "gate_evidence": {
                    "lane_match_evidence_supplied": len(lane_match_evidence),
                    "lane_match_evidence_applied": sum(
                        result.variant_id in lane_match_evidence for result in record.results
                    ),
                    "lane_match_evidence_unused": sorted(
                        set(lane_match_evidence) - {result.variant_id for result in record.results}
                    ),
                    "event_declared": event_declaration is not None,
                },
                "runtime_s": round(time.monotonic() - started, 3),
                "git_revision": git_revision,
                "git_working_tree_clean": working_tree_clean,
                "dataset_metadata_sha256": _metadata_hashes(args.dataset_root, args.dataset_version),
                "metadata_index": metadata_index.status(),
            }
        )

    aggregate = benchmark_aggregate_to_dict(aggregate_benchmark_runs(benchmark_runs))
    run_card_path = output_root / "benchmark-run.json"
    manifest = _reproducibility_manifest(
        output_root,
        run_card_path,
        index_path,
        args,
        git_revision,
        esmini_bin,
        esmini_dat2csv,
        replay_enabled,
    )
    payload = {
        "benchmark_version": "benchmark-run-card-v1",
        "scientific_status": "PROVISIONAL",
        "selection_version": index["selection_version"],
        "selection_status": index["selection_status"],
        "owner_approval": index.get("owner_approval", "not_requested"),
        "dataset": index["dataset"],
        "artifact_visibility": "local_private",
        "runtime_status": "benchmark_run_complete",
        "metadata_index": metadata_index.status(),
        "scenes": run_cards,
        "aggregate": aggregate,
        "reproducibility": {
            "manifest_version": manifest["manifest_version"],
            "git_working_tree_clean": working_tree_clean,
            "artifact_count": len(manifest["artifacts"]),
            "config_sha256": manifest["config_sha256"],
            "manifest_path": "reproducibility-manifest.json",
        },
    }
    run_card_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path = output_root / "reproducibility-manifest.json"
    manifest_path.write_text(manifest_to_json(manifest) + "\n", encoding="utf-8")
    print(run_card_path)
    print(manifest_path)
    return 0


def _reproducibility_manifest(
    output_root: Path,
    run_card_path: Path,
    index_path: Path,
    args,
    git_revision: str,
    esmini_bin: str | None,
    esmini_dat2csv: str | None,
    replay_enabled: bool,
):
    """Build the CP5 manifest for a completed benchmark run.

    The manifest inventories run artifacts by relative path and hash only. Host
    paths, dataset locations and simulator binaries are recorded as caller
    supplied metadata, never as artifact identifiers.
    """
    inventory = tuple(
        path.relative_to(output_root).as_posix()
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path.name != "reproducibility-manifest.json"
    )
    return build_reproducibility_manifest(
        artifact_root=output_root,
        files=inventory,
        config={
            "benchmark": {
                "grid": {
                    "speed_multipliers": list(args.speed_multipliers),
                    "initial_gap_deltas_m": list(args.initial_gap_deltas_m),
                    "timing_offsets_s": list(args.timing_offsets_s),
                },
                "max_actors": args.max_actors,
                "replay_enabled": replay_enabled,
                "seed": args.seed,
            },
            "dataset_version": args.dataset_version,
            "metadata_index_version": METADATA_INDEX_VERSION,
            "scene_index_sha256": _sha256(index_path),
        },
        project_version=_project_version(),
        git_commit=git_revision,
        dataset={
            "name": "nuScenes",
            "version": args.dataset_version,
            "visibility": "local_private",
        },
        simulator={
            "requested": "esmini" if replay_enabled else "none",
            "tool_version": _esmini_version(esmini_bin) if replay_enabled else "not-used",
        },
    )


def _metric_aggregate_view(aggregate) -> dict[str, object]:
    def distribution(value) -> dict[str, float] | None:
        return None if value is None else {
            "mean": value.mean,
            "median": value.median,
            "p95": value.p95,
            "max": value.max,
        }

    return {
        "actor_count": aggregate.actor_count,
        "ade_m": distribution(aggregate.ade_m),
        "fde_m": distribution(aggregate.fde_m),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("real2scenario")
    except PackageNotFoundError:  # pragma: no cover - source checkout without install
        return "0.1.0"


def _esmini_version(esmini_bin: str | None) -> str:
    if not esmini_bin:
        return "unknown"
    try:
        result = subprocess.run(
            [esmini_bin, "--version"], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    for line in result.stdout.splitlines():
        if "GIT TAG" in line:
            return line.split(":", 1)[-1].strip()
    return "unknown"


def _metadata_hashes(dataset_root: Path, version: str) -> dict[str, str]:
    metadata = dataset_root.expanduser().resolve() / version
    digest = hashlib.sha256()
    with (metadata / "scene.json").open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"scene.json": digest.hexdigest()}


def _git_state() -> tuple[str, bool]:
    """Return the git revision and whether the working tree was clean."""
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False
    status = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    return revision, not status.strip()


def _git_revision() -> str:
    return _git_state()[0]


if __name__ == "__main__":
    sys.exit(main())
