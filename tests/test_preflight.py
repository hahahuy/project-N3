import json
from pathlib import Path

import pytest

from real2scenario.preflight import (
    REQUIRED_METADATA_FILES,
    format_report,
    main,
    preflight_dataset,
)


def _write_metadata(root: Path, version: str = "v1.0-mini") -> Path:
    metadata = root / version
    metadata.mkdir(parents=True)
    for filename in REQUIRED_METADATA_FILES:
        (metadata / filename).write_text("[]", encoding="utf-8")
    return metadata


def test_preflight_accepts_complete_metadata_and_map_fixture(tmp_path: Path) -> None:
    _write_metadata(tmp_path)
    (tmp_path / "maps" / "expansion").mkdir(parents=True)
    (tmp_path / "maps" / "expansion" / "map.json").write_text(
        json.dumps({"maps": []}), encoding="utf-8"
    )

    report = preflight_dataset(tmp_path)

    assert report.ready
    assert report.issues == ()
    assert "READY" in format_report(report)


def test_preflight_reports_missing_metadata_and_map(tmp_path: Path) -> None:
    dataset_root = tmp_path / "missing-dataset"
    report = preflight_dataset(dataset_root)

    codes = {issue.code for issue in report.issues}
    assert not report.ready
    assert "missing_dataset_root" in codes
    assert "missing_metadata_directory" in codes
    assert "missing_map_directory" in codes


def test_preflight_reports_missing_file_and_invalid_json(tmp_path: Path) -> None:
    metadata = _write_metadata(tmp_path)
    (metadata / "sample.json").unlink()
    (metadata / "scene.json").write_text("{invalid", encoding="utf-8")

    report = preflight_dataset(tmp_path, map_mode="none")

    assert {issue.code for issue in report.issues} == {
        "missing_metadata_file",
        "invalid_metadata_json",
    }
    assert any(issue.path.endswith("sample.json") for issue in report.issues)
    assert any(issue.path.endswith("scene.json") for issue in report.issues)


def test_preflight_requires_map_json_when_map_directory_exists(tmp_path: Path) -> None:
    _write_metadata(tmp_path)
    (tmp_path / "maps").mkdir()

    report = preflight_dataset(tmp_path)

    assert not report.ready
    assert [issue.code for issue in report.issues] == ["missing_map_json"]


def test_preflight_can_explicitly_skip_map_check(tmp_path: Path) -> None:
    _write_metadata(tmp_path)

    report = preflight_dataset(tmp_path, map_mode="none")

    assert report.ready


def test_preflight_rejects_unknown_map_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="map_mode"):
        preflight_dataset(tmp_path, map_mode="unsupported")  # type: ignore[arg-type]


def test_preflight_cli_returns_failure_for_incomplete_dataset(tmp_path: Path, capsys) -> None:
    exit_code = main(["--root", str(tmp_path), "--map-mode", "none"])

    assert exit_code == 1
    assert "NOT READY" in capsys.readouterr().out
