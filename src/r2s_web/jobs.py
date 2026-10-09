"""Bounded in-process batch orchestration for the local demo."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from real2scenario import (
    FeasibilityLimits,
    RoadBoundary,
    VariantReport,
    aggregate_report,
    aggregate_report_to_dict,
    batch_manifest_to_dict,
    generate_grid_variants,
    generate_random_variants,
    rank_scenario,
    validate_feasibility,
    variant_artifact_to_dict,
    variant_report_to_dict,
    write_aggregate_csv,
    write_aggregate_json,
    write_openscenario,
    run_esmini,
    EsminiConfig,
    compute_scenario_replay_metrics,
    select_opendrive_template,
    STRAIGHT_ROAD_TOPOLOGY,
    artifact_from_json,
)

from .adapter import ArtifactAdapter
from .config import WebSettings
from .schemas import (
    ArtifactLink,
    BatchRequest,
    BatchResults,
    JobStatus,
    ReplayMetricView,
    RankingFeatureView,
    RankingView,
    ScoreBreakdownView,
    ValidationReasonView,
    ValidationView,
    VariantResult,
)


@dataclass(slots=True)
class JobRecord:
    status: JobStatus
    manifest: dict[str, object] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    results: list[VariantResult] = field(default_factory=list)


class BatchService:
    def __init__(self, settings: WebSettings, adapter: ArtifactAdapter):
        self.settings = settings
        self.adapter = adapter
        self.jobs: dict[str, JobRecord] = {}

    def create(self, request: BatchRequest) -> JobStatus:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        status = JobStatus(job_id=job_id, status="running", scenario_id=request.scenario_id)
        record = JobRecord(status=status)
        self.jobs[job_id] = record
        try:
            self._run(record, request)
        except (OSError, ValueError, KeyError) as error:
            record.status = status.model_copy(update={"status": "failed", "error": str(error)})
        return record.status

    def get(self, job_id: str) -> JobRecord:
        try:
            return self.jobs[job_id]
        except KeyError as error:
            raise KeyError(f"Batch job {job_id!r} was not found.") from error

    def _run(self, record: JobRecord, request: BatchRequest) -> None:
        parent = self.adapter.get(request.scenario_id)
        if request.generation_mode == "grid":
            variants, manifest = generate_grid_variants(
                parent.scenario,
                speed_multipliers=request.speed_multipliers,
                initial_gap_deltas_m=request.initial_gap_deltas_m,
                timing_offsets_s=request.timing_offsets_s,
                seed=request.seed,
            )
        else:
            variants, manifest = generate_random_variants(
                parent.scenario,
                count=request.count,
                speed_multiplier_range=request.speed_multiplier_range,
                initial_gap_delta_range_m=request.initial_gap_delta_range_m,
                timing_offset_range_s=request.timing_offset_range_s,
                seed=request.seed,
            )

        job_root = self.settings.output_root / record.status.job_id
        result_models: list[VariantResult] = []
        reports: list[VariantReport] = []
        for variant, config in zip(variants, manifest.configurations):
            result, report = self._process_variant(
                parent.scenario,
                variant,
                config,
                job_root,
                request.replay_enabled,
                request.validation_limits,
            )
            result_models.append(result)
            reports.append(report)
        aggregate = aggregate_report(parent.scenario.scenario_id, tuple(reports))
        job_root.mkdir(parents=True, exist_ok=True)
        write_aggregate_json(aggregate, job_root / "aggregate.json")
        write_aggregate_csv(aggregate, job_root / "aggregate.csv")
        (job_root / "manifest.json").write_text(
            json.dumps(batch_manifest_to_dict(manifest), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        record.manifest = batch_manifest_to_dict(manifest)
        record.counts = {
            "generated": aggregate.generated,
            "valid": aggregate.valid,
            "invalid": aggregate.invalid,
            "simulator_failed": aggregate.simulator_failed,
        }
        record.results = result_models
        record.status = record.status.model_copy(
            update={
                "status": "completed",
                "generated": aggregate.generated,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _process_variant(
        self, parent, variant, config, job_root, replay_enabled, validation_limits
    ):
        variant_root = job_root / variant.scenario_id
        variant_root.mkdir(parents=True, exist_ok=True)
        scenario_relative = _relative(self.settings.project_root, variant_root / "scenario.json")
        report_relative = _relative(self.settings.project_root, variant_root / "report.json")
        (variant_root / "scenario.json").write_text(
            json.dumps(variant_artifact_to_dict(variant, parent.scenario_id, config), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        boundary = validation_limits.road_boundary
        limits = FeasibilityLimits(
            max_acceleration_mps2=validation_limits.max_acceleration_mps2,
            max_deceleration_mps2=validation_limits.max_deceleration_mps2,
            max_jerk_mps3=validation_limits.max_jerk_mps3,
            max_yaw_rate_rps=validation_limits.max_yaw_rate_rps,
            road_boundary=None
            if boundary is None
            else RoadBoundary(
                min_x_m=boundary.min_x_m,
                max_x_m=boundary.max_x_m,
                min_y_m=boundary.min_y_m,
                max_y_m=boundary.max_y_m,
            ),
        )
        validation = validate_feasibility(variant, limits)
        ranking = rank_scenario(variant, validation, parent_scenario=parent)
        status = "valid" if validation.valid else "invalid"
        xosc_relative = None
        trace_relative = None
        replay_metrics = {}
        simulator_error = None
        replay_failure = None
        ranking_for_report = ranking if validation.valid else None

        if validation.valid and replay_enabled:
            try:
                if not self.settings.esmini_bin or not self.settings.esmini_dat2csv:
                    raise ValueError(
                        "Replay requested but ESMINI_BIN and ESMINI_DAT2CSV are not configured."
                    )
                selected, template = select_opendrive_template(
                    variant, topology=STRAIGHT_ROAD_TOPOLOGY
                )
                xosc_path = write_openscenario(selected, template, variant_root / "scenario.xosc")
                xosc_relative = _relative(self.settings.project_root, xosc_path)
                replay_path = variant_root / "replay.csv"
                replay = run_esmini(
                    xosc_path,
                    replay_path,
                    EsminiConfig(
                        executable=self.settings.esmini_bin,
                        trace_converter=self.settings.esmini_dat2csv,
                    ),
                )
                if not replay.completed or replay.trace is None:
                    status = "simulator-failed"
                    simulator_error = _replay_error(replay)
                    replay_failure = {
                        "exit_code": replay.exit_code,
                        "timed_out": replay.timed_out,
                        "tool_version": replay.tool_version,
                        "stderr": replay.stderr,
                        "trace_path": _relative(self.settings.project_root, replay.trace_path),
                    }
                else:
                    trace_relative = _relative(self.settings.project_root, replay.trace_path)
                    replay_metrics = {
                        actor_id: _metric_view(metrics)
                        for actor_id, metrics in compute_scenario_replay_metrics(selected, replay.trace).items()
                    }
            except (OSError, ValueError) as error:
                status = "simulator-failed"
                simulator_error = str(error)

        if status != "valid":
            ranking_for_report = None

        report = VariantReport(
            variant_id=variant.scenario_id,
            status=status,
            scenario_artifact=scenario_relative,
            xosc_artifact=xosc_relative,
            replay_trace_artifact=trace_relative,
            report_artifact=report_relative,
            validation=validation,
            ranking=ranking_for_report,
            simulator_error=simulator_error,
        )
        (variant_root / "report.json").write_text(
            json.dumps(variant_report_to_dict(report), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        result = VariantResult(
            variant_id=variant.scenario_id,
            status=status,
            configuration={
                "speed_multiplier": config.speed_multiplier,
                "initial_gap_delta_m": config.initial_gap_delta_m,
                "timing_offset_s": config.timing_offset_s,
                "seed": config.seed,
            },
            validation=_validation_view(validation),
            ranking=None if status != "valid" else _ranking_view(ranking),
            replay_metrics=replay_metrics,
            simulator_error=simulator_error,
            replay_failure=replay_failure,
            artifacts=_result_links(scenario_relative, xosc_relative, trace_relative, report_relative),
        )
        return result, report

    def export_variant(self, job_id: str, variant_id: str):
        record = self.get(job_id)
        result = next((item for item in record.results if item.variant_id == variant_id), None)
        if result is None:
            raise KeyError(f"Batch result {variant_id!r} was not found.")
        if result.status != "valid":
            raise ValueError("Only valid variants can be exported to OpenSCENARIO.")
        scenario_link = next(item for item in result.artifacts if item.kind == "canonical-json")
        scenario_path = self.adapter.resolve_artifact(scenario_link.path)
        scenario, _, _ = artifact_from_json(scenario_path.read_text(encoding="utf-8"))
        selected, template = select_opendrive_template(
            scenario, topology=STRAIGHT_ROAD_TOPOLOGY
        )
        xosc_path = write_openscenario(
            selected, template, scenario_path.with_name("scenario.xosc")
        )
        xosc_relative = _relative(self.settings.project_root, xosc_path)
        if not any(item.path == xosc_relative for item in result.artifacts):
            result.artifacts.append(
                ArtifactLink(
                    kind="openscenario",
                    path=xosc_relative,
                    url=f"/api/artifacts/{xosc_relative}",
                )
            )
        from .schemas import ExportResponse

        return ExportResponse(variant_id=variant_id, artifacts=result.artifacts)

    def trajectory(self, job_id: str, variant_id: str):
        record = self.get(job_id)
        result = next((item for item in record.results if item.variant_id == variant_id), None)
        if result is None:
            raise KeyError(f"Batch result {variant_id!r} was not found.")
        scenario_link = next(item for item in result.artifacts if item.kind == "canonical-json")
        scenario_path = self.adapter.resolve_artifact(scenario_link.path)
        scenario, _, _ = artifact_from_json(scenario_path.read_text(encoding="utf-8"))
        return self.adapter.trajectory_for_scenario(scenario, scenario_path, path_kind="generated")


def to_results(record: JobRecord) -> BatchResults:
    return BatchResults(
        job=record.status,
        manifest=record.manifest,
        counts=record.counts,
        results=record.results,
    )


def _validation_view(validation):
    return ValidationView(
        valid=validation.valid,
        validation_version=validation.validation_version,
        reasons=[
            ValidationReasonView(
                code=reason.code,
                category=reason.category,
                actor_id=reason.actor_id,
                state_index=reason.state_index,
                observed=reason.observed,
                limit=reason.limit,
                message=reason.message,
            )
            for reason in validation.reasons
        ],
    )


def _ranking_view(ranking):
    return RankingView(
        rankable=ranking.rankable,
        ranking_version=ranking.ranking_version,
        features=RankingFeatureView(
            minimum_distance_m=ranking.features.minimum_distance_m,
            minimum_ttc_s=ranking.features.minimum_ttc_s,
            novelty=ranking.features.novelty,
            risk_signal=ranking.features.risk_signal,
        ),
        breakdown=None
        if ranking.breakdown is None
        else ScoreBreakdownView(
            risk_signal=ranking.breakdown.risk_signal,
            novelty=ranking.breakdown.novelty,
            replay_quality=ranking.breakdown.replay_quality,
            feasibility_penalty=ranking.breakdown.feasibility_penalty,
            total=ranking.breakdown.total,
        ),
    )


def _metric_view(metrics):
    return ReplayMetricView(
        sample_count=metrics.sample_count,
        alignment_method=metrics.alignment_method,
        position_rmse_m=metrics.position_rmse_m,
        final_displacement_m=metrics.final_displacement_m,
        heading_mae_rad=metrics.heading_mae_rad,
        speed_mae_mps=metrics.speed_mae_mps,
    )


def _result_links(scenario, xosc, trace, report):
    values = [("canonical-json", scenario), ("report", report)]
    if xosc:
        values.append(("openscenario", xosc))
    if trace:
        values.append(("replay-trace", trace))
    return [ArtifactLink(kind=kind, path=path, url=f"/api/artifacts/{path}") for kind, path in values]


def _relative(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root).as_posix()


def _replay_error(replay) -> str:
    details = replay.stderr.strip() or replay.stdout.strip() or "Replay did not complete."
    return f"exit_code={replay.exit_code}; timed_out={replay.timed_out}; {details}"
