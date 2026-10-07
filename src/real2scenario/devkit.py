"""Optional nuScenes-devkit commands for onboarding data inspection."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def inventory_dataset(dataroot: Path, version: str) -> dict[str, Any]:
    """Return a JSON-safe inventory summary from a complete nuScenes release."""
    nusc = _load_nuscenes(dataroot, version)
    return {
        "dataset_root": str(dataroot),
        "dataset_version": version,
        "table_counts": {
            "category": len(nusc.category),
            "instance": len(nusc.instance),
            "scene": len(nusc.scene),
            "sample": len(nusc.sample),
            "sample_annotation": len(nusc.sample_annotation),
            "sample_data": len(nusc.sample_data),
            "ego_pose": len(nusc.ego_pose),
            "calibrated_sensor": len(nusc.calibrated_sensor),
            "sensor": len(nusc.sensor),
            "log": len(nusc.log),
            "map": len(nusc.map),
        },
        "scenes": [
            {
                "name": scene["name"],
                "token": scene["token"],
                "sample_count": scene["nbr_samples"],
                "first_sample_token": scene["first_sample_token"],
                "last_sample_token": scene["last_sample_token"],
                "log_token": scene["log_token"],
            }
            for scene in nusc.scene
        ],
    }


def render_sample(
    dataroot: Path,
    version: str,
    output_path: Path,
    *,
    scene_index: int | None = None,
    sample_token: str | None = None,
) -> str:
    """Render one source sample and return the selected sample token."""
    if (scene_index is None) == (sample_token is None):
        raise ValueError("Provide exactly one of scene_index or sample_token.")

    nusc = _load_nuscenes(dataroot, version)
    if scene_index is not None:
        if scene_index < 0 or scene_index >= len(nusc.scene):
            raise ValueError(
                f"scene_index {scene_index} is out of range for {len(nusc.scene)} scenes."
            )
        sample_token = nusc.scene[scene_index]["first_sample_token"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    nusc.render_sample(sample_token, out_path=str(output_path), verbose=False)
    return sample_token


def _load_nuscenes(dataroot: Path, version: str) -> Any:
    os.environ.setdefault("MPLBACKEND", "Agg")
    try:
        from nuscenes.nuscenes import NuScenes
    except ImportError as error:
        raise RuntimeError(
            "nuscenes-devkit is not installed. Install the project with the "
            "'devkit' extra: pip install -e '.[dev,devkit]'."
        ) from error

    try:
        return NuScenes(version=version, dataroot=str(dataroot), verbose=False)
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Unable to load nuScenes. Verify that dataroot contains the complete "
            f"licensed {version} release, including metadata tables, maps, and the "
            "raw sensor files needed for rendering."
        ) from error


def _write_json(payload: dict[str, Any], output_path: Path | None) -> None:
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_path is None:
        print(content, end="")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote inventory to {output_path}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run inventory or sample-rendering for a local nuScenes release."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="nuScenes dataroot.")
    parser.add_argument("--version", default="v1.0-mini")
    commands = parser.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser("inventory", help="Write table and scene inventory JSON.")
    inventory.add_argument("--output", type=Path, help="Optional JSON output path.")

    render = commands.add_parser("render", help="Render one scene's first sample or a sample token.")
    selector = render.add_mutually_exclusive_group(required=True)
    selector.add_argument("--scene-index", type=int)
    selector.add_argument("--sample-token")
    render.add_argument("--output", required=True, type=Path, help="PNG output path.")

    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            _write_json(inventory_dataset(args.root, args.version), args.output)
        else:
            token = render_sample(
                args.root,
                args.version,
                args.output,
                scene_index=args.scene_index,
                sample_token=args.sample_token,
            )
            print(f"Rendered sample {token} to {args.output}")
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
