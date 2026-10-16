#!/usr/bin/env python3
"""Select a deterministic provisional benchmark scene index from metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


SELECTION_VERSION = "agent-selected-scenes-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("/mnt/backup/nuscenes"))
    parser.add_argument("--dataset-version", default="v1.0-trainval")
    parser.add_argument("--location", default="singapore-onenorth")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.count <= 0:
        raise ValueError("count must be positive")

    metadata = args.dataset_root.expanduser().resolve() / args.dataset_version
    logs = _load(metadata / "log.json")
    scenes = _load(metadata / "scene.json")
    log_by_token = {item["token"]: item for item in logs}
    candidates = [
        item for item in scenes
        if log_by_token.get(item.get("log_token"), {}).get("location") == args.location
    ]
    candidates.sort(key=lambda item: (-_sample_count(item), item["token"]))
    selected = candidates[: args.count]
    if len(selected) < args.count:
        raise ValueError(f"Only {len(selected)} scenes match location {args.location!r}.")

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "selection_version": SELECTION_VERSION,
        "selection_status": "agent-selected/provisional",
        "dataset": {"name": "nuScenes", "version": args.dataset_version, "location": args.location},
        "policy": "largest sample_count descending, token ascending tie-break",
        "count": len(selected),
        "git_revision": _git_revision(),
        "metadata_hashes": {
            name: _sha256(metadata / name)
            for name in ("scene.json", "log.json")
        },
        "scenes": [
            {
                "scene_token": item["token"],
                "name": item.get("name", item["token"]),
                "description": item.get("description", ""),
                "sample_count": _sample_count(item),
                "first_sample_token": item["first_sample_token"],
                "last_sample_token": item["last_sample_token"],
                "log_token": item["log_token"],
            }
            for item in selected
        ],
        "artifact_visibility": "local_private",
        "owner_approval": "not_requested",
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


def _load(path: Path) -> list[dict[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Expected JSON array of objects: {path}")
    return value


def _sample_count(scene: dict[str, object]) -> int:
    value = scene.get("nbr_samples", 0)
    return int(value) if isinstance(value, int) else 0


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
