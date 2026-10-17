import pytest

from r2s_web.camera_projection import project_camera_point, project_camera_points


INTRINSIC = (
    (100.0, 0.0, 50.0),
    (0.0, 100.0, 40.0),
    (0.0, 0.0, 1.0),
)


def test_project_camera_point_uses_pinhole_intrinsics():
    point = project_camera_point((1.0, 2.0, 10.0), INTRINSIC)

    assert point is not None
    assert point.u == pytest.approx(60.0)
    assert point.v == pytest.approx(60.0)
    assert point.depth_m == 10.0


def test_projection_drops_points_behind_camera():
    points = project_camera_points(((0.0, 0.0, 2.0), (0.0, 0.0, 0.05)), INTRINSIC)

    assert len(points) == 1
    assert points[0].u == pytest.approx(50.0)


def test_projection_rejects_invalid_geometry():
    with pytest.raises(ValueError, match="must_be_3d"):
        project_camera_point((1.0, 2.0), INTRINSIC)


def test_projection_rejects_invalid_depth_or_intrinsic_values():
    with pytest.raises(ValueError, match="min_depth_invalid"):
        project_camera_point((1.0, 2.0, 3.0), INTRINSIC, min_depth_m=0.0)
    with pytest.raises(ValueError, match="intrinsic_not_finite"):
        project_camera_point((1.0, 2.0, 3.0), ((float("nan"), 0.0, 0.0), INTRINSIC[1], INTRINSIC[2]))
