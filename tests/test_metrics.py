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
