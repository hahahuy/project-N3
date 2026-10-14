import json

import pytest

from real2scenario import build_reproducibility_manifest, manifest_to_json


def test_manifest_has_relative_hashed_inventory_and_stable_config_hash(tmp_path) -> None:
    artifact = tmp_path / "run.json"
    artifact.write_text('{"ok":true}\n', encoding="utf-8")

    manifest = build_reproducibility_manifest(
        artifact_root=tmp_path,
        files=(artifact,),
        config={"seed": 7, "mode": "synthetic"},
        project_version="0.1.0",
        git_commit="abc123",
        dataset={"name": "synthetic", "version": "v1"},
        map_info={"version": "template-v1"},
        simulator={"name": "none"},
    )

    assert manifest["manifest_version"] == "reproducibility-manifest-v1"
    assert manifest["artifact_visibility"] == "local_private"
    assert manifest["artifacts"] == [
        {
            "path": "run.json",
            "size_bytes": artifact.stat().st_size,
            "sha256": "e5f1eb4d806641698a35efe20e098efd20d7d57a9b90ee69079d5bb650920726",
        }
    ]
    assert manifest["config_sha256"] == build_reproducibility_manifest(
        artifact_root=tmp_path,
        config={"mode": "synthetic", "seed": 7},
        project_version="0.1.0",
        git_commit="abc123",
    )["config_sha256"]
    assert "tmp" not in manifest_to_json(manifest)
    assert json.loads(manifest_to_json(manifest)) == manifest


def test_manifest_rejects_outside_and_missing_files(tmp_path) -> None:
    outside = tmp_path.parent / "outside.json"
    outside.write_text("outside", encoding="utf-8")

    with pytest.raises(ValueError, match="outside artifact_root"):
        build_reproducibility_manifest(
            artifact_root=tmp_path,
            files=(outside,),
            project_version="0.1.0",
            git_commit="abc123",
        )
    with pytest.raises(ValueError, match="does not exist"):
        build_reproducibility_manifest(
            artifact_root=tmp_path,
            files=("missing.json",),
            project_version="0.1.0",
            git_commit="abc123",
        )


def test_manifest_rejects_invalid_visibility_and_non_json_config(tmp_path) -> None:
    with pytest.raises(ValueError, match="visibility"):
        build_reproducibility_manifest(
            artifact_root=tmp_path,
            project_version="0.1.0",
            git_commit="abc123",
            visibility="private-forever",
        )
    with pytest.raises(ValueError, match="JSON-safe"):
        build_reproducibility_manifest(
            artifact_root=tmp_path,
            project_version="0.1.0",
            git_commit="abc123",
            config={"bad": object()},
        )
