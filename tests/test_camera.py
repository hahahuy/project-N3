from r2s_web.camera import CameraEvidenceService
from r2s_web.preview_time import resolve_preview_time


def test_camera_frame_keeps_recorded_and_canonical_cuboids_separate():
    service = CameraEvidenceService(resolve_preview_time)

    frame = service.frame(
        channel="CAM_FRONT",
        requested_time_s=0.4,
        timestamps_us=(1_000_000, 1_500_000),
        image={"url": "/private/cam.jpg"},
        recorded_cuboids=({"token": "annotation-1"},),
        canonical_cuboids=({"actor_id": "ego"},),
    )

    assert frame.contract_version == "nuscenes-camera-evidence-v1"
    assert frame.timestamp_us == 1_500_000
    assert frame.recorded_cuboids[0]["token"] == "annotation-1"
    assert frame.canonical_cuboids[0]["actor_id"] == "ego"


def test_camera_frame_projects_lidar_without_mutating_input():
    service = CameraEvidenceService(resolve_preview_time)
    intrinsic = ((100.0, 0.0, 50.0), (0.0, 100.0, 40.0), (0.0, 0.0, 1.0))

    frame = service.frame(
        channel="CAM_FRONT",
        requested_time_s=0.0,
        timestamps_us=(1_000_000,),
        image={"url": "/private/cam.jpg"},
        lidar_points_camera=((1.0, 0.0, 10.0),),
        intrinsic=intrinsic,
    )

    assert len(frame.lidar_points) == 1
    assert frame.lidar_points[0].u == 60.0
    assert frame.provenance["source"] == "nuscenes-devkit-camera-evidence"


def test_camera_frame_contract_can_carry_independent_overlay_layers():
    service = CameraEvidenceService(resolve_preview_time)

    frame = service.frame(
        channel="CAM_BACK",
        requested_time_s=0.0,
        timestamps_us=(1_000_000,),
        image={"url": "/api/workspace/camera-image/sd-1"},
        recorded_cuboids=({"token": "ann-1", "visibility": "recorded_annotation"},),
        canonical_cuboids=({"actor_id": "ego", "visibility": "canonical_scenario"},),
    )

    assert frame.recorded_cuboids[0]["visibility"] != frame.canonical_cuboids[0]["visibility"]


def test_camera_frame_keeps_projected_lidar_points_as_display_data():
    service = CameraEvidenceService(resolve_preview_time)

    frame = service.frame(
        channel="CAM_FRONT",
        requested_time_s=0.0,
        timestamps_us=(1_000_000,),
        image={"url": "/api/workspace/camera-image/sd-1"},
        lidar_points_camera=((1.0, 0.0, 10.0),),
        intrinsic=((100.0, 0.0, 50.0), (0.0, 100.0, 40.0), (0.0, 0.0, 1.0)),
    )

    assert len(frame.lidar_points) == 1
    assert frame.lidar_points[0].depth_m == 10.0
