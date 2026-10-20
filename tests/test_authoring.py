import pytest

from real2scenario import Actor, CanvasKeyframe, Scenario, State, build_canvas_keyframe_branch


def _scenario() -> Scenario:
    provenance = {
        "dataset_name": "synthetic", "dataset_version": "v1", "source_scene_token": "scene-1",
        "source_window": "0-2", "coordinate_transform_version": "v1",
        "map_reconstruction_mode": "template", "map_reconstruction_version": "v1",
        "generator_version": "test",
    }
    return Scenario("parent", 2.0, "ego", (
        Actor("ego", "vehicle.ego", (State(0, 0, 0, 0, 1), State(2, 2, 0, 0, 1)), 4, 2),
        Actor("lead", "vehicle.car", (State(0, 10, 0, 0, 1), State(2, 12, 0, 0, 1)), 4, 2),
    ), "local_road_aligned", provenance)


def _keyframes():
    return (
        CanvasKeyframe("k0", 0, 10, 0, 3.13, 1),
        CanvasKeyframe("k1", 1, 10, 2, -3.13, 2),
    )


def test_canvas_branch_is_deterministic_and_preserves_parent():
    parent = _scenario()
    first = build_canvas_keyframe_branch(parent, "lead", _keyframes())
    second = build_canvas_keyframe_branch(parent, "lead", _keyframes())
    assert first == second
    assert first.scenario.scenario_id.startswith("parent--canvas-")
    assert first.scenario.provenance["snap_to_lane"] == "disabled_free_motion"
    assert first.scenario.actors[1].trajectory[1].yaw_rad > 3.13
    assert parent.actors[1].trajectory[1] == State(2, 12, 0, 0, 1)


@pytest.mark.parametrize("keyframes", [
    (CanvasKeyframe("k0", 0, 0, 0, 0, 1), CanvasKeyframe("k1", 0, 1, 0, 0, 1)),
    (CanvasKeyframe("k0", 0, 0, 0, 0, 1),),
])
def test_canvas_branch_rejects_invalid_keyframe_order(keyframes):
    with pytest.raises(ValueError):
        build_canvas_keyframe_branch(_scenario(), "lead", keyframes)


def test_canvas_branch_locks_origin_and_rejects_short_intervals():
    parent = _scenario()
    with pytest.raises(ValueError, match="origin position"):
        build_canvas_keyframe_branch(parent, "lead", (
            CanvasKeyframe("k0", 0, 11, 0, 0, 1),
            CanvasKeyframe("k1", 1, 12, 0, 0, 1),
        ))
    with pytest.raises(ValueError, match="at least 0.25s"):
        build_canvas_keyframe_branch(parent, "lead", (
            CanvasKeyframe("k0", 0, 10, 0, 0, 1),
            CanvasKeyframe("k1", 0.1, 10.2, 0, 0, 1),
        ))


def test_canvas_branch_keeps_origin_duration_as_horizon():
    with pytest.raises(ValueError, match="origin scenario duration"):
        build_canvas_keyframe_branch(_scenario(), "lead", (
            CanvasKeyframe("k0", 0, 10, 0, 0, 1),
            CanvasKeyframe("k1", 2.1, 12, 0, 0, 1),
        ))


def test_canvas_branch_rejects_sharp_turns():
    with pytest.raises(ValueError, match="turn angle"):
        build_canvas_keyframe_branch(_scenario(), "lead", (
            CanvasKeyframe("k0", 0, 10, 0, 0, 1),
            CanvasKeyframe("k1", 1, 11, 1, 1.2, 1),
            CanvasKeyframe("k2", 2, 12, 0, 2.4, 1),
        ))


def test_canvas_branch_rejects_unwrapped_full_turn():
    with pytest.raises(ValueError, match="yaw rate"):
        build_canvas_keyframe_branch(_scenario(), "lead", (
            CanvasKeyframe("k0", 0, 10, 0, 0, 1),
            CanvasKeyframe("k1", 1, 12, 0, 2 * 3.141592653589793, 1),
        ))
