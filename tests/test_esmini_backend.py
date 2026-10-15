from pathlib import Path

from r2s_web.adapter import ArtifactAdapter
from r2s_web.config import WebSettings
from r2s_web.esmini import EsminiBackend

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic-variant-artifact.json"


def _settings(tmp_path: Path, *, esmini: str | None = None, dat2csv: str | None = None) -> WebSettings:
    return WebSettings(
        project_root=tmp_path,
        artifact_root=tmp_path / "scenarios",
        output_root=tmp_path / "reports",
        dataset_root=None,
        esmini_bin=esmini,
        esmini_dat2csv=dat2csv,
    )


def test_capability_reports_missing_configuration(tmp_path: Path) -> None:
    backend = EsminiBackend(_settings(tmp_path), ArtifactAdapter(_settings(tmp_path)))

    capability = backend.capability()

    assert capability["configured"] is False
    assert capability["available"] is False
    assert "ESMINI_BIN" in capability["diagnostic"]


def test_capability_reports_available_fake_tools(tmp_path: Path) -> None:
    executable = tmp_path / "esmini"
    converter = tmp_path / "dat2csv"
    executable.write_text("#!/bin/sh\nprintf 'fake esmini 1.0\\n'\n")
    converter.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    converter.chmod(0o755)
    settings = _settings(tmp_path, esmini=str(executable), dat2csv=str(converter))

    capability = EsminiBackend(settings, ArtifactAdapter(settings)).capability()

    assert capability["configured"] is True
    assert capability["available"] is True
    assert "fake esmini 1.0" in capability["version"]


def test_image_frame_resolves_nested_real_capture_manifest_by_timestamp(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.artifact_root.mkdir()
    settings.output_root.mkdir()
    (settings.artifact_root / "baseline.json").write_bytes(FIXTURE.read_bytes())
    capture_root = settings.output_root / "replay-job" / "in-car"
    capture_root.mkdir(parents=True)
    (capture_root / "frame-000001.png").write_bytes(b"real-capture-artifact")
    (capture_root / "image-frames.json").write_text(
        '{"scenario_id":"synthetic-variant-001","simulator_version":"esmini-test",'
        '"tolerance_s":0.02,"frames":[{"mode":"in-car","timestamp_s":1.0,'
        '"frame_id":"frame-1","artifact":"frame-000001.png"}]}'
    )

    adapter = ArtifactAdapter(settings)
    record = adapter.get("synthetic-variant-001")
    payload = EsminiBackend(settings, adapter).image_frame(record, mode="in-car", time_s=1.01)

    assert payload["status"] == "rendered"
    assert payload["frame_id"] == "frame-1"
    assert payload["timestamp_s"] == 1.0
    assert payload["artifact"]["path"] == "reports/replay-job/in-car/frame-000001.png"
    assert payload["provenance"]["source"] == "esmini_capture_artifact"
