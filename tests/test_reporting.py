import json

import pytest

from real2scenario import (
    Actor,
    FeasibilityLimits,
    Scenario,
    State,
    VariantReport,
    aggregate_report,
    aggregate_report_to_dict,
    rank_scenario,
    validate_feasibility,
    write_aggregate_csv,
    write_aggregate_json,
    write_variant_report,
)


def _scenario(scenario_id: str = "report-fixture") -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(
            Actor(
                "ego",
                "vehicle",
                (State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 1.0, 0.0, 0.0, 1.0)),
            ),
        ),
        coordinate_frame="local_road_aligned",
    )


def _reports() -> tuple[VariantReport, ...]:
    valid_scenario = _scenario("valid")
    valid_validation = validate_feasibility(valid_scenario)
    invalid_scenario = Scenario(
        "invalid",
        1.0,
        "ego",
        (
            Actor(
                "ego",
                "vehicle",
                (State(0.0, 0.0, 0.0, 0.0, 0.0), State(1.0, 1.0, 0.0, 0.0, 10.0)),
            ),
        ),
        "local_road_aligned",
    )
    invalid_validation = validate_feasibility(invalid_scenario, FeasibilityLimits(max_acceleration_mps2=1.0))
    return (
        VariantReport(
            variant_id="valid",
            status="valid",
            scenario_artifact="generated/valid/scenario.json",
            xosc_artifact="generated/valid/scenario.xosc",
            replay_trace_artifact="generated/valid/replay.csv",
            report_artifact="generated/valid/report.json",
            validation=valid_validation,
            ranking=rank_scenario(valid_scenario, valid_validation),
        ),
        VariantReport(
            variant_id="invalid",
            status="invalid",
            scenario_artifact="generated/invalid/scenario.json",
            xosc_artifact=None,
            replay_trace_artifact=None,
            report_artifact="generated/invalid/report.json",
            validation=invalid_validation,
        ),
        VariantReport(
            variant_id="failed",
            status="simulator-failed",
            scenario_artifact="generated/failed/scenario.json",
            xosc_artifact="generated/failed/scenario.xosc",
            replay_trace_artifact=None,
            report_artifact="generated/failed/report.json",
            validation=valid_validation,
            simulator_error="esmini exited with code 7",
        ),
    )


def test_aggregate_reconciles_all_three_statuses_and_serializes_links() -> None:
    report = aggregate_report("baseline-001", _reports())

    assert report.generated == 3
    assert report.valid == 1
    assert report.invalid == 1
    assert report.simulator_failed == 1
    data = aggregate_report_to_dict(report)
    assert data["counts"] == {"generated": 3, "valid": 1, "invalid": 1, "simulator_failed": 1}
    assert data["variants"][0]["artifacts"]["xosc"] == "generated/valid/scenario.xosc"
    assert data["variants"][1]["validation"]["reasons"]


def test_report_writers_are_deterministic_and_create_parent_directories(tmp_path) -> None:
    reports = _reports()
    aggregate = aggregate_report("baseline-001", reports)
    variant_path = write_variant_report(reports[0], tmp_path / "nested" / "valid.json")
    json_path = write_aggregate_json(aggregate, tmp_path / "nested" / "aggregate.json")
    csv_path = write_aggregate_csv(aggregate, tmp_path / "nested" / "aggregate.csv")

    assert variant_path.read_text(encoding="utf-8") == variant_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["counts"]["generated"] == 3
    assert csv_path.read_text(encoding="utf-8").splitlines()[0].startswith("variant_id,status,")
    assert len(csv_path.read_text(encoding="utf-8").splitlines()) == 4


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"status": "unknown"}, "status"),
        ({"scenario_artifact": ""}, "scenario_artifact"),
        ({"report_artifact": ""}, "report_artifact"),
        ({"status": "simulator-failed", "simulator_error": None}, "simulator_error"),
    ],
)
def test_variant_report_rejects_invalid_status_contract(kwargs: dict[str, object], message: str) -> None:
    scenario = _scenario()
    validation = validate_feasibility(scenario)
    values: dict[str, object] = {
        "variant_id": "variant",
        "status": "valid",
        "scenario_artifact": "scenario.json",
        "xosc_artifact": None,
        "replay_trace_artifact": None,
        "report_artifact": "report.json",
        "validation": validation,
    }
    values.update(kwargs)
    if values["status"] == "simulator-failed":
        values["validation"] = validation
    with pytest.raises(ValueError, match=message):
        VariantReport(**values)  # type: ignore[arg-type]


def test_aggregate_report_rejects_duplicate_variant_ids() -> None:
    report = _reports()[0]
    with pytest.raises(ValueError, match="unique"):
        aggregate_report("baseline-001", (report, report))
