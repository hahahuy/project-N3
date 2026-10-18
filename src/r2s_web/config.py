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
    esmini_lib: str | None = None
    dataset_version: str = "v1.0-trainval"
    esmini_capture_images: bool = False
    batch_max_workers: int = 1
    batch_max_pending: int = 1
    batch_accept_grace_s: float = 0.05

    def __post_init__(self) -> None:
        if self.dataset_root is not None and self.dataset_version == "v1.0-trainval":
            if not (self.dataset_root / "v1.0-trainval").is_dir() and (
                self.dataset_root / "v1.0-mini"
            ).is_dir():
                object.__setattr__(self, "dataset_version", "v1.0-mini")

    @classmethod
    def from_environment(cls, project_root: str | Path | None = None) -> "WebSettings":
        root = Path(project_root or os.environ.get("PROJECT_N3_ROOT", ".")).resolve()
        artifact_root = _project_path(root, os.environ.get("PROJECT_N3_ARTIFACT_ROOT", "scenarios"))
        output_root = _project_path(root, os.environ.get("PROJECT_N3_OUTPUT_ROOT", "reports"))
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
            esmini_lib=os.environ.get("ESMINILIB_PATH"),
            esmini_capture_images=os.environ.get("ESMINI_CAPTURE_IMAGES", "0") == "1",
            batch_max_workers=_positive_int(os.environ.get("R2S_BATCH_MAX_WORKERS", "1"), "R2S_BATCH_MAX_WORKERS"),
            batch_max_pending=_non_negative_int(os.environ.get("R2S_BATCH_MAX_PENDING", "1"), "R2S_BATCH_MAX_PENDING"),
            batch_accept_grace_s=_non_negative_float(os.environ.get("R2S_BATCH_ACCEPT_GRACE_S", "0.05"), "R2S_BATCH_ACCEPT_GRACE_S"),
        dataset_version=os.environ.get(
            "NUSCENES_VERSION",
            _default_dataset_version(dataset_root),
        ),
        )

    def with_paths(
        self,
        *,
        artifact_root: str | Path | None = None,
        output_root: str | Path | None = None,
        dataset_root: str | Path | None = None,
        dataset_version: str | None = None,
    ) -> "WebSettings":
        """Return settings updated from paths supplied by the local UI.

        Roots supplied over the API are untrusted input. Each one must resolve
        inside this project root, inside the directory it currently points at,
        or inside an explicitly configured extra root. Anything else is
        rejected, because these values are later used to read and write files.
        """
        allowed = (self.project_root, self.artifact_root, self.output_root)
        if self.dataset_root is not None:
            allowed += (self.dataset_root,)
        allowed += _extra_allowed_roots()
        return WebSettings(
            project_root=self.project_root,
            artifact_root=_confined_root(
                self.project_root, artifact_root, allowed, "artifact_root"
            )
            if artifact_root is not None
            else self.artifact_root,
            output_root=_confined_root(self.project_root, output_root, allowed, "output_root")
            if output_root is not None
            else self.output_root,
            dataset_root=None
            if dataset_root == ""
            else _confined_root(
                self.project_root, dataset_root, allowed, "dataset_root"
            )
            if dataset_root is not None
            else self.dataset_root,
            esmini_bin=self.esmini_bin,
            esmini_dat2csv=self.esmini_dat2csv,
            esmini_lib=self.esmini_lib,
            dataset_version=dataset_version or self.dataset_version,
            esmini_capture_images=self.esmini_capture_images,
        )


def _project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return (project_root / path).resolve() if not path.is_absolute() else path.resolve()


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _extra_allowed_roots() -> tuple[Path, ...]:
    """Return operator-configured roots that the local UI may select.

    ``PROJECT_N3_EXTRA_DATA_ROOTS`` is a ``os.pathsep`` separated list of directories
    the operator is willing to expose, such as a mounted nuScenes release that
    lives outside the project tree. It is read from the environment only and is
    never populated from request data.
    """
    configured = os.environ.get("PROJECT_N3_EXTRA_DATA_ROOTS", "")
    roots = []
    for value in configured.split(os.pathsep):
        if value.strip():
            roots.append(Path(value).expanduser().resolve())
    return tuple(roots)


def _confined_root(
    project_root: Path, value: str | Path, allowed: tuple[Path, ...], label: str
) -> Path:
    """Resolve ``value`` and reject roots outside every permitted location."""
    candidate = _project_path(project_root, str(value))
    if not any(_is_within(candidate, root) for root in allowed):
        permitted = ", ".join(str(root) for root in allowed)
        raise ValueError(
            f"{label} must stay inside an allowed root. Permitted roots: {permitted}."
        )
    return candidate


def _default_dataset_root(project_root: Path) -> Path | None:
    candidates = (
        Path("/mnt/backup/nuscenes"),
        project_root / "data" / "v1.0-mini",
    )
    for candidate in candidates:
        if (candidate / "v1.0-trainval").is_dir():
            return candidate.resolve()
        if (candidate / "v1.0-mini").is_dir():
            return candidate.resolve()
    return None


def _default_dataset_version(dataset_root: Path | None) -> str:
    if dataset_root is not None and (dataset_root / "v1.0-mini").is_dir():
        return "v1.0-mini"
    return "v1.0-trainval"


def _positive_int(value: str, name: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{name} must be at least 1")
    return parsed


def _non_negative_int(value: str, name: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _non_negative_float(value: str, name: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed
