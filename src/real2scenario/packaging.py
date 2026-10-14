"""Reproducibility and artifact-boundary manifests for local runs."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any, Mapping


PACKAGING_MANIFEST_VERSION = "reproducibility-manifest-v1"


def build_reproducibility_manifest(
    *,
    artifact_root: str | Path,
    files: tuple[str | Path, ...] = (),
    config: Mapping[str, Any] | None = None,
    project_version: str,
    git_commit: str,
    dataset: Mapping[str, str] | None = None,
    map_info: Mapping[str, str] | None = None,
    simulator: Mapping[str, str] | None = None,
    visibility: str = "local_private",
) -> dict[str, Any]:
    """Build a deterministic manifest without recording host-specific paths.

    ``files`` are resolved below ``artifact_root`` and represented by relative
    POSIX paths plus SHA-256/size metadata. Runtime and dataset values are
    caller-supplied because this library cannot reliably discover local tools
    or restricted dataset installations.
    """
    root = Path(artifact_root).resolve()
    if visibility not in {"public", "conditional", "local_private"}:
        raise ValueError("visibility must be public, conditional, or local_private.")
    if not project_version or not git_commit:
        raise ValueError("project_version and git_commit must not be empty.")

    file_entries: list[dict[str, Any]] = []
    for file_path in sorted((Path(item) for item in files), key=lambda item: item.as_posix()):
        resolved = (root / file_path).resolve() if not file_path.is_absolute() else file_path.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Manifest file is outside artifact_root: {file_path}") from error
        if not resolved.is_file():
            raise ValueError(f"Manifest file does not exist: {file_path}")
        file_entries.append(
            {
                "path": relative.as_posix(),
                "size_bytes": resolved.stat().st_size,
                "sha256": _sha256(resolved),
            }
        )

    normalized_config = _json_object(config or {}, "config")
    manifest = {
        "manifest_version": PACKAGING_MANIFEST_VERSION,
        "project": {"version": project_version, "git_commit": git_commit},
        "runtime": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "executable_major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "dataset": dict(sorted((dataset or {}).items())),
        "map": dict(sorted((map_info or {}).items())),
        "simulator": dict(sorted((simulator or {}).items())),
        "config": normalized_config,
        "config_sha256": _sha256_bytes(_canonical_json(normalized_config)),
        "artifact_visibility": visibility,
        "artifacts": file_entries,
    }
    return manifest


def manifest_to_json(manifest: Mapping[str, Any]) -> str:
    """Serialize a manifest deterministically for evidence or persistence."""
    return _canonical_json(manifest).decode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_object(value: Mapping[str, Any], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object.")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain JSON-safe values.") from error
    return json.loads(_canonical_json(value))
