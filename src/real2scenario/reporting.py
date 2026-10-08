"""Deterministic per-variant and aggregate batch reports."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .ranking import RankingResult
from .validation import FeasibilityReport


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
) -> AggregateReport:
    """Build an aggregate report and enforce the three-status invariant."""
    result = AggregateReport(parent_scenario_id, reports, report_version)
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
