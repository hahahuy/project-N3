import pytest

from real2scenario import Actor, FeasibilityLimits, Scenario, State
from real2scenario.gates import evaluate_g4_g5


def _scenario(*, event: bool = True, collision: bool = False) -> Scenario:
    lead_x = 1.0 if collision else 10.0
    provenance = (
        {
            "main_event_start_s": "1.0",
            "main_event_end_s": "2.0",
            "event_type": "lead_braking",
            "event_target_actor_id": "lead",
        }
        if event
        else {}
    )
    return Scenario(
        scenario_id="gate-evaluator",
        duration_s=2.0,
        ego_actor_id="ego",
        coordinate_frame="local_road_aligned",
        provenance=provenance,
        actors=(
            Actor("ego", "vehicle", (State(0, 0, 0, 0, 1), State(1, 1, 0, 0, 1), State(2, 2, 0, 0, 1)), 4.0, 2.0),
            Actor("lead", "vehicle", (State(0, lead_x, 0, 0, 1), State(1, lead_x + 1, 0, 0, 1), State(2, lead_x + 2, 0, 0, 1)), 4.0, 2.0),
        ),
    )


def test_g4_and_g5_pass_for_non_collision_with_event_metadata() -> None:
    result = evaluate_g4_g5(_scenario(), limits=FeasibilityLimits())
    assert result["G4"].status == "pass"
    assert result["G5"].status == "pass"


def test_g5_reports_collision_before_event() -> None:
    result = evaluate_g4_g5(_scenario(collision=True), limits=FeasibilityLimits())
    assert result["G5"].status == "fail"
    assert "collision_before_main_event" in result["G5"].reasons


def test_g5_checks_collision_at_the_event_window_state() -> None:
    scenario = _scenario(collision=False)
    actors = list(scenario.actors)
    lead = actors[1]
    actors[1] = Actor(
        "lead",
        "vehicle",
        (State(0, 10, 0, 0, 1), State(1, 1, 0, 0, 1), State(2, 2, 0, 0, 1)),
        4.0,
        2.0,
    )
    provenance = dict(scenario.provenance)
    provenance["main_event_start_s"] = "1.5"
    scenario = Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=scenario.ego_actor_id,
        coordinate_frame=scenario.coordinate_frame,
        provenance=provenance,
        actors=tuple(actors),
    )
    result = evaluate_g4_g5(scenario, limits=FeasibilityLimits())
    assert result["G5"].status == "fail"


def test_g5_skips_when_no_event_is_declared() -> None:
    result = evaluate_g4_g5(_scenario(event=False), limits=FeasibilityLimits())
    assert result["G5"].status == "skipped"
    assert result["G5"].reasons == ("event_definition_not_declared",)


def test_g5_ignores_collisions_at_or_after_the_event_start() -> None:
    scenario = _scenario(event=False)
    actors = list(scenario.actors)
    actors[1] = Actor(
        "lead",
        "vehicle",
        (State(0, 10, 0, 0, 1), State(1, 1, 0, 0, 1), State(2, 2, 0, 0, 1)),
        4.0,
        2.0,
    )
    declaration = {
        "main_event_start_s": 1.0,
        "main_event_end_s": 2.0,
        "event_type": "lead_braking",
        "event_target_actor_id": "lead",
    }

    result = evaluate_g4_g5(
        Scenario(
            scenario_id=scenario.scenario_id,
            duration_s=scenario.duration_s,
            ego_actor_id=scenario.ego_actor_id,
            coordinate_frame=scenario.coordinate_frame,
            provenance={},
            actors=tuple(actors),
        ),
        limits=FeasibilityLimits(),
        event_declaration=declaration,
    )

    assert result["G5"].status == "pass"
    assert result["G5"].observed["event_source"] == "scenario_provenance"


def test_g5_uses_an_explicit_declaration_without_scenario_provenance() -> None:
    result = evaluate_g4_g5(
        _scenario(event=False),
        limits=FeasibilityLimits(),
        event_declaration={
            "main_event_start_s": 1.0,
            "main_event_end_s": 2.0,
            "event_type": "lead_braking",
            "event_target_actor_id": "lead",
            "event_source": "operator_declared",
        },
    )

    assert result["G5"].status == "pass"
    assert result["G5"].observed["event_source"] == "operator_declared"


def test_g5_errors_on_a_malformed_declaration() -> None:
    for declaration, reason in (
        ({"main_event_start_s": 2.0, "main_event_end_s": 1.0, "event_type": "x",
          "event_target_actor_id": "lead"}, "invalid_event_window"),
        ({"main_event_start_s": 0.5, "main_event_end_s": 9.0, "event_type": "x",
          "event_target_actor_id": "lead"}, "event_window_outside_scenario"),
        ({"main_event_start_s": 0.5, "main_event_end_s": 1.5, "event_type": "x",
          "event_target_actor_id": "missing"}, "unknown_event_target"),
    ):
        result = evaluate_g4_g5(
            _scenario(event=False), limits=FeasibilityLimits(), event_declaration=declaration
        )
        assert result["G5"].status == "error", declaration
        assert result["G5"].reasons == (reason,)


def test_g5_rejects_unknown_or_incomplete_declaration_fields() -> None:
    complete = {
        "main_event_start_s": 1.0,
        "main_event_end_s": 2.0,
        "event_type": "lead_braking",
        "event_target_actor_id": "lead",
    }
    with pytest.raises(ValueError, match="unsupported_event_fields"):
        evaluate_g4_g5(_scenario(), event_declaration={**complete, "invented_s": 1})
    with pytest.raises(ValueError, match="incomplete_event_declaration"):
        evaluate_g4_g5(_scenario(), event_declaration={"main_event_start_s": 1.0})
