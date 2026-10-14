import importlib.util
import io
import sys
import tarfile
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_release.py"


def _module():
    spec = importlib.util.spec_from_file_location("verify_release", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restricted_content_scan_finds_dataset_and_sensor_artifacts(tmp_path: Path) -> None:
    verify_release = _module()
    (tmp_path / "data" / "v1.0-mini").mkdir(parents=True)
    (tmp_path / "data" / "v1.0-mini" / "v1.0-mini").write_text("{}", encoding="utf-8")
    (tmp_path / "samples.pcd").write_bytes(b"\x00")
    (tmp_path / "frame.jpg").write_bytes(b"\x00")
    (tmp_path / "README.md").write_text("clean", encoding="utf-8")

    findings = verify_release._restricted_content(tmp_path)

    assert findings == ["data/v1.0-mini", "frame.jpg", "samples.pcd"]


def test_host_path_scan_reports_file_and_line(tmp_path: Path) -> None:
    verify_release = _module()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "clean.md").write_text("no host paths here\n", encoding="utf-8")
    (docs / "dirty.md").write_text("intro\nsee /home/user/data\n", encoding="utf-8")

    findings = verify_release._host_path_findings(tmp_path)

    assert findings == ["docs/dirty.md:2"]


def test_tree_hash_is_deterministic_and_content_addressed(tmp_path: Path) -> None:
    verify_release = _module()
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("two\n", encoding="utf-8")
    first = verify_release._tree_hash(tmp_path)

    (tmp_path / "b.txt").write_text("changed\n", encoding="utf-8")
    second = verify_release._tree_hash(tmp_path)

    assert first != second
    (tmp_path / "b.txt").write_text("two\n", encoding="utf-8")
    assert verify_release._tree_hash(tmp_path) == first


def test_archive_extraction_refuses_unsafe_members(tmp_path: Path) -> None:
    verify_release = _module()
    destination = tmp_path / "out"
    destination.mkdir()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as bundle:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        bundle.addfile(info, io.BytesIO(b"x"))

    with tarfile.open(fileobj=io.BytesIO(buffer.getvalue())) as bundle:
        with pytest.raises(SystemExit, match="unsafe archive member"):
            verify_release._safe_extract(bundle, destination)

    assert not (tmp_path / "escape.txt").exists()


def test_archive_extraction_accepts_regular_files(tmp_path: Path) -> None:
    verify_release = _module()
    destination = tmp_path / "out"
    destination.mkdir()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as bundle:
        info = tarfile.TarInfo("docs/report.md")
        info.size = 5
        bundle.addfile(info, io.BytesIO(b"hello"))

    with tarfile.open(fileobj=io.BytesIO(buffer.getvalue())) as bundle:
        verify_release._safe_extract(bundle, destination)

    assert (destination / "docs" / "report.md").read_text(encoding="utf-8") == "hello"


def test_verification_command_is_recorded_without_host_paths(tmp_path: Path) -> None:
    verify_release = _module()
    record = verify_release._verification(
        [sys.executable, "-m", "pytest", "-q"], tmp_path, tmp_path
    )

    assert record["command"][0] == "python"
    assert all("/" not in part for part in record["command"])
    assert record["status"] in {"pass", "fail"}
    assert record["source_root"] == "clean_checkout"