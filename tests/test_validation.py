import pytest

from real2scenario import (
    VALIDATION_VERSION,
    Actor,
    FeasibilityLimits,
    RoadBoundary,
    Scenario,
    State,
    validate_feasibility,
)


def _scenario(states: tuple[State, ...]) -> Scenario:
    return Scenario(
        scenario_id="validation-fixture",
        duration_s=states[-1].time_s,
        ego_actor_id="ego",
        actors=(Actor("ego", "vehicle", states),),
        coordinate_frame="local_road_aligned",
    )


def test_exact_kinematic_limits_are_valid() -> None:
    scenario = _scenario(
        (
            State(0.0, 0.0, 0.0, 0.0, 0.0),
            State(1.0, 1.0, 0.0, 0.5, 2.0),
            State(2.0, 2.0, 0.0, 1.0, 0.0),
        )
    )

    report = validate_feasibility(
        scenario,
        FeasibilityLimits(
            max_acceleration_mps2=2.0,
            max_deceleration_mps2=2.0,
            max_jerk_mps3=4.0,
            max_yaw_rate_rps=0.5,
            version="limits-test-v1",
        ),
    )

    assert report.valid
    assert report.reasons == ()
    assert report.validation_version == "limits-test-v1"


def test_exceeded_kinematic_limits_return_all_structured_reasons() -> None:
    scenario = _scenario(
        (
            State(0.0, 0.0, 0.0, 0.0, 0.0),
            State(1.0, 1.0, 0.0, 1.0, 3.0),
            State(2.0, 2.0, 0.0, 2.0, 0.0),
        )
    )

    report = validate_feasibility(
        scenario,
        FeasibilityLimits(
            max_acceleration_mps2=2.0,
            max_deceleration_mps2=2.0,
            max_jerk_mps3=4.0,
            max_yaw_rate_rps=0.5,
        ),
    )

    assert not report.valid
    assert {reason.code for reason in report.reasons} == {
        "acceleration_exceeded",
        "deceleration_exceeded",
        "jerk_exceeded",
        "yaw_rate_exceeded",
    }
    assert all(reason.category == "kinematic" for reason in report.reasons)
    assert all(reason.actor_id == "ego" for reason in report.reasons)
    assert all(reason.observed is not None and reason.limit is not None for reason in report.reasons)


def test_road_boundary_accepts_edges_and_reports_each_outside_coordinate() -> None:
    scenario = _scenario(
        (
            State(0.0, 0.0, 0.0, 0.0, 0.0),
            State(1.0, 1.0, 1.0, 0.0, 0.0),
            State(2.0, 1.1, -1.1, 0.0, 0.0),
        )
    )
    limits = FeasibilityLimits(
        max_acceleration_mps2=0.0,
        max_deceleration_mps2=0.0,
        max_jerk_mps3=0.0,
        max_yaw_rate_rps=0.0,
        road_boundary=RoadBoundary(0.0, 1.0, -1.0, 1.0),
    )

    report = validate_feasibility(scenario, limits)

    assert not report.valid
    assert {reason.code for reason in report.reasons} == {"road_boundary_x", "road_boundary_y"}
    assert len(report.reasons) == 2
    assert all(reason.category == "road" for reason in report.reasons)


def test_validation_checks_every_actor_and_state() -> None:
    ego = Actor(
        "ego",
        "vehicle",
        (State(0.0, 0.0, 0.0, 0.0, 0.0), State(1.0, 1.0, 0.0, 0.0, 5.0)),
    )
    lead = Actor(
        "lead",
        "vehicle",
        (State(0.0, 0.0, 0.0, 0.0, 0.0), State(1.0, 1.0, 0.0, 0.0, 5.0)),
    )
    scenario = Scenario(
        "multi-actor-validation",
        1.0,
        "ego",
        (ego, lead),
        "local_road_aligned",
    )

    report = validate_feasibility(scenario, FeasibilityLimits(max_acceleration_mps2=1.0))

    assert len(report.reasons) == 2
    assert {reason.actor_id for reason in report.reasons} == {"ego", "lead"}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_acceleration_mps2": -1.0}, "non-negative"),
        ({"max_deceleration_mps2": float("nan")}, "non-negative"),
        ({"max_jerk_mps3": float("inf")}, "non-negative"),
        ({"max_yaw_rate_rps": -0.1}, "non-negative"),
        ({"version": ""}, "version"),
    ],
)
def test_limits_reject_invalid_configuration(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        FeasibilityLimits(**kwargs)  # type: ignore[arg-type]


def test_road_boundary_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="minimums"):
        RoadBoundary(1.0, 0.0, 0.0, 1.0)


def test_default_validation_version_is_explicit() -> None:
    assert FeasibilityLimits().version == VALIDATION_VERSION
