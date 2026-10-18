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
