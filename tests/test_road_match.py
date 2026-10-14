import math

import pytest

from real2scenario import (
    Actor,
    LaneCenterlinePose,
    LaneCenterlineRecord,
    LaneRoadMatchConfig,
    LaneSequenceMatchConfig,
    LaneWidthRecord,
    Scenario,
    State,
    diagnose_lane_road_match,
    diagnose_lane_footprint_occupancy,
    diagnose_nearest_lane_candidates,
    diagnose_lane_sequence_match,
    diagnose_lane_sequence_triage,
    build_lane_graph,
    compare_lane_references,
    analyze_actor_reference_sensitivity,
    classify_direction_counterfactuals,
    lane_graph_from_opendrive,
    lane_road_match_evidence_from_dict,
    lane_road_match_evidence_from_report,
    lane_road_match_evidence_to_dict,
)
from real2scenario.gates import evaluate_cp4_gates


def _road_match_report_fixture():
    scenario = Scenario("evidence-fixture", 1.0, "ego", (
        Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 10.0, 0.0, 0.0, 1.0))),
        Actor("other", "vehicle", (State(0.0, 0.0, 2.0, 0.0, 1.0), State(1.0, 10.0, 2.0, 0.0, 1.0))),
    ), "local_road_aligned")
    return diagnose_lane_road_match(
        scenario,
        (_lane(),),
        lane_coordinate_frame="local_road_aligned",
        config=LaneRoadMatchConfig(0.5, 0.2),
    )


def _gate_scenario_fixture() -> Scenario:
    return Scenario("evidence-fixture", 1.0, "ego", (
        Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 10.0, 0.0, 0.0, 1.0))),
        Actor("other", "vehicle", (State(0.0, 0.0, 2.0, 0.0, 1.0), State(1.0, 10.0, 2.0, 0.0, 1.0))),
    ), "local_road_aligned")


def _scenario() -> Scenario:
    return Scenario("match", 1.0, "ego", (
        Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 10.0, 0.0, 0.0, 1.0))),
        Actor("other", "vehicle", (State(0.0, 0.0, 2.0, 0.0, 1.0), State(1.0, 10.0, 2.0, 0.0, 1.0))),
    ), "local_road_aligned")


def _lane(y=0.0, yaw=0.0, lane_id="lane"):
    return LaneCenterlineRecord(lane_id, (LaneCenterlinePose(0.0, y, yaw), LaneCenterlinePose(10.0, y, yaw)))


def test_exact_match_reports_raw_state_and_actor_rates() -> None:
    report = diagnose_lane_road_match(_scenario(), (_lane(),), lane_coordinate_frame="local_road_aligned")

    assert report.overall.raw_match_rate == 1.0
    assert report.per_actor[0].summary.provisional_95_status == "at_or_above_95_percent"
    assert all(item.matched for item in report.state_matches)


def test_match_reports_distance_and_heading_reasons() -> None:
    scenario = Scenario("match", 1.0, "ego", (Actor("ego", "vehicle", (
        State(0.0, 0.0, 2.0, math.pi / 2, 1.0),
        State(1.0, 10.0, 2.0, math.pi / 2, 1.0),
    )),), "local_road_aligned")
    report = diagnose_lane_road_match(scenario, (_lane(),), lane_coordinate_frame="local_road_aligned", config=LaneRoadMatchConfig(0.5, 0.2))

    assert {item.reason for item in report.state_matches} == {"distance_and_heading_exceed_tolerance"}
    assert report.state_matches[0].lane_id == "lane"


def test_match_heading_wrap_and_deterministic_tie_break() -> None:
    scenario = Scenario("match", 1.0, "ego", (Actor("ego", "vehicle", (State(0.0, 5.0, 0.0, -math.pi + 0.01, 1.0),)),), "local_road_aligned")
    lanes = (_lane(yaw=math.pi - 0.01, lane_id="z-lane"), _lane(yaw=math.pi - 0.01, lane_id="a-lane"))
    report = diagnose_lane_road_match(scenario, lanes, lane_coordinate_frame="local_road_aligned", config=LaneRoadMatchConfig(0.5, 0.05))

    assert report.state_matches[0].lane_id == "a-lane"
    assert report.state_matches[0].matched


def test_match_selected_actors_and_frame_validation() -> None:
    report = diagnose_lane_road_match(_scenario(), (_lane(), _lane(y=2.0, lane_id="other-lane")), lane_coordinate_frame="local_road_aligned", actor_ids=("ego", "other"))
    assert report.selected_actor_ids == ("ego", "other")
    with pytest.raises(ValueError, match="coordinate_frame"):
        diagnose_lane_road_match(_scenario(), (_lane(),), lane_coordinate_frame="nuscenes_global")


def test_candidate_diagnostic_preserves_legacy_rank_one_and_exposes_alternatives() -> None:
    report = diagnose_nearest_lane_candidates(
        _scenario(), (_lane(0.0, lane_id="a"), _lane(1.0, lane_id="b")),
        lane_coordinate_frame="local_road_aligned", max_candidates=1,
    )

    assert report.states[0].candidate_count == 2
    assert len(report.states[0].candidates) == 1
    assert report.states[0].candidates[0].rank == 1
    assert report.states[0].candidates[0].lane_id == "a"


def test_footprint_occupancy_keeps_unsupported_dimensions_explicit() -> None:
    report = diagnose_lane_footprint_occupancy(
        _scenario(), (_lane(),), (LaneWidthRecord("lane", 3.5, "polygon"),),
        lane_coordinate_frame="local_road_aligned",
    )

    assert report.states[0].occupied is None
    assert report.states[0].reason == "vehicle_dimensions_unavailable"


def test_footprint_occupancy_uses_full_width_and_vehicle_dimensions() -> None:
    scenario = Scenario("match", 1.0, "ego", (Actor("ego", "vehicle", (
        State(0.0, 5.0, 0.0, 0.0, 1.0),
    ), length_m=4.0, width_m=1.8),), "local_road_aligned")
    report = diagnose_lane_footprint_occupancy(
        scenario, (_lane(),), (LaneWidthRecord("lane", 3.5, "polygon"),),
        lane_coordinate_frame="local_road_aligned",
    )

    assert report.states[0].occupied is True
    assert report.states[0].footprint_lateral_extent_m == pytest.approx(0.9)
    assert report.states[0].lane_width_source == "polygon"


def _sequence_scenario(states, *, dimensions=False) -> Scenario:
    actor = Actor("ego", "vehicle", tuple(states), length_m=4.0 if dimensions else None,
                  width_m=1.8 if dimensions else None)
    return Scenario("sequence", max(state.time_s for state in states) + 1.0, "ego", (actor,), "local_road_aligned")


def _lane_with_links(lane_id, y, *, successors=(), changes=(), polygon=True):
    return LaneCenterlineRecord(
        lane_id,
        (LaneCenterlinePose(0.0, y, 0.0), LaneCenterlinePose(10.0, y, 0.0)),
        successor_ids=tuple(successors),
        legal_lane_change_ids=tuple(changes),
        polygon=((0.0, y - 1.75), (10.0, y - 1.75), (10.0, y + 1.75), (0.0, y + 1.75)) if polygon else None,
        width_m=3.5 if polygon else None,
        width_source="polygon" if polygon else "unspecified",
    )


def test_sequence_match_preserves_legacy_and_decodes_declared_lane_change() -> None:
    states = (
        State(0.0, 0.0, 0.0, 0.0, 5.0),
        State(1.0, 5.0, 0.8, 0.0, 5.0),
        State(2.0, 10.0, 2.0, 0.0, 5.0),
    )
    scenario = _sequence_scenario(states, dimensions=True)
    lanes = (_lane_with_links("a", 0.0, changes=("b",)), _lane_with_links("b", 2.0))
    report = diagnose_lane_sequence_match(scenario, lanes, lane_coordinate_frame="local_road_aligned")

    assert [state.best_lane_id for state in report.states] == ["a", "a", "b"]
    assert report.per_actor[0].lane_switch_count == 1
    assert report.states[2].status in {"matched_high_confidence", "matched_low_confidence", "ambiguous_lane"}
    assert report.diagnostic_status == "diagnostic"
    assert report.scientific_status == "PROVISIONAL"


def test_sequence_match_rejects_undeclared_lane_change_as_topology_gap() -> None:
    states = (
        State(0.0, 0.0, 0.0, 0.0, 5.0),
        State(1.0, 5.0, 2.0, 0.0, 5.0),
        State(2.0, 10.0, 2.0, 0.0, 5.0),
    )
    report = diagnose_lane_sequence_match(
        _sequence_scenario(states),
        (_lane_with_links("a", 0.0), _lane_with_links("b", 2.0)),
        lane_coordinate_frame="local_road_aligned",
        config=LaneSequenceMatchConfig(topology_gap_penalty=50.0),
    )

    assert report.per_actor[0].topology_violation_count >= 1
    assert any(state.status == "unmatched_topology" for state in report.states)
    assert any("unresolved_topology_transition" in interval.reasons for interval in report.per_actor[0].ambiguous_intervals)


def test_sequence_match_reports_reverse_motion_without_mutating_lane_direction() -> None:
    states = (
        State(0.0, 10.0, 0.0, math.pi, 5.0),
        State(1.0, 5.0, 0.0, math.pi, 5.0),
        State(2.0, 0.0, 0.0, math.pi, 5.0),
    )
    report = diagnose_lane_sequence_match(
        _sequence_scenario(states), (_lane_with_links("forward", 0.0),),
        lane_coordinate_frame="local_road_aligned",
    )

    assert all(state.direction_classification == "motion_reverse_of_lane" for state in report.states)
    assert all(state.status == "direction_conflict" for state in report.states)
    assert report.lane_graph.lanes[0].travel_direction == "forward"


def test_sequence_match_keeps_noisy_outside_point_and_missing_dimensions_separate() -> None:
    states = (
        State(0.0, 0.0, 0.0, 0.0, 5.0),
        State(1.0, 5.0, 2.0, 0.0, 5.0),
        State(2.0, 10.0, 0.0, 0.0, 5.0),
    )
    report = diagnose_lane_sequence_match(
        _sequence_scenario(states), (_lane_with_links("lane", 0.0),),
        lane_coordinate_frame="local_road_aligned",
    )

    assert all(state.best_lane_id == "lane" for state in report.states)
    assert report.states[1].inside_polygon is False
    assert report.per_actor[0].unsupported_occupancy_count == 3
    assert report.per_actor[0].unmatched_state_count == 0


def test_sequence_match_is_deterministic_and_source_scenario_immutable() -> None:
    scenario = _sequence_scenario((State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 1.0, 0.0, 0.0, 1.0)))
    before = scenario
    lanes = (_lane_with_links("z", 0.0), _lane_with_links("a", 0.0))
    first = diagnose_lane_sequence_match(scenario, lanes, lane_coordinate_frame="local_road_aligned")
    second = diagnose_lane_sequence_match(scenario, lanes, lane_coordinate_frame="local_road_aligned")

    assert first == second
    assert scenario == before
    assert build_lane_graph(lanes).lanes[0].lane_id == "a"


def test_sequence_match_ambiguous_parallel_lanes_route_to_review() -> None:
    states = (State(0.0, 0.0, 1.0, 0.0, 1.0), State(1.0, 1.0, 1.0, 0.0, 1.0))
    report = diagnose_lane_sequence_match(
        _sequence_scenario(states), (_lane_with_links("a", 0.0), _lane_with_links("b", 2.0)),
        lane_coordinate_frame="local_road_aligned",
    )

    assert any(state.status == "ambiguous_lane" for state in report.states)
    assert report.per_actor[0].ambiguous_intervals


def test_source_reference_convention_is_explicit_and_uncorrected() -> None:
    from real2scenario.ingestion import source_reference_convention

    convention = source_reference_convention()

    assert convention["trajectory_position"] == "sample_annotation.translation_xy"
    assert convention["annotation_box_origin"] == "3D bounding-box center translation"
    assert convention["correction"] == "none"


def test_lane_reference_comparison_separates_polygon_and_centerline_status() -> None:
    scenario = _sequence_scenario((State(0.0, 0.0, 1.0, 0.0, 1.0),), dimensions=False)
    lane = LaneCenterlineRecord(
        "lane", (LaneCenterlinePose(0.0, 0.0, 0.0), LaneCenterlinePose(10.0, 0.0, 0.0)),
        polygon=((0.0, -2.0), (10.0, -2.0), (10.0, 2.0), (0.0, 2.0)),
    )
    report = compare_lane_references(
        scenario, (("native", build_lane_graph((lane,))),), actor_ids=("ego",), high_lateral_error_m=0.5
    )

    summary = report.summaries[0]
    assert summary.lane_semantically_valid_count == 1
    assert summary.lane_centerline_offset_high_count == 1
    assert summary.lane_polygon_outside_count == 0
    assert summary.footprint_unsupported_count == 1


def test_opendrive_reference_uses_declared_lane_width_offset() -> None:
    xml = """<OpenDRIVE><road name='source' id='r-source' length='10' junction='-1'><planView><geometry s='0' x='0' y='0' hdg='0' length='10'><line/></geometry></planView><lanes><laneSection s='0'><right><lane id='-1' type='driving' level='false'><width sOffset='0' a='4'/></lane></right></laneSection></lanes></road></OpenDRIVE>"""
    graph = lane_graph_from_opendrive(xml)

    assert graph.lanes[0].poses[0].y_m == pytest.approx(-2.0)


def test_sequence_triage_keeps_transform_hypotheses_counterfactual_and_compares_baseline() -> None:
    scenario = _sequence_scenario((State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 1.0, 0.0, 0.0, 1.0)))
    report = diagnose_lane_sequence_triage(
        scenario, (_lane_with_links("lane", 0.0),),
        lane_coordinate_frame="local_road_aligned",
        alignment_hypotheses=(("identity", 0.0, 0.0, 0.0), ("shifted", 0.0, 1.0, 0.0)),
    )

    assert [item.name for item in report.alignment_hypotheses] == ["identity", "shifted"]
    assert report.nearest_lane_changes == ()
    assert report.sequence_report.states[0].best_lane_id == "lane"
    assert report.scientific_status == "PROVISIONAL"


def test_sequence_graph_validates_missing_links_and_curved_centerline() -> None:
    curved = LaneCenterlineRecord(
        "curve",
        (LaneCenterlinePose(0.0, 0.0, 0.0), LaneCenterlinePose(5.0, 1.0, 0.2), LaneCenterlinePose(10.0, 3.0, 0.4)),
        predecessor_ids=("missing",),
    )
    graph = build_lane_graph((curved,))

    assert graph.lanes[0].length_m > 0
    assert any("unknown_topology_reference:missing" in failure for failure in graph.validation[0].failures)


def test_actor_reference_sensitivity_is_global_and_keeps_missing_dimensions_explicit() -> None:
    scenario = _sequence_scenario((State(0.0, 0.0, 0.0, 0.0, 1.0),), dimensions=False)
    graph = build_lane_graph((_lane_with_links("lane", 0.0),))

    report = analyze_actor_reference_sensitivity(scenario, (("native", graph),))

    assert [item.name for item in report.hypotheses] == [
        "annotation_center", "rear_axle", "front_axle", "fixed_heading_offset",
    ]
    assert len(report.rows) == 4
    assert [row.unsupported_state_count for row in report.rows] == [0, 1, 1, 0]
    assert all(row.actor_id == "ego" for row in report.rows)
    assert report.scientific_status == "PROVISIONAL"


def test_actor_reference_sensitivity_applies_one_declared_offset_to_all_states() -> None:
    scenario = _sequence_scenario((State(0.0, 0.0, 0.0, math.pi / 2, 1.0),), dimensions=True)
    graph = build_lane_graph((_lane_with_links("lane", 0.0),))

    report = analyze_actor_reference_sensitivity(
        scenario, (("native", graph),), fixed_heading_offset_m=0.25,
    )

    fixed = next(row for row in report.rows if row.hypothesis == "fixed_heading_offset")
    assert fixed.supported_state_count == 1
    assert fixed.unsupported_state_count == 0
    assert fixed.mean_lateral_error_m == pytest.approx(0.25)


def test_direction_counterfactual_preserves_lane_direction_and_reports_reverse_motion() -> None:
    states = (
        State(0.0, 10.0, 0.0, math.pi, 5.0),
        State(1.0, 5.0, 0.0, math.pi, 5.0),
        State(2.0, 0.0, 0.0, math.pi, 5.0),
    )
    scenario = _sequence_scenario(states)
    graph = build_lane_graph((_lane_with_links("forward", 0.0),))

    report = classify_direction_counterfactuals(scenario, (("native", graph),))

    assert len(report.states) == 3
    assert all(item.classification == "true_reverse_motion" for item in report.states)
    assert all(item.motion_heading_error_rad == pytest.approx(math.pi) for item in report.states)
    assert graph.lanes[0].travel_direction == "forward"


def test_sequence_match_accepts_declared_connector_transition() -> None:
    incoming = LaneCenterlineRecord(
        "incoming", (LaneCenterlinePose(0.0, 0.0, 0.0), LaneCenterlinePose(10.0, 0.0, 0.0)),
        successor_ids=("connector",),
    )
    connector = LaneCenterlineRecord(
        "connector", (LaneCenterlinePose(10.0, 0.0, 0.0), LaneCenterlinePose(12.0, 2.0, math.pi / 2)),
        predecessor_ids=("incoming",), is_connector=True, junction_id="j1",
    )
    states = (State(0.0, 5.0, 0.0, 0.0, 5.0), State(1.0, 10.5, 0.5, math.pi / 4, 5.0), State(2.0, 12.0, 2.0, math.pi / 2, 5.0))
    report = diagnose_lane_sequence_match(
        _sequence_scenario(states), (incoming, connector), lane_coordinate_frame="local_road_aligned"
    )

    assert report.states[-1].best_lane_id == "connector"
    assert report.per_actor[0].topology_violation_count == 0


def test_lane_road_match_evidence_round_trips_and_is_provisional() -> None:
    evidence = lane_road_match_evidence_from_report(_road_match_report_fixture())

    payload = lane_road_match_evidence_to_dict(evidence)

    assert payload["evidence_version"] == "lane-road-match-evidence-v1"
    assert payload["scientific_status"] == "PROVISIONAL"
    assert payload["diagnostic_status"] == "diagnostic"
    assert lane_road_match_evidence_from_dict(payload) == evidence
    assert evaluate_cp4_gates(_gate_scenario_fixture(), lane_match_report=evidence)[2].observed[
        "raw_match_rate"
    ] == evidence.overall.raw_match_rate


def test_lane_road_match_evidence_reader_is_fail_closed() -> None:
    payload = lane_road_match_evidence_to_dict(
        lane_road_match_evidence_from_report(_road_match_report_fixture())
    )

    with pytest.raises(ValueError, match="Unsupported lane road-match evidence fields"):
        lane_road_match_evidence_from_dict({**payload, "invented": 1})
    with pytest.raises(ValueError, match="scientific_status=PROVISIONAL"):
        lane_road_match_evidence_from_dict({**payload, "scientific_status": "FINAL"})
    with pytest.raises(ValueError, match="diagnostic_status=diagnostic"):
        lane_road_match_evidence_from_dict({**payload, "diagnostic_status": "accepted"})
    with pytest.raises(ValueError, match="raw_match_rate"):
        lane_road_match_evidence_from_dict(
            {
                **payload,
                "overall": {**payload["overall"], "raw_match_rate": 0.9},
            }
        )
    with pytest.raises(ValueError, match="provisional_95_status"):
        lane_road_match_evidence_from_dict(
            {**payload, "overall": dict(payload["overall"], provisional_95_status="unknown")}
        )
    with pytest.raises(ValueError, match="max_distance_m"):
        lane_road_match_evidence_from_dict({**payload, "config": {}})


def test_lane_road_match_evidence_is_accepted_by_the_g3_gate() -> None:
    evidence = lane_road_match_evidence_from_report(_road_match_report_fixture())
    gates = evaluate_cp4_gates(
        _gate_scenario_fixture(), lane_match_report=evidence, minimum_match_rate=0.0
    )

    assert gates[2].status == "pass"
    assert gates[2].scientific_status == "PROVISIONAL"
