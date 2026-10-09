"""Environment-backed configuration for the local web demo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WebSettings:
    """Project-relative paths and optional simulator configuration."""

    project_root: Path
    artifact_root: Path
    output_root: Path
    dataset_root: Path | None
    esmini_bin: str | None
    esmini_dat2csv: str | None
    dataset_version: str = "v1.0-mini"

    @classmethod
    def from_environment(cls, project_root: str | Path | None = None) -> "WebSettings":
        root = Path(project_root or os.environ.get("R2S_PROJECT_ROOT", ".")).resolve()
        artifact_root = _project_path(root, os.environ.get("R2S_ARTIFACT_ROOT", "scenarios"))
        output_root = _project_path(root, os.environ.get("R2S_OUTPUT_ROOT", "reports"))
        dataset_value = os.environ.get("NUSCENES_ROOT")
        dataset_root = (
            Path(dataset_value).resolve()
            if dataset_value
            else _default_dataset_root(root)
        )
        return cls(
            project_root=root,
            artifact_root=artifact_root,
            output_root=output_root,
            dataset_root=dataset_root,
            esmini_bin=os.environ.get("ESMINI_BIN"),
            esmini_dat2csv=os.environ.get("ESMINI_DAT2CSV"),
            dataset_version=os.environ.get("NUSCENES_VERSION", "v1.0-mini"),
        )

    def with_paths(
        self,
        *,
        artifact_root: str | Path | None = None,
        output_root: str | Path | None = None,
        dataset_root: str | Path | None = None,
        dataset_version: str | None = None,
    ) -> "WebSettings":
        """Return settings updated from paths supplied by the local UI."""
        return WebSettings(
            project_root=self.project_root,
            artifact_root=_project_path(self.project_root, str(artifact_root))
            if artifact_root is not None
            else self.artifact_root,
            output_root=_project_path(self.project_root, str(output_root))
            if output_root is not None
            else self.output_root,
            dataset_root=None
            if dataset_root == ""
            else Path(dataset_root).expanduser().resolve()
            if dataset_root is not None
            else self.dataset_root,
            esmini_bin=self.esmini_bin,
            esmini_dat2csv=self.esmini_dat2csv,
            dataset_version=dataset_version or self.dataset_version,
        )
def _project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return (project_root / path).resolve() if not path.is_absolute() else path.resolve()


def _default_dataset_root(project_root: Path) -> Path | None:
    candidate = project_root / "data" / "v1.0-mini"
    return candidate.resolve() if candidate.is_dir() else None
