from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from real2scenario.native_sources import (
    LIDAR_CONTRACT_VERSION,
    MAP_LAYERS,
    NATIVE_MAP_VERSION,
    PREDICTION_EVAL_VERSION,
    LidarPayloadContract,
    evaluate_prediction_advisory,
    lidar_payload_contract,
    native_map_patch,
    native_map_records,
    road_ahead_query,
)


class FakeMapApi:
    def __init__(self, **layers: object) -> None:
        for name, records in layers.items():
            setattr(self, name, records)


class QueryMapApi:
    def __init__(self, next_roads: object = None, patch_records: object = None) -> None:
        self.next_roads = next_roads
        self.patch_records = patch_records
        self.calls: list[tuple[object, ...]] = []

    def get_next_roads(self, x_m: float, y_m: float) -> object:
        self.calls.append(("next", x_m, y_m))
        return self.next_roads

    def get_records_in_patch(self, patch: list[float], layers: list[str]) -> object:
        self.calls.append(("patch", patch, layers))
        return self.patch_records


def _sample_data() -> dict[str, object]:
    return {"timestamp": 1_532_402_927_647_951, "filename": "samples/LIDAR_TOP/a.pcd.bin"}


def _calibration() -> dict[str, object]:
    return {"token": "calib-top"}


def test_map_records_reject_an_unsupported_layer() -> None:
    with pytest.raises(ValueError, match="Unsupported native map layer: lane"):
        native_map_records(FakeMapApi(lane=[]), "lane")


def test_map_records_reject_a_missing_layer_attribute() -> None:
    with pytest.raises(ValueError, match="unavailable: stop_line"):
        native_map_records(FakeMapApi(), "stop_line")


def test_map_records_reject_a_layer_that_is_not_a_list() -> None:
    with pytest.raises(ValueError, match="unavailable: walkway"):
        native_map_records(FakeMapApi(walkway=({"token": "w"},)), "walkway")


def test_map_records_are_sorted_by_token() -> None:
    api = FakeMapApi(road_segment=[{"token": "c"}, {"token": "a"}, {"token": "b"}])

    records = native_map_records(api, "road_segment")

    assert [record["token"] for record in records] == ["a", "b", "c"]


def test_map_records_are_copies_of_the_api_records() -> None:
    original = {"token": "a", "polygon_token": "p"}
    api = FakeMapApi(drivable_area=[original])

    records = native_map_records(api, "drivable_area")
    records[0]["token"] = "mutated"

    assert original["token"] == "a"
    assert records[0] is not original


def test_map_records_never_reorder_the_api_list() -> None:
    layer = [{"token": "b"}, {"token": "a"}]
    api = FakeMapApi(traffic_light=layer)

    native_map_records(api, "traffic_light")

    assert [record["token"] for record in layer] == ["b", "a"]


def test_map_records_sort_missing_tokens_first() -> None:
    api = FakeMapApi(ped_crossing=[{"token": "a"}, {"name": "untokened"}])

    records = native_map_records(api, "ped_crossing")

    assert records[0] == {"name": "untokened"}


def test_map_records_return_empty_for_an_empty_layer() -> None:
    assert native_map_records(FakeMapApi(lane_divider=[]), "lane_divider") == ()


def test_map_records_accept_every_supported_layer() -> None:
    api = FakeMapApi(**{layer: [{"token": layer}] for layer in MAP_LAYERS})

    for layer in MAP_LAYERS:
        assert native_map_records(api, layer) == ({"token": layer},)


def test_road_ahead_reports_unavailable_without_the_devkit_query() -> None:
    result = road_ahead_query(FakeMapApi(), 1.0, 2.0)

    assert result == {
        "version": NATIVE_MAP_VERSION,
        "status": "unavailable",
        "reason": "devkit_query_missing",
        "records": [],
    }


def test_road_ahead_passes_the_query_position_to_the_devkit() -> None:
    api = QueryMapApi(next_roads=[])

    road_ahead_query(api, 12.5, -3.25)

    assert api.calls == [("next", 12.5, -3.25)]


def test_road_ahead_returns_devkit_records_as_available() -> None:
    result = road_ahead_query(QueryMapApi(next_roads=["road-1", "road-2"]), 0.0, 0.0)

    assert result["status"] == "available"
    assert result["records"] == ["road-1", "road-2"]


def test_road_ahead_treats_a_none_devkit_result_as_no_records() -> None:
    result = road_ahead_query(QueryMapApi(next_roads=None), 0.0, 0.0)

    assert result["status"] == "available"
    assert result["records"] == []


def test_road_ahead_marks_available_results_local_private() -> None:
    result = road_ahead_query(QueryMapApi(next_roads=[]), 0.0, 0.0)

    assert result["artifact_visibility"] == "local_private"
    assert result["version"] == NATIVE_MAP_VERSION


def test_road_ahead_copies_the_devkit_records_into_a_new_list() -> None:
    devkit_records = ["road-1"]

    result = road_ahead_query(QueryMapApi(next_roads=devkit_records), 0.0, 0.0)

    assert result["records"] is not devkit_records


def test_map_patch_rejects_a_patch_without_four_values() -> None:
    with pytest.raises(ValueError, match="positive area"):
        native_map_patch(QueryMapApi(), (0.0, 0.0, 1.0))  # type: ignore[arg-type]


def test_map_patch_rejects_inverted_x_bounds() -> None:
    with pytest.raises(ValueError, match="positive area"):
        native_map_patch(QueryMapApi(), (5.0, 0.0, 1.0, 1.0))


def test_map_patch_rejects_inverted_y_bounds() -> None:
    with pytest.raises(ValueError, match="positive area"):
        native_map_patch(QueryMapApi(), (0.0, 5.0, 1.0, 1.0))


def test_map_patch_rejects_a_zero_width_patch() -> None:
    with pytest.raises(ValueError, match="positive area"):
        native_map_patch(QueryMapApi(), (1.0, 0.0, 1.0, 1.0))


def test_map_patch_rejects_a_zero_height_patch() -> None:
    with pytest.raises(ValueError, match="positive area"):
        native_map_patch(QueryMapApi(), (0.0, 1.0, 1.0, 1.0))


def test_map_patch_rejects_an_unsupported_layer() -> None:
    with pytest.raises(ValueError, match="Unsupported native map layer: lane"):
        native_map_patch(QueryMapApi(), (0.0, 0.0, 1.0, 1.0), layers=("walkway", "lane"))


def test_map_patch_names_the_first_unsupported_layer_alphabetically() -> None:
    with pytest.raises(ValueError, match="Unsupported native map layer: alpha"):
        native_map_patch(QueryMapApi(), (0.0, 0.0, 1.0, 1.0), layers=("zeta", "alpha"))


def test_map_patch_validates_layers_before_checking_the_devkit_query() -> None:
    with pytest.raises(ValueError, match="Unsupported native map layer"):
        native_map_patch(FakeMapApi(), (0.0, 0.0, 1.0, 1.0), layers=("lane",))


def test_map_patch_reports_unavailable_without_the_devkit_query() -> None:
    result = native_map_patch(FakeMapApi(), (0.0, 0.0, 1.0, 1.0))

    assert result == {
        "version": NATIVE_MAP_VERSION,
        "status": "unavailable",
        "reason": "devkit_query_missing",
        "patch": [0.0, 0.0, 1.0, 1.0],
        "layers": {},
    }


def test_map_patch_queries_every_layer_by_default() -> None:
    api = QueryMapApi(patch_records={})

    result = native_map_patch(api, (0.0, 0.0, 1.0, 1.0))

    assert api.calls == [("patch", [0.0, 0.0, 1.0, 1.0], list(MAP_LAYERS))]
    assert list(result["layers"]) == list(MAP_LAYERS)


def test_map_patch_passes_only_the_requested_layers_to_the_devkit() -> None:
    api = QueryMapApi(patch_records={})

    native_map_patch(api, (0.0, 0.0, 1.0, 1.0), layers=("stop_line",))

    assert api.calls == [("patch", [0.0, 0.0, 1.0, 1.0], ["stop_line"])]


def test_map_patch_sorts_record_tokens_per_layer() -> None:
    api = QueryMapApi(patch_records={"walkway": ["w3", "w1", "w2"]})

    result = native_map_patch(api, (0.0, 0.0, 1.0, 1.0), layers=("walkway",))

    assert result["layers"] == {"walkway": ["w1", "w2", "w3"]}


def test_map_patch_fills_layers_missing_from_the_devkit_result_with_empty_lists() -> None:
    api = QueryMapApi(patch_records={"walkway": ["w1"]})

    result = native_map_patch(api, (0.0, 0.0, 1.0, 1.0), layers=("walkway", "stop_line"))

    assert result["layers"] == {"walkway": ["w1"], "stop_line": []}


def test_map_patch_treats_a_none_devkit_result_as_empty_layers() -> None:
    result = native_map_patch(QueryMapApi(patch_records=None), (0.0, 0.0, 1.0, 1.0), layers=("walkway",))

    assert result["layers"] == {"walkway": []}


def test_map_patch_drops_devkit_layers_that_were_not_requested() -> None:
    api = QueryMapApi(patch_records={"walkway": ["w1"], "stop_line": ["s1"]})

    result = native_map_patch(api, (0.0, 0.0, 1.0, 1.0), layers=("walkway",))

    assert list(result["layers"]) == ["walkway"]


def test_map_patch_marks_available_results_local_private_with_the_patch() -> None:
    result = native_map_patch(QueryMapApi(patch_records={}), (-1.0, -2.0, 3.0, 4.0), layers=())

    assert result["status"] == "available"
    assert result["patch"] == [-1.0, -2.0, 3.0, 4.0]
    assert result["artifact_visibility"] == "local_private"


def test_lidar_contract_describes_the_sample_without_point_bytes() -> None:
    contract = lidar_payload_contract(_sample_data(), _calibration())

    assert contract == LidarPayloadContract(
        LIDAR_CONTRACT_VERSION,
        "LIDAR_TOP",
        1_532_402_927_647_951,
        "samples/LIDAR_TOP/a.pcd.bin",
        "ego_vehicle",
        "calib-top",
        8,
    )


def test_lidar_contract_defaults_to_local_private_visibility() -> None:
    assert lidar_payload_contract(_sample_data(), _calibration()).artifact_visibility == "local_private"


def test_lidar_contract_uses_the_requested_decimation() -> None:
    assert lidar_payload_contract(_sample_data(), _calibration(), decimation=1).decimation == 1


def test_lidar_contract_rejects_zero_decimation() -> None:
    with pytest.raises(ValueError, match="Invalid private LiDAR payload contract"):
        lidar_payload_contract(_sample_data(), _calibration(), decimation=0)


def test_lidar_contract_coerces_string_timestamps_and_tokens() -> None:
    contract = lidar_payload_contract(
        {"timestamp": "42", "filename": "a.bin"}, {"token": 7}
    )

    assert contract.timestamp_us == 42
    assert contract.calibration_token == "7"


def test_lidar_contract_requires_a_sample_timestamp() -> None:
    with pytest.raises(KeyError, match="timestamp"):
        lidar_payload_contract({"filename": "a.bin"}, _calibration())


def test_lidar_contract_requires_a_calibration_token() -> None:
    with pytest.raises(KeyError, match="token"):
        lidar_payload_contract(_sample_data(), {})


def test_lidar_contract_rejects_an_unknown_version() -> None:
    with pytest.raises(ValueError, match="Invalid private LiDAR payload contract"):
        LidarPayloadContract("lidar-v0", "LIDAR_TOP", 1, "a.bin", "ego_vehicle", "c", 8)


def test_lidar_contract_rejects_a_non_top_channel() -> None:
    with pytest.raises(ValueError, match="Invalid private LiDAR payload contract"):
        LidarPayloadContract(LIDAR_CONTRACT_VERSION, "RADAR_FRONT", 1, "a.bin", "ego_vehicle", "c", 8)


def test_lidar_contract_rejects_public_visibility() -> None:
    with pytest.raises(ValueError, match="must remain local_private"):
        LidarPayloadContract(
            LIDAR_CONTRACT_VERSION, "LIDAR_TOP", 1, "a.bin", "ego_vehicle", "c", 8, "public"
        )


def test_lidar_contract_is_immutable() -> None:
    contract = lidar_payload_contract(_sample_data(), _calibration())

    with pytest.raises(FrozenInstanceError):
        contract.decimation = 2  # type: ignore[misc]


def test_prediction_advisory_rejects_no_predicted_paths() -> None:
    with pytest.raises(ValueError, match="non-empty and equal"):
        evaluate_prediction_advisory([], [(0.0, 0.0)])


def test_prediction_advisory_rejects_an_empty_reference() -> None:
    with pytest.raises(ValueError, match="non-empty and equal"):
        evaluate_prediction_advisory([[]], [])


def test_prediction_advisory_rejects_a_path_with_a_different_horizon() -> None:
    with pytest.raises(ValueError, match="non-empty and equal"):
        evaluate_prediction_advisory([[(0.0, 0.0)], [(0.0, 0.0), (1.0, 0.0)]], [(0.0, 0.0)])


def test_prediction_advisory_reports_zero_error_for_a_perfect_prediction() -> None:
    actual = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]

    result = evaluate_prediction_advisory([list(actual)], actual)

    assert result["min_ade_m"] == 0.0
    assert result["min_fde_m"] == 0.0


def test_prediction_advisory_averages_euclidean_displacement() -> None:
    result = evaluate_prediction_advisory([[(3.0, 4.0), (0.0, 0.0)]], [(0.0, 0.0), (0.0, 0.0)])

    assert result["min_ade_m"] == pytest.approx(2.5)


def test_prediction_advisory_measures_final_displacement_on_the_last_step() -> None:
    result = evaluate_prediction_advisory([[(9.0, 9.0), (6.0, 8.0)]], [(0.0, 0.0), (0.0, 0.0)])

    assert result["min_fde_m"] == pytest.approx(10.0)


def test_prediction_advisory_takes_ade_and_fde_minima_independently() -> None:
    actual = [(0.0, 0.0), (0.0, 0.0)]
    close_start = [(0.0, 0.0), (2.0, 0.0)]
    close_end = [(3.0, 0.0), (1.0, 0.0)]

    result = evaluate_prediction_advisory([close_start, close_end], actual)

    assert result["min_ade_m"] == pytest.approx(1.0)
    assert result["min_fde_m"] == pytest.approx(1.0)


def test_prediction_advisory_is_labelled_provisional_and_advisory_only() -> None:
    result = evaluate_prediction_advisory([[(0.0, 0.0)]], [(0.0, 0.0)])

    assert result["evaluation_version"] == PREDICTION_EVAL_VERSION
    assert result["metric_role"] == "advisory_prediction_only"
    assert result["scientific_status"] == "PROVISIONAL"
