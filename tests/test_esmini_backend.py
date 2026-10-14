from pathlib import Path

from r2s_web.adapter import ArtifactAdapter
from r2s_web.config import WebSettings
from r2s_web.esmini import EsminiBackend


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
