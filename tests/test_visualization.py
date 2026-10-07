from pathlib import Path

from real2scenario import Actor, Scenario, State
from real2scenario.visualization import _state_at_or_before, save_top_down_plot


def _scenario() -> Scenario:
    return Scenario(
        scenario_id="visualization-fixture",
        duration_s=10.0,
        ego_actor_id="ego",
        actors=(
            Actor(
                actor_id="ego",
                actor_type="vehicle",
                trajectory=(
                    State(0.0, 0.0, 0.0, 0.0, 1.0),
                    State(10.0, 10.0, 0.0, 0.0, 1.0),
                ),
            ),
            Actor(
                actor_id="lead",
                actor_type="vehicle",
                trajectory=(
                    State(2.0, 2.0, 1.0, 0.0, 1.0),
                    State(10.0, 12.0, 1.0, 0.0, 1.0),
                ),
            ),
        ),
        coordinate_frame="nuscenes_global",
    )


def test_state_at_or_before_handles_actor_late_appearance() -> None:
    actor = _scenario().actors[1]

    assert _state_at_or_before(actor, 1.0) is None
    assert _state_at_or_before(actor, 2.0) == actor.trajectory[0]
    assert _state_at_or_before(actor, 8.0) == actor.trajectory[0]
    assert _state_at_or_before(actor, 10.0) == actor.trajectory[1]


def test_save_top_down_plot_creates_png(tmp_path: Path) -> None:
    output = tmp_path / "top-down.png"

    save_top_down_plot(_scenario(), output, time_s=5.0)

    assert output.is_file()
    assert output.stat().st_size > 0
