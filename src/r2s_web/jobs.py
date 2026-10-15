"""Bounded in-process batch orchestration for the local demo."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from real2scenario import (
    AggregateReport,
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
    variant_report_to_dict,
    write_aggregate_csv,
    write_aggregate_json,
    write_openscenario,
    run_esmini,
    EsminiConfig,
    compute_scenario_replay_metrics,
    aggregate_replay_metrics,
    select_opendrive_template,
    STRAIGHT_ROAD_TOPOLOGY,
    artifact_from_json,
    ActorMotionEdit,
    preview_variant,
    evaluate_g4_g5,
    evaluate_cp4_gates,
    lane_road_match_evidence_from_dict,
    ALIGNMENT_METHOD,
    evaluate_temporary_g6_g7,
    variant_artifact_to_dict,
)
from real2scenario.kinematic import KINEMATIC_VERSION, KinematicLimits

from .adapter import ArtifactAdapter
from .config import WebSettings
from .schemas import (
    ArtifactLink,
    MetricAvailabilityView,
    MetricDistributionView,
    ReplayMetricAggregateView,
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
    PreviewRequest,
    PreviewResponse,
    GateResultView,
)


@dataclass(slots=True)
class JobRecord:
    status: JobStatus
    manifest: dict[str, object] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    results: list[VariantResult] = field(default_factory=list)
    replay_metric_aggregate: object | None = None
    replay_metrics: MetricAvailabilityView | None = None
    gate_funnel: dict[str, object] | None = None
    aggregate: AggregateReport | None = None


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
        declaration = (
            None if request.event_declaration is None else request.event_declaration.to_declaration()
        )
        for variant, config in zip(variants, manifest.configurations):
            result, report = self._process_variant(
                parent.scenario,
                variant,
                config,
                job_root,
                request.replay_enabled,
                request.validation_limits,
                lane_match_evidence=request.lane_match_evidence.get(variant.scenario_id),
                event_declaration=declaration,
            )
            result_models.append(result)
            reports.append(report)
        all_metrics = tuple(metric for report in reports for metric in report.replay_metrics.values())
        metric_aggregate = aggregate_replay_metrics(all_metrics) if all_metrics else None
        aggregate = aggregate_report(parent.scenario.scenario_id, tuple(reports), replay_metric_aggregate=metric_aggregate)
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
        record.replay_metrics = _metric_availability(
            all_metrics, metric_aggregate, _metric_provenance(parent.scenario)
        )
        record.aggregate = aggregate
        record.replay_metric_aggregate = metric_aggregate
        record.gate_funnel = None if aggregate.gate_funnel is None else {
            "generated": aggregate.gate_funnel.generated,
            "evaluated_counts": dict(aggregate.gate_funnel.evaluated_counts),
            "pass_counts": dict(aggregate.gate_funnel.pass_counts),
            "cumulative_pass_counts": dict(aggregate.gate_funnel.cumulative_pass_counts),
            "scientific_status": aggregate.gate_funnel.scientific_status,
        }
        record.status = record.status.model_copy(
            update={
                "status": "completed",
                "generated": aggregate.generated,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _process_variant(
        self,
        parent,
        variant,
        config,
        job_root,
        replay_enabled,
        validation_limits,
        *,
        lane_match_evidence=None,
        event_declaration=None,
    ):
        if event_declaration is not None:
            variant = replace(
                variant,
                provenance={
                    **variant.provenance,
                    **{key: _provenance_value(value) for key, value in event_declaration.items()},
                },
            )
        evidence = (
            None
            if lane_match_evidence is None
            else lane_road_match_evidence_from_dict(lane_match_evidence)
        )
        if evidence is not None and evidence.scenario_id != variant.scenario_id:
            raise ValueError(
                "lane_match_evidence_scenario_mismatch: evidence for "
                f"{evidence.scenario_id!r} cannot gate candidate {variant.scenario_id!r}."
            )
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
        xosc_path = None
        trace_relative = None
        replay_metrics = {}
        simulator_error = None
        replay_failure = None
        replay_metric_models = {}
        replay_metric_aggregate = None
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
                    scenario_metrics = compute_scenario_replay_metrics(selected, replay.trace)
                    replay_metric_models = scenario_metrics.metrics
                    replay_metric_aggregate = aggregate_replay_metrics(tuple(replay_metric_models.values())) if replay_metric_models else None
                    replay_metrics = {
                        actor_id: _metric_view(metrics)
                        for actor_id, metrics in replay_metric_models.items()
                    }
            except (OSError, ValueError) as error:
                status = "simulator-failed"
                simulator_error = str(error)

        if status != "valid":
            ranking_for_report = None

        simulator_statuses = {"esmini": "unverified"}
        if replay_enabled and validation.valid:
            simulator_statuses["esmini"] = "completed" if status != "simulator-failed" else "failed"
        elif not validation.valid:
            simulator_statuses["esmini"] = "skipped"
        gates = evaluate_cp4_gates(
            variant,
            xosc_path=xosc_path,
            simulator_statuses=simulator_statuses,
            required_simulators=("esmini",),
            lane_match_report=evidence,
            event_declaration=event_declaration,
            limits=limits,
            no_collision=None,
        )
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
            gate_results=gates,
            replay_metrics=replay_metric_models,
            replay_metric_aggregate=replay_metric_aggregate,
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
            replay_metric_aggregate=_metric_aggregate_view(replay_metric_aggregate),
            gates=[_gate_view(gate) for gate in gates],
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


class PreviewService:
    """Synchronous synthetic-fixture-compatible U0 preview service."""

    def __init__(self, settings: WebSettings, adapter: ArtifactAdapter):
        self.settings = settings
        self.adapter = adapter

    def preview(self, scenario_id: str, request: PreviewRequest) -> PreviewResponse:
        parent_record = self.adapter.get(scenario_id)
        if request.behavior == "behavior":
            return PreviewResponse(
                parent_scenario_id=scenario_id, variant_id=None, status="unsupported",
                behavior={"requested": "behavior", "status": "unsupported",
                          "reason": "behavior executor is not implemented"},
                configuration=request.model_dump(), provenance=dict(parent_record.scenario.provenance),
            )
        edits = tuple(ActorMotionEdit(**edit.model_dump()) for edit in request.actor_edits)
        variant = preview_variant(parent_record.scenario, edits, seed=request.seed)
        validation = validate_feasibility(variant, FeasibilityLimits())
        gates = evaluate_cp4_gates(
            variant,
            simulator_statuses={"esmini": "unverified"},
            required_simulators=("esmini",),
            no_collision=None,
        )
        variant_root = self.settings.output_root / "previews" / variant.scenario_id
        variant_root.mkdir(parents=True, exist_ok=True)
        scenario_path = variant_root / "scenario.json"
        scenario_path.write_text(json.dumps(variant_artifact_to_dict(
            variant, parent_record.scenario.scenario_id,
            edits[0] if False else _preview_config(edits, request.seed)), sort_keys=True, separators=(",", ":")), encoding="utf-8")
        relative = _relative(self.settings.project_root, scenario_path)
        trajectory = self.adapter.trajectory_for_scenario(variant, scenario_path, path_kind="generated")
        config_hash = variant.provenance.get("preview_config_hash", "")
        artifacts = [ArtifactLink(kind="canonical-json", path=relative, url=f"/api/artifacts/{relative}")]
        limits = KinematicLimits()
        maneuver_violations = []
        for edit in edits:
            if edit.acceleration_mps2 is not None and edit.acceleration_mps2 > limits.max_acceleration_mps2:
                maneuver_violations.append({"code": "acceleration_exceeded", "actor_id": edit.actor_id, "observed": edit.acceleration_mps2, "limit": limits.max_acceleration_mps2, "provenance": KINEMATIC_VERSION})
            if edit.braking_mps2 is not None and edit.braking_mps2 > limits.max_deceleration_mps2:
                maneuver_violations.append({"code": "deceleration_exceeded", "actor_id": edit.actor_id, "observed": edit.braking_mps2, "limit": limits.max_deceleration_mps2, "provenance": KINEMATIC_VERSION})
            if abs(edit.steering_angle_rad) > limits.max_yaw_rate_radps:
                maneuver_violations.append({"code": "yaw_rate_exceeded", "actor_id": edit.actor_id, "observed": abs(edit.steering_angle_rad), "limit": limits.max_yaw_rate_radps, "provenance": KINEMATIC_VERSION})
        recipe_steps = [step.model_dump() for step in request.recipe_steps]
        return PreviewResponse(
            parent_scenario_id=scenario_id, variant_id=variant.scenario_id,
            status="valid" if validation.valid else "invalid",
            behavior={"requested": "parameterized", "status": "supported"},
            configuration={"actor_edits": [edit.model_dump() for edit in request.actor_edits], "replay_mode": request.replay_mode, "seed": request.seed},
            provenance={**variant.provenance, "config_hash": config_hash, "simulator_version": KINEMATIC_VERSION, "preview_mode": "kinematic-open-loop-v1", "fixed_timestep_s": "0.05", "silent_clamps": "forbidden"},
            paths=trajectory.paths, validation=_validation_view(validation),
            gates=[GateResultView(gate_id=g.gate_id, status=g.status, reasons=list(g.reasons), config_version=g.config_version,
                                  observed=None if g.observed is None else dict(g.observed), scientific_status=g.scientific_status) for g in gates],
            replay_metrics=trajectory.replay_metrics,
            metrics=MetricAvailabilityView(
                available=False,
                unavailable_reason="preview_has_no_simulator_trace",
                scientific_status="PROVISIONAL",
                provenance={
                    **_metric_provenance(parent_record.scenario),
                    "preview_mode": "kinematic-open-loop-v1",
                },
            ),
            artifacts=artifacts,
            recipe_steps=recipe_steps,
            limits={"version": limits.version, "simulator": KINEMATIC_VERSION, "max_acceleration_mps2": limits.max_acceleration_mps2, "max_deceleration_mps2": limits.max_deceleration_mps2, "max_yaw_rate_radps": limits.max_yaw_rate_radps, "silent_clamps": "forbidden"},
            violations=maneuver_violations,
            rollback_marker={"parent_scenario_id": scenario_id, "variant_id": variant.scenario_id, "immutable_parent": True},
        )


def _provenance_value(value: object) -> str:
    """Canonical scenario provenance is string-valued."""
    return str(value)


def _preview_config(edits, seed):
    from real2scenario import VariantConfig
    if len(edits) != 1 or edits[0].heading_offset_rad != 0:
        # Preview artifacts use the canonical variant schema; multi-actor/heading
        # details remain in the response and provenance until schema v2 exists.
        return VariantConfig(seed=seed)
    edit = edits[0]
    return VariantConfig(edit.speed_multiplier, edit.initial_gap_delta_m, edit.timing_offset_s, seed)


def to_results(record: JobRecord) -> BatchResults:
    return BatchResults(
        job=record.status,
        manifest=record.manifest,
        counts=record.counts,
        results=record.results,
        replay_metric_aggregate=_metric_aggregate_view(record.replay_metric_aggregate),
        replay_metrics=record.replay_metrics,
        gate_funnel=record.gate_funnel,
    )


def _gate_view(gate):
    return GateResultView(gate_id=gate.gate_id, status=gate.status, reasons=list(gate.reasons), config_version=gate.config_version,
                          observed=None if gate.observed is None else dict(gate.observed), scientific_status=gate.scientific_status)


def _metric_aggregate_view(aggregate):
    if aggregate is None:
        return None
    from .schemas import MetricDistributionView, ReplayMetricAggregateView
    return ReplayMetricAggregateView(actor_count=aggregate.actor_count,
        ade_m=MetricDistributionView(mean=aggregate.ade_m.mean, median=aggregate.ade_m.median, p95=aggregate.ade_m.p95, max=aggregate.ade_m.max),
        fde_m=None if aggregate.fde_m is None else MetricDistributionView(mean=aggregate.fde_m.mean, median=aggregate.fde_m.median, p95=aggregate.fde_m.p95, max=aggregate.fde_m.max))


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


def _metric_provenance(scenario) -> dict[str, str]:
    """Dataset, source-scene and transform provenance for a metric block."""
    keys = ("dataset_version", "source_scene_token", "coordinate_transform_version")
    return {key: scenario.provenance[key] for key in keys if key in scenario.provenance}


def _metric_availability(metrics, aggregate, provenance=None) -> MetricAvailabilityView:
    """Expose whether replay metrics exist, and why they do not when absent."""
    if not metrics:
        return MetricAvailabilityView(
            available=False,
            unavailable_reason="no_replay_trace_was_recorded",
            scientific_status="PROVISIONAL",
            provenance=dict(provenance or {}),
        )
    return MetricAvailabilityView(
        available=True,
        source="replay_trace",
        alignment_method=ALIGNMENT_METHOD,
        scientific_status="PROVISIONAL",
        provenance={
            "alignment_method": ALIGNMENT_METHOD,
            "metric_status": "replay_alignment_metrics_are_provisional",
            **dict(provenance or {}),
        },
        per_actor={},
        aggregate=_metric_aggregate_view(aggregate),
    )


def _metric_view(metrics):
        return ReplayMetricView(
        sample_count=metrics.sample_count,
        alignment_method=metrics.alignment_method,
        position_rmse_m=metrics.position_rmse_m,
        final_displacement_m=metrics.final_displacement_m,
        heading_mae_rad=metrics.heading_mae_rad,
            speed_mae_mps=metrics.speed_mae_mps,
            ade_m=metrics.ade_m,
            fde_m=metrics.fde_m,
            coverage_status=metrics.coverage_status,
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
