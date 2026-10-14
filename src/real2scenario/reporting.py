"""Deterministic per-variant and aggregate batch reports."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .ranking import RankingResult
from .validation import FeasibilityReport
from .gates import GATE_IDS, GateFunnelSummary, GateResult, summarize_gate_funnel
from .metrics import ReplayMetrics, ReplayMetricAggregate


REPORT_VERSION = "batch-report-v1"
REPORT_STATUSES = frozenset({"valid", "invalid", "simulator-failed"})


@dataclass(frozen=True, slots=True)
class VariantReport:
    """Auditable result and artifact links for one generated variant."""

    variant_id: str
    status: str
    scenario_artifact: str
    xosc_artifact: str | None
    replay_trace_artifact: str | None
    report_artifact: str
    validation: FeasibilityReport
    ranking: RankingResult | None = None
    simulator_error: str | None = None
    gate_results: tuple[GateResult, ...] = ()
    replay_metrics: Mapping[str, ReplayMetrics] = field(default_factory=dict)
    replay_metric_aggregate: ReplayMetricAggregate | None = None

    def __post_init__(self) -> None:
        if not self.variant_id:
            raise ValueError("VariantReport variant_id must not be empty.")
        if self.status not in REPORT_STATUSES:
            raise ValueError("VariantReport status must be valid, invalid, or simulator-failed.")
        for name, value in (
            ("scenario_artifact", self.scenario_artifact),
            ("report_artifact", self.report_artifact),
        ):
            if not value:
                raise ValueError(f"VariantReport {name} must not be empty.")
        if self.status == "simulator-failed" and not self.simulator_error:
            raise ValueError("Simulator-failed reports must include simulator_error.")
        if self.status == "valid" and not self.validation.valid:
            raise ValueError("Valid reports require a valid feasibility report.")
        if self.status == "invalid" and self.validation.valid:
            raise ValueError("Invalid reports require a failed feasibility report.")


@dataclass(frozen=True, slots=True)
class AggregateReport:
    """Ordered batch summary with a checked status reconciliation."""

    parent_scenario_id: str
    reports: tuple[VariantReport, ...]
    report_version: str = REPORT_VERSION
    replay_metric_aggregate: ReplayMetricAggregate | None = None
    gate_funnel: GateFunnelSummary | None = None

    def __post_init__(self) -> None:
        if not self.parent_scenario_id:
            raise ValueError("AggregateReport parent_scenario_id must not be empty.")
        if not self.report_version:
            raise ValueError("AggregateReport report_version must not be empty.")
        variant_ids = [report.variant_id for report in self.reports]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("AggregateReport variant IDs must be unique.")
        if self.generated != self.valid + self.invalid + self.simulator_failed:
            raise ValueError("Aggregate report counts do not reconcile.")

    @property
    def generated(self) -> int:
        return len(self.reports)

    @property
    def valid(self) -> int:
        return sum(report.status == "valid" for report in self.reports)

    @property
    def invalid(self) -> int:
        return sum(report.status == "invalid" for report in self.reports)

    @property
    def simulator_failed(self) -> int:
        return sum(report.status == "simulator-failed" for report in self.reports)

def aggregate_report(
    parent_scenario_id: str,
    reports: tuple[VariantReport, ...],
    *,
    report_version: str = REPORT_VERSION,
    replay_metric_aggregate: ReplayMetricAggregate | None = None,
    gate_funnel: GateFunnelSummary | None = None,
) -> AggregateReport:
    """Build an aggregate report and enforce the three-status invariant."""
    if gate_funnel is None:
        gate_funnel = summarize_gate_funnel(tuple(_complete_gate_set(report.gate_results) for report in reports))
    result = AggregateReport(parent_scenario_id, reports, report_version, replay_metric_aggregate, gate_funnel)
    if result.generated != result.valid + result.invalid + result.simulator_failed:
        raise ValueError("Aggregate report counts do not reconcile.")
    return result


def variant_report_to_dict(report: VariantReport) -> dict[str, object]:
    """Convert a per-variant report to deterministic JSON-safe data."""
    return {
        "report_version": REPORT_VERSION,
        "variant_id": report.variant_id,
        "status": report.status,
        "artifacts": {
            "scenario": report.scenario_artifact,
            "xosc": report.xosc_artifact,
            "replay_trace": report.replay_trace_artifact,
            "report": report.report_artifact,
        },
        "validation": {
            "scenario_id": report.validation.scenario_id,
            "validation_version": report.validation.validation_version,
            "valid": report.validation.valid,
            "reasons": [
                {
                    "code": reason.code,
                    "category": reason.category,
                    "actor_id": reason.actor_id,
                    "state_index": reason.state_index,
                    "observed": reason.observed,
                    "limit": reason.limit,
                    "message": reason.message,
                }
                for reason in report.validation.reasons
            ],
        },
        "ranking": _ranking_to_dict(report.ranking),
        "simulator_error": report.simulator_error,
        "replay_metrics": {actor_id: _replay_metrics_to_dict(metrics) for actor_id, metrics in sorted(report.replay_metrics.items())},
        "replay_metric_aggregate": _replay_metric_aggregate_to_dict(report.replay_metric_aggregate),
        "gates": [
            {
                "gate_id": gate.gate_id,
                "status": gate.status,
                "reasons": list(gate.reasons),
                "config_version": gate.config_version,
                "observed": dict(gate.observed or {}),
                "scientific_status": gate.scientific_status,
            }
            for gate in report.gate_results
        ],
    }


def aggregate_report_to_dict(report: AggregateReport) -> dict[str, object]:
    """Convert an aggregate report to deterministic JSON-safe data."""
    return {
        "report_version": report.report_version,
        "parent_scenario_id": report.parent_scenario_id,
        "counts": {
            "generated": report.generated,
            "valid": report.valid,
            "invalid": report.invalid,
            "simulator_failed": report.simulator_failed,
        },
        "variants": [variant_report_to_dict(item) for item in report.reports],
        "replay_metric_aggregate": _replay_metric_aggregate_to_dict(report.replay_metric_aggregate),
        "gate_funnel": _gate_funnel_to_dict(report.gate_funnel),
    }


def write_variant_report(report: VariantReport, output_path: str | Path) -> Path:
    """Write one report as compact deterministic JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(variant_report_to_dict(report), allow_nan=False, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def write_aggregate_json(report: AggregateReport, output_path: str | Path) -> Path:
    """Write the aggregate report as compact deterministic JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(aggregate_report_to_dict(report), allow_nan=False, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def write_aggregate_csv(report: AggregateReport, output_path: str | Path) -> Path:
    """Write one stable CSV row per variant with reconciliation counts."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "variant_id",
        "status",
        "scenario_artifact",
        "xosc_artifact",
        "replay_trace_artifact",
        "report_artifact",
        "validation_version",
        "validation_reason_count",
        "simulator_error",
        "replay_actor_count",
        "replay_ade_mean_m",
        "replay_ade_median_m",
        "replay_ade_p95_m",
        "replay_ade_max_m",
        "replay_fde_mean_m",
        "replay_fde_median_m",
        "replay_fde_p95_m",
        "replay_fde_max_m",
        "gate_G4_status",
        "gate_G5_status",
        "gate_G6_status",
        "gate_G7_status",
        "gate_G1_status",
        "gate_G2_status",
        "gate_G3_status",
    )
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in report.reports:
            writer.writerow(
                {
                    "variant_id": item.variant_id,
                    "status": item.status,
                    "scenario_artifact": item.scenario_artifact,
                    "xosc_artifact": item.xosc_artifact or "",
                    "replay_trace_artifact": item.replay_trace_artifact or "",
                    "report_artifact": item.report_artifact,
                    "validation_version": item.validation.validation_version,
                    "validation_reason_count": len(item.validation.reasons),
                    "simulator_error": item.simulator_error or "",
                    **_aggregate_csv_values(item.replay_metric_aggregate),
                    **{f"gate_{gate.gate_id}_status": gate.status for gate in item.gate_results},
                }
            )
    return path


def _ranking_to_dict(ranking: RankingResult | None) -> Mapping[str, object] | None:
    if ranking is None:
        return None
    return {
        "scenario_id": ranking.scenario_id,
        "ranking_version": ranking.ranking_version,
        "valid": ranking.valid,
        "rankable": ranking.rankable,
        "features": {
            "minimum_distance_m": ranking.features.minimum_distance_m,
            "minimum_ttc_s": ranking.features.minimum_ttc_s,
            "novelty": ranking.features.novelty,
            "risk_signal": ranking.features.risk_signal,
        },
        "breakdown": None
        if ranking.breakdown is None
        else {
            "risk_signal": ranking.breakdown.risk_signal,
            "novelty": ranking.breakdown.novelty,
            "replay_quality": ranking.breakdown.replay_quality,
            "feasibility_penalty": ranking.breakdown.feasibility_penalty,
            "total": ranking.breakdown.total,
        },
    }


def _complete_gate_set(gates: tuple[GateResult, ...]) -> tuple[GateResult, ...]:
    by_id = {gate.gate_id: gate for gate in gates}
    return tuple(
        by_id.get(
            gate_id,
            GateResult(gate_id, "skipped", ("gate_unavailable",)),
        )
        for gate_id in GATE_IDS
    )


def _gate_funnel_to_dict(summary: GateFunnelSummary | None) -> dict[str, object] | None:
    if summary is None:
        return None
    return {
        "generated": summary.generated,
        "evaluated_counts": dict(summary.evaluated_counts),
        "pass_counts": dict(summary.pass_counts),
        "cumulative_pass_counts": dict(summary.cumulative_pass_counts),
        "scientific_status": summary.scientific_status,
    }


def _replay_metrics_to_dict(metrics: ReplayMetrics) -> dict[str, object]:
    return {
        "sample_count": metrics.sample_count,
        "alignment_method": metrics.alignment_method,
        "position_rmse_m": metrics.position_rmse_m,
        "final_displacement_m": metrics.final_displacement_m,
        "heading_mae_rad": metrics.heading_mae_rad,
        "speed_mae_mps": metrics.speed_mae_mps,
        "ade_m": metrics.ade_m,
        "fde_m": metrics.fde_m,
        "coverage_status": metrics.coverage_status,
    }


def _replay_metric_aggregate_to_dict(aggregate: ReplayMetricAggregate | None) -> dict[str, object] | None:
    if aggregate is None:
        return None
    return {
        "actor_count": aggregate.actor_count,
        "ade_m": _distribution_to_dict(aggregate.ade_m),
        "fde_m": None if aggregate.fde_m is None else _distribution_to_dict(aggregate.fde_m),
    }


def _distribution_to_dict(distribution) -> dict[str, float]:
    return {"mean": distribution.mean, "median": distribution.median, "p95": distribution.p95, "max": distribution.max}


def _aggregate_csv_values(aggregate: ReplayMetricAggregate | None) -> dict[str, object]:
    empty = {name: "" for name in ("replay_actor_count", "replay_ade_mean_m", "replay_ade_median_m", "replay_ade_p95_m", "replay_ade_max_m", "replay_fde_mean_m", "replay_fde_median_m", "replay_fde_p95_m", "replay_fde_max_m")}
    if aggregate is None:
        return empty
    values = {"replay_actor_count": aggregate.actor_count, "replay_ade_mean_m": aggregate.ade_m.mean, "replay_ade_median_m": aggregate.ade_m.median, "replay_ade_p95_m": aggregate.ade_m.p95, "replay_ade_max_m": aggregate.ade_m.max}
    if aggregate.fde_m is not None:
        values.update({"replay_fde_mean_m": aggregate.fde_m.mean, "replay_fde_median_m": aggregate.fde_m.median, "replay_fde_p95_m": aggregate.fde_m.p95, "replay_fde_max_m": aggregate.fde_m.max})
    else:
        values.update({name: "" for name in ("replay_fde_mean_m", "replay_fde_median_m", "replay_fde_p95_m", "replay_fde_max_m")})
    return values
