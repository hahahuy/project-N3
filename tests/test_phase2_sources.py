from real2scenario import (
    CanPoseSample,
    Actor,
    CollisionCheck,
    KinematicLimits,
    State,
    build_source_state_extension,
    evaluate_prediction_advisory,
    integrate_kinematic_open_loop,
    lidar_payload_contract,
    native_map_records,
    native_map_patch,
    check_footprint_collisions,
)


def test_source_state_uses_can_and_explicitly_falls_back() -> None:
    extension = build_source_state_extension(
        (0, 1_000_000, 2_000_000),
        ((0.0, 0.0), (1.0, 0.0), (3.0, 0.0)),
        (0.0, 0.1, 0.2),
        (CanPoseSample(0, 1.0, 2.5, 0.4),),
        max_gap_us=10,
    )
    assert extension.version == "source-state-extension-v1"
    assert extension.states[0].acceleration_source == "can_pose"
    assert extension.states[1].yaw_rate_source == "finite_difference"
    assert extension.provenance["source_state_fallback"] == "explicit_finite_difference"


def test_tier1_preview_keeps_canonical_state_shape() -> None:
    extension = build_source_state_extension((0, 1_000_000), ((0.0, 0.0), (1.0, 0.0)), (0.0, 0.0))
    preview = integrate_kinematic_open_loop(State(0.0, 0.0, 0.0, 0.0, 2.0), extension)
    assert preview.provenance["simulator_version"] == "kinematic-open-loop-v1"
    assert preview.states[1].speed_mps == 2.0
    assert not hasattr(preview.states[0], "acceleration_mps2")
    assert preview.trace is not None
    assert preview.trace.states_for("ego")[1].speed_mps == 2.0


def test_tier1_reports_limits_without_silent_clamping() -> None:
    extension = build_source_state_extension(
        (0, 50_000, 100_000),
        ((0.0, 0.0), (0.1, 0.0), (0.2, 0.0)),
        (0.0, 0.0, 0.0),
        (CanPoseSample(0, 1.0, -100.0, 0.0), CanPoseSample(50_000, 1.0, -100.0, 0.0)),
    )
    preview = integrate_kinematic_open_loop(
        State(0.0, 0.0, 0.0, 0.0, 1.0), extension,
        limits=KinematicLimits(max_deceleration_mps2=1.0),
    )
    assert preview.states[1].speed_mps < 0.0
    assert any(reason.code == "deceleration_exceeded" for reason in preview.violations)
    assert any(reason.code == "negative_speed" for reason in preview.violations)


def test_footprint_collision_check_fails_closed_without_dimensions() -> None:
    state = State(0.0, 0.0, 0.0, 0.0, 0.0)
    missing = Actor("a", "vehicle", (state,))
    assert check_footprint_collisions((missing,)).status == "unsupported"


def test_footprint_collision_check_reports_collision() -> None:
    first = Actor("a", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 0.0),), 4.0, 2.0)
    second = Actor("b", "vehicle", (State(0.0, 1.0, 0.0, 0.0, 0.0),), 4.0, 2.0)
    result = check_footprint_collisions((first, second))
    assert result.status == "collision"
    assert result.collisions[0]["left_actor_id"] == "a"


def test_native_map_layers_are_read_only_and_sorted() -> None:
    api = type("Map", (), {"road_segment": [{"token": "b"}, {"token": "a"}]})()
    assert [record["token"] for record in native_map_records(api, "road_segment")] == ["a", "b"]


def test_native_map_patch_is_versioned_and_private() -> None:
    class Map:
        def get_records_in_patch(self, patch, layers):
            assert patch == [0.0, 0.0, 10.0, 10.0]
            return {"road_segment": ["road-b", "road-a"]}

    result = native_map_patch(Map(), (0.0, 0.0, 10.0, 10.0), ["road_segment"])
    assert result["version"] == "nuscenes-native-map-query-v1"
    assert result["layers"] == {"road_segment": ["road-a", "road-b"]}
    assert result["artifact_visibility"] == "local_private"


def test_lidar_contract_is_private_and_prediction_is_advisory() -> None:
    contract = lidar_payload_contract({"timestamp": 10, "filename": "samples/LIDAR_TOP/a.pcd"}, {"token": "cal-1"})
    assert contract.artifact_visibility == "local_private"
    result = evaluate_prediction_advisory([((0.0, 0.0), (2.0, 0.0))], ((0.0, 0.0), (3.0, 0.0)))
    assert result["metric_role"] == "advisory_prediction_only"
    assert result["min_fde_m"] == 1.0
