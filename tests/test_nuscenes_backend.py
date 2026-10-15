from real2scenario.nuscenes_backend import (
    CanPoseSample,
    CanVehicleMonitorSample,
    NuScenesSourceAdapter,
    _normalize_can_pose,
    _normalize_vehicle_monitor,
    nearest_can_poses,
)


def test_nearest_can_poses_matches_without_extrapolating() -> None:
    poses = (CanPoseSample(1_000, 2.0, None, None), CanPoseSample(2_000, 3.0, None, None))

    matches = nearest_can_poses((900, 2_050, 10_000), poses, max_gap_us=200)

    assert matches[0] == poses[0]
    assert matches[1] == poses[1]
    assert matches[2] is None


def test_vehicle_monitor_normalization_rejects_non_numeric_or_missing_brake() -> None:
    normalized = _normalize_vehicle_monitor({"utime": 1_500, "brake": 0.25})
    missing_brake = _normalize_vehicle_monitor({"utime": 1_500})
    non_numeric = _normalize_vehicle_monitor({"utime": 1_500, "brake": "on"})
    missing_timestamp = _normalize_vehicle_monitor({"brake": 0.25})

    assert normalized == CanVehicleMonitorSample(1_500, 0.25)
    assert missing_brake is None
    assert non_numeric is None
    assert missing_timestamp is None


def test_can_pose_normalization_keeps_partial_messages_with_a_source() -> None:
    assert _normalize_can_pose({"utime": 10, "vel": [3.0, 4.0, 0.0]}) == CanPoseSample(
        10, 5.0, None, None
    )
    assert _normalize_can_pose({"utime": 10}) is None


def test_vehicle_monitor_channel_fails_closed_without_a_dataset(tmp_path) -> None:
    adapter = NuScenesSourceAdapter(tmp_path / "missing-dataset")

    assert adapter.can_vehicle_monitor("scene-0001") == ()