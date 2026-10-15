"""Deterministic provisional multi-scene benchmark aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from .gates import GateFunnelSummary, summarize_gate_funnel
from .metrics import ReplayMetricAggregate, aggregate_replay_metrics
from .reporting import AggregateReport


BENCHMARK_VERSION = "benchmark-aggregate-v1"
EvidenceClass = Literal["synthetic", "nuscenes_local", "other_local"]
SimulatorClass = Literal["none", "esmini", "carla_unverified"]


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    """One completed scene/batch report with explicit evidence provenance."""

    run_id: str
    scene_id: str
    evidence_class: EvidenceClass
    simulator: SimulatorClass
    report: AggregateReport
    visibility: Literal["local_private", "conditional", "public"] = "local_private"

    def __post_init__(self) -> None:
        if not self.run_id or not self.scene_id:
            raise ValueError("BenchmarkRun identifiers must not be empty.")
        if self.evidence_class not in {"synthetic", "nuscenes_local", "other_local"}:
            raise ValueError("Unsupported benchmark evidence_class.")
        if self.simulator not in {"none", "esmini", "carla_unverified"}:
            raise ValueError("Unsupported benchmark simulator.")
        if self.visibility not in {"local_private", "conditional", "public"}:
            raise ValueError("Unsupported benchmark visibility.")


@dataclass(frozen=True, slots=True)
class BenchmarkSceneSummary:
    run_id: str
    scene_id: str
    evidence_class: EvidenceClass
    simulator: SimulatorClass
    visibility: str
    generated: int
    valid: int
    invalid: int
    simulator_failed: int


@dataclass(frozen=True, slots=True)
class BenchmarkAggregate:
    benchmark_version: str
    scene_summaries: tuple[BenchmarkSceneSummary, ...]
    counts_by_evidence_class: Mapping[str, int]
    counts_by_simulator: Mapping[str, int]
    status_counts: Mapping[str, int]
    replay_metric_aggregate: ReplayMetricAggregate | None
    gate_funnel: GateFunnelSummary
    scientific_status: Literal["PROVISIONAL"] = "PROVISIONAL"

    @property
    def scene_count(self) -> int:
        return len(self.scene_summaries)


def aggregate_benchmark_runs(runs: Sequence[BenchmarkRun]) -> BenchmarkAggregate:
    """Aggregate scene reports without mixing evidence provenance classes."""
    ordered = tuple(sorted(runs, key=lambda run: (run.scene_id, run.run_id)))
    if len({run.run_id for run in ordered}) != len(ordered):
        raise ValueError("Benchmark run IDs must be unique.")
    if len({run.scene_id for run in ordered}) != len(ordered):
        raise ValueError("Benchmark scene IDs must be unique for one aggregate.")

    summaries = tuple(
        BenchmarkSceneSummary(
            run.run_id,
            run.scene_id,
            run.evidence_class,
            run.simulator,
            run.visibility,
            run.report.generated,
            run.report.valid,
            run.report.invalid,
            run.report.simulator_failed,
        )
        for run in ordered
    )
    reports = tuple(report for run in ordered for report in run.report.reports)
    metrics = tuple(metric for report in reports for metric in report.replay_metrics.values())
    gate_reports = tuple(report.gate_results for report in reports)
    return BenchmarkAggregate(
        BENCHMARK_VERSION,
        summaries,
        _count_by(runs, lambda run: run.evidence_class),
        _count_by(runs, lambda run: run.simulator),
        {
            "generated": sum(summary.generated for summary in summaries),
            "valid": sum(summary.valid for summary in summaries),
            "invalid": sum(summary.invalid for summary in summaries),
            "simulator_failed": sum(summary.simulator_failed for summary in summaries),
        },
        aggregate_replay_metrics(metrics) if metrics else None,
        summarize_gate_funnel(gate_reports),
    )


def benchmark_aggregate_to_dict(aggregate: BenchmarkAggregate) -> dict[str, object]:
    """Convert a benchmark aggregate to deterministic JSON-safe data."""
    return {
        "benchmark_version": aggregate.benchmark_version,
        "scientific_status": aggregate.scientific_status,
        "scene_count": aggregate.scene_count,
        "scenes": [
            {
                "run_id": summary.run_id,
                "scene_id": summary.scene_id,
                "evidence_class": summary.evidence_class,
                "simulator": summary.simulator,
                "visibility": summary.visibility,
                "counts": {
                    "generated": summary.generated,
                    "valid": summary.valid,
                    "invalid": summary.invalid,
                    "simulator_failed": summary.simulator_failed,
                },
            }
            for summary in aggregate.scene_summaries
        ],
        "counts_by_evidence_class": dict(aggregate.counts_by_evidence_class),
        "counts_by_simulator": dict(aggregate.counts_by_simulator),
        "status_counts": dict(aggregate.status_counts),
        "replay_metric_aggregate": _metric_dict(aggregate.replay_metric_aggregate),
        "gate_funnel": {
            "generated": aggregate.gate_funnel.generated,
            "evaluated_counts": dict(aggregate.gate_funnel.evaluated_counts),
            "pass_counts": dict(aggregate.gate_funnel.pass_counts),
            "cumulative_pass_counts": dict(aggregate.gate_funnel.cumulative_pass_counts),
            "scientific_status": aggregate.gate_funnel.scientific_status,
        },
    }


def _count_by(runs: Sequence[BenchmarkRun], selector) -> dict[str, int]:
    return {key: sum(selector(run) == key for run in runs) for key in sorted({selector(run) for run in runs})}


def _metric_dict(aggregate: ReplayMetricAggregate | None) -> dict[str, object] | None:
    if aggregate is None:
        return None
    return {
        "actor_count": aggregate.actor_count,
        "ade_m": _distribution_dict(aggregate.ade_m),
        "fde_m": None if aggregate.fde_m is None else _distribution_dict(aggregate.fde_m),
    }


def _distribution_dict(distribution) -> dict[str, float]:
    return {
        "mean": distribution.mean,
        "median": distribution.median,
        "p95": distribution.p95,
        "max": distribution.max,
    }
