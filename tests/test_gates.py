import pytest

from real2scenario import Actor, Scenario, State
from real2scenario.gates import (
    G3_MINIMUM_MATCH_RATE,
    evaluate_cp4_gates,
    evaluate_g3_road_match,
    evaluate_g2_simulator_completion,
    summarize_funnels,
    summarize_gate_funnel,
    evaluate_temporary_g6_g7,
)


def _scenario() -> Scenario:
    return Scenario(
        scenario_id="gate-fixture",
        duration_s=1.0,
        ego_actor_id="ego",
        coordinate_frame="local_road_aligned",
        actors=(
            Actor("ego", "vehicle", (State(0, 0, 0, 0, 10), State(1, 10, 0, 0, 10))),
            Actor("lead", "vehicle", (State(0, 5, 0, 0, 1), State(1, 6, 0, 0, 1))),
        ),
    )


def test_temporary_gates_are_provisional_and_report_observed_values() -> None:
    report = evaluate_temporary_g6_g7(_scenario(), diversity_distance=0.2, no_collision=True)

    assert report.temporary is True
    assert report.gates[0].gate_id == "G6"
    assert report.gates[0].scientific_status == "PROVISIONAL"
    assert report.gates[0].status == "pass"
    assert report.gates[1].status == "pass"


def test_g6_does_not_claim_collision_free_without_runtime_status() -> None:
    report = evaluate_temporary_g6_g7(_scenario(), diversity_distance=0.2)

    assert report.gates[0].status == "fail"
    assert "collision_status_unverified" in report.gates[0].reasons


def test_g7_rejects_near_duplicate_and_final_count_is_unavailable() -> None:
    report = evaluate_temporary_g6_g7(_scenario(), diversity_distance=0.1, no_collision=True)
    summary = summarize_funnels((report,))

    assert report.first_failed_gate == "G7"
    assert summary.temporary_valid_count == 0
    assert summary.final_valid_count is None


def test_invalid_gate_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        evaluate_temporary_g6_g7(_scenario(), diversity_epsilon=0.0)


def test_cp4_gate_orchestration_returns_ordered_g1_to_g7_results() -> None:
    gates = evaluate_cp4_gates(
        _scenario(),
        simulator_statuses={"esmini": "completed"},
        no_collision=True,
        diversity_distance=0.2,
    )

    assert tuple(gate.gate_id for gate in gates) == ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
    assert gates[0].status == "skipped"
    assert gates[1].status == "pass"
    assert gates[2].status == "skipped"
    assert all(gate.scientific_status != "FINAL" for gate in gates)


def test_cp4_funnel_reconciliation_counts_cumulative_passes() -> None:
    first = evaluate_cp4_gates(
        _scenario(), simulator_statuses={"esmini": "completed"},
        no_collision=True, diversity_distance=0.2,
    )
    second = evaluate_cp4_gates(
        _scenario(), simulator_statuses={"esmini": "failed"},
        no_collision=True, diversity_distance=0.2,
    )

    summary = summarize_gate_funnel((first, second))

    assert summary.generated == 2
    assert summary.evaluated_counts["G2"] == 2
    assert summary.pass_counts["G2"] == 1
    assert summary.cumulative_pass_counts["G2"] == 0
    assert summary.scientific_status == "PROVISIONAL"


def test_g2_keeps_unverified_and_failed_statuses_separate() -> None:
    unverified = evaluate_g2_simulator_completion({"esmini": "unverified", "carla": "skipped"}, required_simulators=("esmini", "carla"))
    failed = evaluate_g2_simulator_completion({"esmini": "failed"})

    assert unverified.status == "skipped"
    assert "simulator_completion_unverified" in unverified.reasons
    assert failed.status == "fail"
    assert failed.reasons == ("simulator_failed",)


def _lane_match_evidence(state_count: int, matched_state_count: int):
    from real2scenario.road_match import (
        LaneRoadMatchConfig,
        LaneRoadMatchEvidence,
        LaneRoadMatchSummary,
    )

    rate = matched_state_count / state_count
    return LaneRoadMatchEvidence(
        scenario_id="gate-fixture",
        coordinate_frame="local_road_aligned",
        overall=LaneRoadMatchSummary(
            state_count=state_count,
            matched_state_count=matched_state_count,
            raw_match_rate=rate,
            provisional_95_status=(
                "at_or_above_95_percent" if rate >= 0.95 else "below_95_percent"
            ),
        ),
        config=LaneRoadMatchConfig(0.5, 0.2),
    )


def test_g3_evaluates_supplied_evidence_against_the_fixed_provisional_reference() -> None:
    below = evaluate_cp4_gates(_scenario(), lane_match_report=_lane_match_evidence(143, 20))
    above = evaluate_cp4_gates(_scenario(), lane_match_report=_lane_match_evidence(100, 95))

    assert below[2].status == "fail"
    assert below[2].reasons == ("road_match_below_provisional_threshold",)
    assert below[2].observed["raw_match_rate"] == 20 / 143
    assert below[2].scientific_status == "PROVISIONAL"
    assert above[2].status == "pass"
    assert above[2].observed["minimum_match_rate"] == 0.95


def test_g3_skips_without_evidence_and_never_claims_a_pass() -> None:
    gates = evaluate_cp4_gates(_scenario())

    assert gates[2].gate_id == "G3"
    assert gates[2].status == "skipped"
    assert gates[2].reasons == ("road_match_unavailable",)


def test_g3_rejects_an_out_of_range_minimum_match_rate() -> None:
    with pytest.raises(ValueError):
        evaluate_g3_road_match(_lane_match_evidence(143, 20), minimum_match_rate=1.5)
    with pytest.raises(ValueError):
        evaluate_g3_road_match(_lane_match_evidence(143, 20), minimum_match_rate=-0.1)


def test_g3_default_reference_is_the_fixed_provisional_value() -> None:
    gates = evaluate_cp4_gates(_scenario(), lane_match_report=_lane_match_evidence(143, 20))

    assert G3_MINIMUM_MATCH_RATE == 0.95
    assert gates[2].observed["minimum_match_rate"] == G3_MINIMUM_MATCH_RATE
