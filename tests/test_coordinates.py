from math import pi

import pytest

from real2scenario import (
    Actor,
    COORDINATE_TRANSFORM_VERSION,
    RoadAlignedTransform,
    Scenario,
    State,
    transform_to_local_road_aligned,
)


def _source_scenario() -> Scenario:
    ego = Actor(
        actor_id="ego",
        actor_type="vehicle.ego",
        trajectory=(
            State(time_s=0.0, x_m=100.0, y_m=200.0, yaw_rad=pi / 2, speed_mps=5.0),
            State(time_s=1.0, x_m=100.0, y_m=205.0, yaw_rad=pi / 2, speed_mps=5.0),
        ),
    )
    actor = Actor(
        actor_id="lead",
        actor_type="vehicle.car",
        trajectory=(
            State(time_s=0.0, x_m=98.0, y_m=210.0, yaw_rad=pi / 2, speed_mps=4.0),
        ),
    )
    return Scenario(
        scenario_id="coordinate-fixture",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(ego, actor),
        coordinate_frame="nuscenes_global",
        provenance={"dataset": "synthetic", "coordinate_transform_version": "source-global-v1"},
    )


def test_transform_converts_a_known_point_and_records_metadata() -> None:
    local = transform_to_local_road_aligned(
        _source_scenario(),
        RoadAlignedTransform(origin_x_m=100.0, origin_y_m=200.0, heading_rad=pi / 2),
    )

    ego, lead = local.actors
    assert local.coordinate_frame == "local_road_aligned"
    assert (ego.trajectory[1].x_m, ego.trajectory[1].y_m, ego.trajectory[1].yaw_rad) == pytest.approx(
        (5.0, 0.0, 0.0)
    )
    assert (lead.trajectory[0].x_m, lead.trajectory[0].y_m) == pytest.approx((10.0, 2.0))
    assert local.provenance["coordinate_transform_version"] == COORDINATE_TRANSFORM_VERSION
    assert local.provenance["coordinate_transform_axes"] == "x_forward_m,y_left_m,z_up_m"
    assert local.provenance["coordinate_transform_origin_x_m"] == "100"
    assert local.provenance["coordinate_transform_heading_rad"] == format(pi / 2, ".17g")


def test_transform_round_trip_stays_within_configured_tolerance() -> None:
    transform = RoadAlignedTransform(
        origin_x_m=-50.25,
        origin_y_m=11.5,
        heading_rad=-1.1,
        round_trip_tolerance_m=1e-10,
    )
    source = State(time_s=3.0, x_m=123.4, y_m=-8.9, yaw_rad=2.7, speed_mps=12.5)

    reconstructed = transform.to_source_state(transform.to_local_state(source))

    assert reconstructed.time_s == source.time_s
    assert reconstructed.x_m == pytest.approx(source.x_m, abs=transform.round_trip_tolerance_m)
    assert reconstructed.y_m == pytest.approx(source.y_m, abs=transform.round_trip_tolerance_m)
    assert reconstructed.yaw_rad == pytest.approx(source.yaw_rad, abs=transform.round_trip_tolerance_m)
    assert reconstructed.speed_mps == source.speed_mps


@pytest.mark.parametrize(
    ("source_yaw_rad", "heading_rad", "expected_yaw_rad"),
    [
        (pi, 0.0, -pi),
        (-pi, 0.0, -pi),
        (pi - 0.01, -0.02, -pi + 0.01),
        (-pi + 0.01, 0.02, pi - 0.01),
    ],
)
def test_transform_wraps_yaw_at_pi_boundaries(
    source_yaw_rad: float, heading_rad: float, expected_yaw_rad: float
) -> None:
    transform = RoadAlignedTransform(origin_x_m=0.0, origin_y_m=0.0, heading_rad=heading_rad)
    local = transform.to_local_state(
        State(time_s=0.0, x_m=0.0, y_m=0.0, yaw_rad=source_yaw_rad, speed_mps=0.0)
    )

    assert local.yaw_rad == pytest.approx(expected_yaw_rad)


def test_transform_does_not_mutate_the_source_scenario() -> None:
    source = _source_scenario()
    local = transform_to_local_road_aligned(
        source, RoadAlignedTransform(origin_x_m=100.0, origin_y_m=200.0, heading_rad=0.0)
    )

    assert source.coordinate_frame == "nuscenes_global"
    assert source.actors[0].trajectory[0].x_m == 100.0
    assert "coordinate_transform_origin_x_m" not in source.provenance
    assert local is not source


def test_transform_rejects_mismatched_source_frame() -> None:
    source = _source_scenario()
    transform = RoadAlignedTransform(
        origin_x_m=0.0, origin_y_m=0.0, heading_rad=0.0, source_frame="other_global"
    )

    with pytest.raises(ValueError, match="coordinate_frame"):
        transform_to_local_road_aligned(source, transform)


@pytest.mark.parametrize("tolerance_m", [0.0, -0.01])
def test_transform_rejects_non_positive_round_trip_tolerance(tolerance_m: float) -> None:
    with pytest.raises(ValueError, match="tolerance"):
        RoadAlignedTransform(
            origin_x_m=0.0,
            origin_y_m=0.0,
            heading_rad=0.0,
            round_trip_tolerance_m=tolerance_m,
        )
