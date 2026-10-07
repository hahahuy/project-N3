"""Filesystem and metadata preflight for a local nuScenes release."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


MapMode = Literal["none", "expansion"]

REQUIRED_METADATA_FILES: tuple[str, ...] = (
    "scene.json",
    "sample.json",
    "sample_data.json",
    "sample_annotation.json",
    "instance.json",
    "ego_pose.json",
    "calibrated_sensor.json",
    "sensor.json",
    "category.json",
    "log.json",
)


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    """One actionable preflight failure."""

    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Structured result of checking one local nuScenes release."""

    dataset_root: Path
    version: str
    metadata_path: Path
    map_mode: MapMode
    checked_metadata_files: tuple[str, ...]
    issues: tuple[PreflightIssue, ...]

    @property
    def ready(self) -> bool:
        """Whether all requested metadata and map checks passed."""
        return not self.issues


def preflight_dataset(
    dataset_root: str | Path,
    *,
    version: str = "v1.0-mini",
    map_mode: MapMode = "expansion",
) -> PreflightReport:
    """Check required nuScenes metadata and an optional map expansion.

    ``dataset_root`` is the directory containing the version directory, for
    example ``/datasets/nuscenes/v1.0-mini``. This function does not import the
    nuScenes devkit and does not inspect raw sensor payloads.

    ``map_mode='expansion'`` requires the official ``map.json`` manifest and
    every raster map file it references. Use ``map_mode='none'`` for a
    metadata-only check; this is not sufficient for road-aware extraction.
    """
    if map_mode not in ("none", "expansion"):
        raise ValueError("map_mode must be either 'none' or 'expansion'.")
    if not version:
        raise ValueError("version must not be empty.")

    root = Path(dataset_root).expanduser()
    metadata_path = root / version
    issues: list[PreflightIssue] = []

    if not root.is_dir():
        issues.append(
            PreflightIssue(
                code="missing_dataset_root",
                path=str(root),
                message="Dataset root directory does not exist.",
            )
        )

    if not metadata_path.is_dir():
        issues.append(
            PreflightIssue(
                code="missing_metadata_directory",
                path=str(metadata_path),
                message=(
                    "Version directory does not exist; expected nuScenes tables "
                    "under <dataset_root>/<version>."
                ),
            )
        )

    checked_files: list[str] = []
    if metadata_path.is_dir():
        for filename in REQUIRED_METADATA_FILES:
            checked_files.append(filename)
            path = metadata_path / filename
            if not path.is_file():
                issues.append(
                    PreflightIssue(
                        code="missing_metadata_file",
                        path=str(path),
                        message=f"Required metadata table {filename} is missing.",
                    )
                )
                continue
            _check_json_file(path, issues)

    if map_mode == "expansion":
        _check_map_expansion(root, metadata_path, issues)

    return PreflightReport(
        dataset_root=root,
        version=version,
        metadata_path=metadata_path,
        map_mode=map_mode,
        checked_metadata_files=tuple(checked_files),
        issues=tuple(issues),
    )


def _check_json_file(path: Path, issues: list[PreflightIssue]) -> None:
    try:
        with path.open(encoding="utf-8") as file:
            json.load(file)
    except (OSError, UnicodeDecodeError) as error:
        issues.append(
            PreflightIssue(
                code="unreadable_metadata_file",
                path=str(path),
                message=f"Required metadata table cannot be read: {error}.",
            )
        )
    except json.JSONDecodeError as error:
        issues.append(
            PreflightIssue(
                code="invalid_metadata_json",
                path=str(path),
                message=f"Required metadata table is not valid JSON: {error.msg}.",
            )
        )


def _check_map_expansion(
    dataset_root: Path, metadata_path: Path, issues: list[PreflightIssue]
) -> None:
    map_directory = dataset_root / "maps"
    if not map_directory.is_dir():
        issues.append(
            PreflightIssue(
                code="missing_map_directory",
                path=str(map_directory),
                message=(
                    "Map expansion directory does not exist; provide licensed "
                    "nuScenes map data under <dataset_root>/maps."
                ),
            )
        )
        return

    manifest_path = metadata_path / "map.json"
    if not manifest_path.is_file():
        issues.append(
            PreflightIssue(
                code="missing_map_manifest",
                path=str(manifest_path),
                message="Required map metadata table map.json is missing.",
            )
        )
        return

    try:
        with manifest_path.open(encoding="utf-8") as file:
            records = json.load(file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        issues.append(
            PreflightIssue(
                code="invalid_map_manifest",
                path=str(manifest_path),
                message=f"Map metadata table cannot be parsed: {error}.",
            )
        )
        return

    if not isinstance(records, list):
        issues.append(
            PreflightIssue(
                code="invalid_map_manifest",
                path=str(manifest_path),
                message="Map metadata table must contain a JSON array.",
            )
        )
        return

    for index, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get("filename"), str):
            issues.append(
                PreflightIssue(
                    code="invalid_map_record",
                    path=f"{manifest_path}[{index}]",
                    message="Map record must provide a string filename.",
                )
            )
            continue
        map_path = dataset_root / record["filename"]
        if not map_path.is_file():
            issues.append(
                PreflightIssue(
                    code="missing_map_file",
                    path=str(map_path),
                    message="Map file referenced by map.json is missing.",
                )
            )


def format_report(report: PreflightReport) -> str:
    """Render a concise human-readable preflight report."""
    status = "READY" if report.ready else "NOT READY"
    lines = [
        f"{status}: nuScenes {report.version}",
        f"dataset_root: {report.dataset_root}",
        f"metadata_path: {report.metadata_path}",
        f"map_mode: {report.map_mode}",
    ]
    if report.ready:
        lines.append("All required metadata and requested map checks passed.")
    else:
        lines.append(f"issues: {len(report.issues)}")
        for issue in report.issues:
            lines.append(f"- [{issue.code}] {issue.path}: {issue.message}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the preflight command and return a shell status code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        required=True,
        type=Path,
        help="Directory containing the nuScenes version directory.",
    )
    parser.add_argument("--version", default="v1.0-mini")
    parser.add_argument("--map-mode", choices=("none", "expansion"), default="expansion")
    args = parser.parse_args(argv)

    report = preflight_dataset(args.root, version=args.version, map_mode=args.map_mode)
    print(format_report(report))
    return 0 if report.ready else 1


if __name__ == "__main__":
    sys.exit(main())
