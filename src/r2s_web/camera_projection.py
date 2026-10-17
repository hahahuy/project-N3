"""Pure nuScenes-style camera projection primitives for preview overlays.

The functions here operate on already-resolved sensor geometry. They do not
load dataset files, mutate scenarios, or participate in replay metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


@dataclass(frozen=True, slots=True)
class ProjectedPoint:
    u: float
    v: float
    depth_m: float


def project_camera_point(
    point_camera: Sequence[float],
    intrinsic: Sequence[Sequence[float]],
    *,
    min_depth_m: float = 0.1,
) -> ProjectedPoint | None:
    """Project one camera-frame point using a 3x3 pinhole intrinsic matrix."""
    if len(point_camera) != 3 or len(intrinsic) != 3 or any(len(row) != 3 for row in intrinsic):
        raise ValueError("camera_projection_geometry_must_be_3d")
    if not isfinite(float(min_depth_m)) or min_depth_m <= 0:
        raise ValueError("camera_projection_min_depth_invalid")
    try:
        matrix = tuple(tuple(float(value) for value in row) for row in intrinsic)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("camera_projection_intrinsic_not_numeric") from error
    if any(not isfinite(value) for row in matrix for value in row):
        raise ValueError("camera_projection_intrinsic_not_finite")
    x, y, depth = (float(value) for value in point_camera)
    if not all(isfinite(value) for value in (x, y, depth)):
        raise ValueError("camera_projection_point_not_finite")
    if depth <= min_depth_m:
        return None
    u = (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * depth) / depth
    v = (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * depth) / depth
    if not all(isfinite(value) for value in (u, v)):
        raise ValueError("camera_projection_result_not_finite")
    return ProjectedPoint(u=u, v=v, depth_m=depth)


def project_camera_points(
    points_camera: Sequence[Sequence[float]],
    intrinsic: Sequence[Sequence[float]],
    *,
    min_depth_m: float = 0.1,
) -> list[ProjectedPoint]:
    """Project visible points, preserving input order and dropping behind-camera points."""
    return [
        projected
        for point in points_camera
        if (projected := project_camera_point(point, intrinsic, min_depth_m=min_depth_m)) is not None
    ]
