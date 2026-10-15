from math import pi

import pytest

from real2scenario import (
    ALIGNMENT_METHOD,
    Actor,
    ReplayState,
    ReplayTrace,
    Scenario,
    State,
    compute_replay_metrics,
    compute_scenario_replay_metrics,
)
from real2scenario.metrics import aggregate_replay_metrics


def _state(time_s: float, x_m: float, yaw_rad: float = 0.0, speed_mps: float = 0.0) -> State:
    return State(time_s=time_s, x_m=x_m, y_m=0.0, yaw_rad=yaw_rad, speed_mps=speed_mps)


def test_metrics_align_replay_to_recorded_timestamps_with_known_values() -> None:
    recorded = (_state(0.0, 0.0, speed_mps=2.0), _state(1.0, 2.0, speed_mps=2.0), _state(2.0, 4.0, speed_mps=2.0))
    replayed = (_state(0.0, 0.0, speed_mps=1.0), _state(2.0, 2.0, speed_mps=3.0))

    metrics = compute_replay_metrics(recorded, replayed)

    assert metrics.sample_count == 3
    assert metrics.alignment_method == ALIGNMENT_METHOD
    assert metrics.position_rmse_m == pytest.approx((5 / 3) ** 0.5)
    assert metrics.final_displacement_m == pytest.approx(2.0)
    assert metrics.heading_mae_rad == 0.0
    assert metrics.speed_mae_mps == pytest.approx(2 / 3)
    assert metrics.ade_m == pytest.approx(1.0)
    assert metrics.fde_m == pytest.approx(2.0)
    assert metrics.coverage_status == "complete"


def test_metrics_wrap_heading_error_at_pi_boundary() -> None:
    metrics = compute_replay_metrics(
        (_state(0.0, 0.0, yaw_rad=pi - 0.01),),
        (_state(0.0, 0.0, yaw_rad=-pi + 0.01),),
    )

    assert metrics.heading_mae_rad == pytest.approx(0.02)


@pytest.mark.parametrize(
    ("recorded", "replayed", "message"),
    [
        ((), (_state(0.0, 0.0),), "Recorded trajectory is empty"),
        ((_state(0.0, 0.0),), (), "Replayed trajectory is empty"),
        ((_state(0.0, 0.0),), (_state(1.0, 0.0),), "overlapping"),
    ],
)
def test_metrics_reject_empty_or_mismatched_trajectories(
    recorded: tuple[State, ...], replayed: tuple[State, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        compute_replay_metrics(recorded, replayed)


def test_scenario_metrics_return_one_entry_per_actor() -> None:
    scenario = Scenario(
        scenario_id="metric-fixture",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle", (_state(0.0, 0.0), _state(1.0, 1.0))),
            Actor("lead", "vehicle", (_state(0.0, 3.0), _state(1.0, 4.0))),
        ),
        coordinate_frame="local_road_aligned",
    )
    trace = ReplayTrace(
        (
            ReplayState("ego", _state(0.0, 0.0)),
            ReplayState("lead", _state(0.0, 3.0)),
            ReplayState("ego", _state(1.0, 1.0)),
            ReplayState("lead", _state(1.0, 4.0)),
        )
    )

    result = compute_scenario_replay_metrics(scenario, trace)

    assert set(result) == {"ego", "lead"}
    assert result["ego"].position_rmse_m == 0.0


def test_metrics_report_insufficient_coverage_without_fabricating_fde() -> None:
    metrics = compute_replay_metrics(
        (_state(0.0, 0.0), _state(1.0, 1.0), _state(2.0, 2.0)),
        (_state(0.0, 0.0), _state(1.0, 1.0)),
    )

    assert metrics.coverage_status == "insufficient_coverage"
    assert metrics.sample_count == 2
    assert metrics.ade_m == 0.0
    assert metrics.fde_m is None


def test_short_tracks_are_reported_separately() -> None:
    scenario = Scenario(
        scenario_id="short-track-fixture",
        duration_s=2.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle", (_state(0.0, 0.0), _state(2.0, 2.0))),
            Actor("short", "vehicle", (_state(0.0, 3.0), _state(0.5, 3.5))),
        ),
        coordinate_frame="local_road_aligned",
    )
    trace = ReplayTrace(
        (
            ReplayState("ego", _state(0.0, 0.0)),
            ReplayState("ego", _state(2.0, 2.0)),
            ReplayState("short", _state(0.0, 3.0)),
            ReplayState("short", _state(0.5, 3.5)),
        )
    )

    result = compute_scenario_replay_metrics(scenario, trace, min_track_duration_s=2.0)

    assert set(result.metrics) == {"ego"}
    assert result.excluded_short_tracks == ("short",)


def test_metric_aggregate_reports_distribution_statistics() -> None:
    metrics = (
        compute_replay_metrics((_state(0.0, 0.0),), (_state(0.0, 1.0),)),
        compute_replay_metrics((_state(0.0, 0.0),), (_state(0.0, 3.0),)),
    )
    aggregate = aggregate_replay_metrics(metrics)
    assert aggregate.actor_count == 2
    assert aggregate.ade_m.mean == pytest.approx(2.0)
    assert aggregate.ade_m.median == pytest.approx(2.0)
    assert aggregate.ade_m.p95 == pytest.approx(3.0)
    assert aggregate.fde_m.max == pytest.approx(3.0)


def test_metric_aggregate_does_not_treat_incomplete_fde_as_zero() -> None:
    complete = compute_replay_metrics(
        (_state(0.0, 0.0), _state(1.0, 1.0)),
        (_state(0.0, 0.0), _state(1.0, 2.0)),
    )
    incomplete = compute_replay_metrics(
        (_state(0.0, 0.0), _state(1.0, 1.0)),
        (_state(0.0, 0.0), _state(0.5, 2.0)),
    )

    aggregate = aggregate_replay_metrics((complete, incomplete))

    assert aggregate.actor_count == 2
    assert aggregate.fde_m is not None
    assert aggregate.fde_m.mean == pytest.approx(1.0)
