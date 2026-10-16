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


class _BareExceptionCanBus:
    """Mimics the devkit, which signals missing CAN data with a bare Exception."""

    all_messages = ("pose", "vehicle_monitor")

    def get_messages(self, scene_name, message_name, print_warnings=True):
        raise Exception(f"Error: {scene_name} does not have any CAN bus data!")


def test_missing_can_pose_degrades_to_empty_capability_result(tmp_path, monkeypatch) -> None:
    """Contract conformance: unavailable CAN must not abort the run.

    CAN pose is optional and documented to fall back to finite differences, so a
    scene without CAN data must yield an empty capability result rather than
    propagating the devkit's bare Exception out of the adapter.
    """
    (tmp_path / "can_bus").mkdir()
    adapter = NuScenesSourceAdapter(tmp_path)
    monkeypatch.setattr(
        "nuscenes.can_bus.can_bus_api.NuScenesCanBus", lambda **kwargs: _BareExceptionCanBus()
    )

    assert adapter.can_pose("scene-0001") == ()
    assert adapter.can_vehicle_monitor("scene-0001") == ()
    assert adapter._can_error == "Exception"
