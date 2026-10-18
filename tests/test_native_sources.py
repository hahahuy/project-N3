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
