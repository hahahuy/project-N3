"""Focused esmini capability discovery and asynchronous replay service."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from real2scenario import (
    EsminiConfig,
    compute_scenario_replay_metrics,
    select_opendrive_template,
    STRAIGHT_ROAD_TOPOLOGY,
    write_openscenario,
    run_esmini,
    artifact_from_json,
    baseline_artifact_to_dict,
)
from real2scenario.visualization import save_replay_overlay

from .adapter import ArtifactAdapter
from .config import WebSettings


@dataclass(slots=True)
class ReplayJob:
    job_id: str
    scenario_id: str
    status: str = "queued"
    error: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    tool_version: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, object] = field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None


class EsminiBackend:
    """Run one selected scenario through the local esmini toolchain."""

    def __init__(self, settings: WebSettings, adapter: ArtifactAdapter):
        self.settings = settings
        self.adapter = adapter
        self.jobs: dict[str, ReplayJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="esmini")
        self._lock = threading.Lock()

    def capability(self) -> dict[str, object]:
        executable = self.settings.esmini_bin
        converter = self.settings.esmini_dat2csv
        executable_path = _path_exists(executable)
        converter_path = _path_exists(converter)
        version = _probe_version(executable) if executable_path else None
        reasons: list[str] = []
        if not executable:
            reasons.append("ESMINI_BIN is not configured.")
        elif not executable_path:
            reasons.append("Configured esmini executable is not readable.")
        if not converter:
            reasons.append("ESMINI_DAT2CSV is not configured.")
        elif not converter_path:
            reasons.append("Configured dat2csv executable is not readable.")
        return {
            "configured": bool(executable and converter),
            "available": executable_path and converter_path,
            "executable": executable,
            "trace_converter": converter,
            "version": version,
            "diagnostic": "Available." if not reasons else " ".join(reasons),
        }

    def submit(self, scenario_id: str) -> ReplayJob:
        job = ReplayJob(job_id=f"replay-{uuid.uuid4().hex[:12]}", scenario_id=scenario_id)
        with self._lock:
            self.jobs[job.job_id] = job
        self._executor.submit(self._run, job)
        return job

    def get(self, job_id: str) -> ReplayJob:
        try:
            return self.jobs[job_id]
        except KeyError as error:
            raise KeyError(f"Replay job {job_id!r} was not found.") from error

    def image_frame(self, record, *, mode: str, time_s: float) -> dict[str, object]:
        """Resolve a real private capture manifest; never use a transform as an image."""
        if mode not in {"third-person", "in-car"}:
            raise ValueError("Unsupported POV mode.")
        manifests = sorted(self.settings.output_root.glob("replay-*/image-frames.json"))
        for manifest_path in manifests:
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if payload.get("scenario_id") != record.scenario.scenario_id:
                continue
            for frame in payload.get("frames", ()):
                if frame.get("mode") != mode:
                    continue
                timestamp = frame.get("timestamp_s")
                artifact = frame.get("artifact")
                if not isinstance(timestamp, (int, float)) or not isinstance(artifact, str):
                    continue
                artifact_path = (manifest_path.parent / artifact).resolve()
                if not artifact_path.is_file() or self.settings.output_root not in artifact_path.parents:
                    continue
                if abs(float(timestamp) - time_s) > float(payload.get("tolerance_s", 0.05)):
                    continue
                relative = _relative(self.settings.project_root, artifact_path)
                return {
                    "contract_version": "workspace-pov-image-v1",
                    "scenario_id": record.scenario.scenario_id,
                    "mode": mode,
                    "status": "rendered",
                    "frame_id": str(frame.get("frame_id") or artifact_path.stem),
                    "timestamp_s": float(timestamp),
                    "simulator": "esmini",
                    "simulator_version": str(payload.get("simulator_version") or "unknown"),
                    "artifact": {"kind": "esmini-image-frame", "path": relative, "url": f"/api/artifacts/{relative}"},
                    "unavailable_reason": None,
                    "provenance": {
                        "manifest": _relative(self.settings.project_root, manifest_path),
                        "artifact_visibility": "local_private",
                        "source": "esmini_capture_artifact",
                    },
                }
        return {
            "contract_version": "workspace-pov-image-v1",
            "scenario_id": record.scenario.scenario_id,
            "mode": mode,
            "status": "unavailable",
            "frame_id": None,
            "timestamp_s": None,
            "simulator": "esmini",
            "simulator_version": None,
            "artifact": None,
            "unavailable_reason": "esmini_image_capture_artifact_unavailable",
            "provenance": {"artifact_visibility": "local_private"},
        }

    def _run(self, job: ReplayJob) -> None:
        job.status = "running"
        job.started_at = _now()
        job_root = self.settings.output_root / job.job_id
        try:
            record = self.adapter.get(job.scenario_id)
            scenario = record.scenario
            selected, template = select_opendrive_template(
                scenario, topology=STRAIGHT_ROAD_TOPOLOGY
            )
            job_root.mkdir(parents=True, exist_ok=True)
            scenario_path = job_root / "scenario.json"
            scenario_path.write_text(
                json.dumps(baseline_artifact_to_dict(selected), sort_keys=True),
                encoding="utf-8",
            )
            xosc_path = write_openscenario(selected, template, job_root / "scenario.xosc")
            trace_path = job_root / "replay.csv"
            (job_root / "stdout.log").touch()
            (job_root / "stderr.log").touch()
            report = run_esmini(
                xosc_path,
                trace_path,
                EsminiConfig(
                    executable=self.settings.esmini_bin,
                    trace_converter=self.settings.esmini_dat2csv,
                    capture_images=self.settings.esmini_capture_images,
                ),
            )
            job.tool_version = report.tool_version
            job.failure_code = report.failure_code
            job.failure_message = report.failure_message
            job.exit_code = report.exit_code
            job.timed_out = report.timed_out
            job.stdout = report.stdout
            job.stderr = report.stderr
            (job_root / "stdout.log").write_text(report.stdout, encoding="utf-8")
            (job_root / "stderr.log").write_text(report.stderr, encoding="utf-8")
            job.artifacts = _artifact_paths(self.settings.project_root, job_root, xosc_path, trace_path)
            if not report.completed or report.trace is None:
                job.status = "timed-out" if report.timed_out else "failed"
                job.failure_message = report.failure_message or report.stderr.strip() or "esmini replay did not complete."
                job.error = job.failure_message
            else:
                _write_image_manifest(
                    self.settings.project_root, job_root, scenario, report.trace, mode="third-person"
                )
                if self.settings.esmini_capture_images:
                    self._capture_additional_mode(job_root, scenario, mode="in-car")
                job.metrics = {
                    actor_id: metrics.__dict__ if hasattr(metrics, "__dict__") else {
                        key: getattr(metrics, key)
                        for key in (
                            "sample_count",
                            "alignment_method",
                            "position_rmse_m",
                            "final_displacement_m",
                            "heading_mae_rad",
                            "speed_mae_mps",
                            "ade_m",
                            "fde_m",
                            "coverage_status",
                        )
                    }
                    for actor_id, metrics in compute_scenario_replay_metrics(selected, report.trace).items()
                }
                overlay = job_root / "replay-overlay.png"
                save_replay_overlay(selected, report.trace, overlay)
                job.artifacts["overlay"] = _relative(self.settings.project_root, overlay)
                job.status = "completed"
        except (OSError, ValueError, KeyError) as error:
            job.status = "failed"
            job.failure_code = _failure_code(error)
            job.failure_message = str(error)
            job.error = str(error)
        finally:
            job.finished_at = _now()

    def _capture_additional_mode(self, job_root: Path, scenario, *, mode: str) -> None:
        """Capture the second real camera mode without changing replay status."""
        mode_root = job_root / mode
        mode_root.mkdir(parents=True, exist_ok=True)
        try:
            selected, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)
            xosc_path = write_openscenario(selected, template, mode_root / "scenario.xosc")
            report = run_esmini(
                xosc_path,
                mode_root / "replay.csv",
                EsminiConfig(
                    executable=self.settings.esmini_bin,
                    trace_converter=self.settings.esmini_dat2csv,
                    capture_images=True,
                    camera_mode="driver",
                ),
            )
            if report.completed and report.trace is not None:
                _write_image_manifest(
                    self.settings.project_root, mode_root, scenario, report.trace, mode=mode
                )
        except (OSError, ValueError, KeyError):
            return


def _path_exists(value: str | None) -> bool:
    return bool(value and Path(value).is_file())


def _probe_version(executable: str) -> str | None:
    import subprocess
    try:
        result = subprocess.run((executable, "--version"), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (result.stdout.strip() or result.stderr.strip()) or None


def _artifact_paths(root: Path, job_root: Path, xosc: Path, trace: Path) -> dict[str, str]:
    return {
        "openscenario": _relative(root, xosc),
        "opendrive": _relative(root, job_root / "straight-two-lane-v1.xodr"),
        "replay-trace": _relative(root, trace),
        "stdout": _relative(root, job_root / "stdout.log"),
        "stderr": _relative(root, job_root / "stderr.log"),
    }


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _failure_code(error: Exception) -> str:
    message = str(error).lower()
    if "template" in message or "scenario" in message:
        return "missing_opendrive_template_or_scenario"
    return "replay_setup_failed"


def _write_image_manifest(root: Path, job_root: Path, scenario, trace, *, mode: str) -> None:
    """Index only image files that esmini actually emitted during this replay."""
    image_paths = sorted(
        path for path in job_root.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not image_paths:
        return
    timestamps = sorted({state.state.time_s for state in trace.states})
    if len(image_paths) != len(timestamps):
        return
    manifest = {
        "contract_version": "workspace-pov-image-v1",
        "scenario_id": scenario.scenario_id,
        "simulator": "esmini",
        "simulator_version": "configured-esmini",
        "tolerance_s": 0.05,
        "frames": [
            {
                "frame_id": f"{scenario.scenario_id}:esmini:{index:06d}",
                "mode": mode,
                "timestamp_s": timestamp,
                "artifact": image_path.name,
            }
            for index, (image_path, timestamp) in enumerate(zip(image_paths, timestamps))
        ],
        "artifact_visibility": "local_private",
    }
    (job_root / "image-frames.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
