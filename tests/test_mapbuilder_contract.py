import pytest

from real2scenario.mapbuilder import (
    MAP_BUILDER_VERSION,
    build_map_manifest,
    stable_road_id,
    validate_opendrive_subset,
    fit_line_arc_geometry,
    analyze_connectivity_continuity,
    build_scene_local_corridor,
    repair_centerline_paths,
    validate_lane_topology,
)
import math
from xml.etree import ElementTree as ET
import real2scenario.mapbuilder as mapbuilder
from real2scenario import Actor, Scenario, State


def _corridor_scenario() -> Scenario:
    return Scenario(
        "corridor",
        1.0,
        "ego",
        (Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 10.0, 0.0, 0.0, 1.0))),),
        "nuscenes_global",
        {"source_scene_token": "scene-token"},
    )


def test_stable_ids_are_order_independent() -> None:
    assert stable_road_id("lane-token") == stable_road_id("lane-token")
    assert stable_road_id("lane-token").startswith("r-")


def test_map_manifest_contains_private_artifact_boundary() -> None:
    manifest = build_map_manifest(
        source_map_token="map-token",
        location="singapore-onenorth",
        xodr_sha256="abc",
        git_revision="deadbeef",
    )
    assert manifest["map_builder_version"] == MAP_BUILDER_VERSION
    assert manifest["artifact_visibility"] == "local_private"


def test_structural_validator_rejects_missing_root() -> None:
    with pytest.raises(ValueError, match="OpenDRIVE"):
        validate_opendrive_subset("<root/>")


def test_line_arc_fitter_keeps_straight_path_as_one_line() -> None:
    poses = [(float(index), 0.0, 0.0) for index in range(5)]

    segments = fit_line_arc_geometry(poses)

    assert len(segments) == 1
    assert segments[0].kind == "line"
    assert segments[0].max_residual_m == pytest.approx(0.0)


def test_line_arc_fitter_recovers_known_circular_arc() -> None:
    poses = []
    radius = 10.0
    for index in range(5):
        angle = index * (math.pi / 8)
        poses.append((radius * math.sin(angle), radius * (1 - math.cos(angle)), angle))

    segments = fit_line_arc_geometry(poses, tolerance_m=1e-6)

    assert len(segments) == 1
    assert segments[0].kind == "arc"
    assert segments[0].curvature == pytest.approx(0.1, rel=1e-3)
    assert segments[0].max_residual_m == pytest.approx(0.0, abs=1e-6)


def test_line_arc_fitter_rejects_invalid_geometry_configuration() -> None:
    with pytest.raises(ValueError, match="tolerance_m"):
        fit_line_arc_geometry([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], tolerance_m=0.0)


def test_centerline_repair_removes_duplicate_samples_with_provenance() -> None:
    paths, report = repair_centerline_paths({
        "source": [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
    })

    assert len(paths["source"]) == 2
    assert report["records_inspected"] == 1
    assert report["records_repaired"] == 1
    assert report["repaired_source_ids"] == ["source"]
    assert report["records_excluded"] == 0


def test_centerline_repair_excludes_collapsed_path_explicitly() -> None:
    paths, report = repair_centerline_paths({
        "collapsed": [(1.0, 1.0, 0.0), (1.0, 1.0, 0.0)],
    })

    assert paths == {}
    assert report["records_excluded"] == 1
    assert report["excluded"][0]["source_id"] == "collapsed"
    assert report["excluded"][0]["reason"] == "collapsed_centerline_after_duplicate_filter"


def test_lane_topology_validation_reports_reciprocal_and_endpoint_defects() -> None:
    report = validate_lane_topology(
        {
            "a": {"incoming": [], "outgoing": ["b"]},
            "b": {"incoming": [], "outgoing": []},
        },
        {
            "a": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
            "b": [(100.0, 0.0, math.pi), (101.0, 0.0, math.pi)],
        },
    )

    assert report["failure_count"] == 1
    assert report["failures"][0]["classification"] == "missing_source_link"
    assert "endpoint_gap" in report["failures"][0]["reasons"]


class _FakeMap:
    lane = [{"token": "lane-1"}]
    lane_connector = []
    connectivity = {}

    def discretize_lanes(self, tokens, resolution_m):
        radius = 10.0
        return {"lane-1": [
            (radius * math.sin(index * math.pi / 8), radius * (1 - math.cos(index * math.pi / 8)), index * math.pi / 8)
            for index in range(5)
        ]}

    def get_incoming_lane_ids(self, token):
        return []

    def get_outgoing_lane_ids(self, token):
        return []


class _ContinuityMap(_FakeMap):
    lane = [{"token": "incoming"}, {"token": "outgoing"}]
    connectivity = {
        "incoming": {"incoming": [], "outgoing": ["outgoing"]},
        "outgoing": {"incoming": ["incoming"], "outgoing": []},
    }

    def discretize_lanes(self, tokens, resolution_m):
        return {
            "incoming": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
            "outgoing": [(10.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
        }


class _TopologyMap(_ContinuityMap):
    lane = [{"token": "incoming"}, {"token": "outgoing"}]
    lane_connector = [{"token": "connector", "polygon_token": "poly-1"}]
    connectivity = {
        "incoming": {"incoming": [], "outgoing": ["connector"]},
        "connector": {"incoming": ["incoming"], "outgoing": ["outgoing"]},
        "outgoing": {"incoming": ["connector"], "outgoing": []},
    }

    def discretize_lanes(self, tokens, resolution_m):
        return {
            "incoming": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
            "connector": [(10.0, 0.0, 0.0), (15.0, 0.0, 0.0)],
            "outgoing": [(15.0, 0.0, 0.0), (25.0, 0.0, 0.0)],
        }

    def extract_polygon(self, token):
        class Polygon:
            area = 10.0
        return Polygon()


def test_builder_line_arc_mode_emits_arc_and_residual_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: _FakeMap())
    output = tmp_path / "line-arc.xodr"

    manifest = mapbuilder.build_opendrive_from_nuscenes(
        tmp_path, output_path=output, geometry_mode="line_arc", arc_tolerance_m=1e-6
    )

    root = ET.fromstring(output.read_text(encoding="utf-8"))
    assert root.find("./road/planView/geometry/arc") is not None
    assert root.find("./road/planView/geometry/line") is None
    assert manifest["geometry_mode"] == "line_arc"
    assert manifest["residual_statistics"]["arc_segment_count"] == 1
    assert manifest["residual_statistics"]["max_residual_m"] == pytest.approx(0.0, abs=1e-6)


def test_builder_default_mode_remains_line_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: _FakeMap())
    output = tmp_path / "line.xodr"

    manifest = mapbuilder.build_opendrive_from_nuscenes(tmp_path, output_path=output)

    root = ET.fromstring(output.read_text(encoding="utf-8"))
    assert root.find("./road/planView/geometry/line") is not None
    assert root.find("./road/planView/geometry/arc") is None
    assert manifest["geometry_mode"] == "line"
    assert manifest["residual_statistics"] is None


def test_builder_rejects_unknown_geometry_mode_before_loading_map(tmp_path) -> None:
    with pytest.raises(ValueError, match="geometry_mode"):
        mapbuilder.build_opendrive_from_nuscenes(tmp_path, output_path=tmp_path / "map.xodr", geometry_mode="bad")


def test_connectivity_continuity_reports_clean_join(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: _ContinuityMap())

    report = analyze_connectivity_continuity(tmp_path)

    assert report["edge_count"] == 1
    assert report["edge_status_counts"] == {"pass": 1, "fail": 0, "unsupported": 0}
    assert report["position_gap_m"]["max"] == pytest.approx(0.0)
    assert report["heading_gap_rad"]["max"] == pytest.approx(0.0)
    assert report["failures"] == []


def test_connectivity_continuity_reports_position_heading_and_asymmetry(tmp_path, monkeypatch) -> None:
    class BrokenMap(_ContinuityMap):
        connectivity = {
            "incoming": {"incoming": [], "outgoing": ["outgoing"]},
            "outgoing": {"incoming": [], "outgoing": []},
        }

        def discretize_lanes(self, tokens, resolution_m):
            return {
                "incoming": [(0.0, 0.0, 0.0), (10.0, 0.0, math.pi / 2)],
                "outgoing": [(11.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
            }

    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: BrokenMap())

    report = analyze_connectivity_continuity(tmp_path, position_tolerance_m=0.5, heading_tolerance_rad=0.2)

    assert report["edge_status_counts"] == {"pass": 0, "fail": 1, "unsupported": 0}
    assert report["asymmetric_connectivity_edges"] == 1
    assert set(report["failures"][0]["reason"].split(";")) == {
        "asymmetric_connectivity", "heading_gap_exceeds_tolerance", "position_gap_exceeds_tolerance"
    }


def test_builder_emits_connector_junction_and_polygon_width(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: _TopologyMap())
    output = tmp_path / "topology.xodr"

    manifest = mapbuilder.build_opendrive_from_nuscenes(tmp_path, output_path=output)
    root = ET.fromstring(output.read_text(encoding="utf-8"))

    junction = root.find("junction")
    assert junction is not None
    assert len(junction.findall("connection")) == 1
    widths = root.findall(".//road[@name='connector']//width")
    assert float(widths[0].attrib["a"]) == pytest.approx(2.0)
    assert manifest["lane_width_source_counts"]["polygon"] == 1
    assert manifest["junction_count"] == 1
    road_ids = {road.attrib["id"] for road in root.findall("road")}
    junction_ids = {junction.attrib["id"] for junction in root.findall("junction")}
    assert all(road.attrib["junction"] == "-1" or road.attrib["junction"] in junction_ids for road in root.findall("road"))
    assert all(link.attrib["elementId"] in road_ids for link in root.findall(".//predecessor") + root.findall(".//successor"))


def test_builder_omits_links_to_unemitted_map_tokens(tmp_path, monkeypatch) -> None:
    class MissingLinkMap(_FakeMap):
        def get_outgoing_lane_ids(self, token):
            return ["missing-token"]

    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: MissingLinkMap())
    output = tmp_path / "missing-link.xodr"
    mapbuilder.build_opendrive_from_nuscenes(tmp_path, output_path=output)
    root = ET.fromstring(output.read_text(encoding="utf-8"))
    assert root.find(".//successor") is None


def test_builder_links_are_order_independent_for_selected_records(tmp_path, monkeypatch) -> None:
    class OrderedTopologyMap(_TopologyMap):
        lane = [{"token": "incoming"}, {"token": "outgoing"}]
        lane_connector = [{"token": "connector", "polygon_token": "poly-1"}]

        def get_outgoing_lane_ids(self, token):
            return {"incoming": ["connector"], "connector": ["outgoing"], "outgoing": []}[token]

        def get_incoming_lane_ids(self, token):
            return {"incoming": [], "connector": ["incoming"], "outgoing": ["connector"]}[token]

    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: OrderedTopologyMap())
    output = tmp_path / "ordered.xodr"
    mapbuilder.build_opendrive_from_nuscenes(tmp_path, output_path=output)
    root = ET.fromstring(output.read_text(encoding="utf-8"))
    road_by_name = {road.attrib["name"]: road for road in root.findall("road")}
    assert road_by_name["incoming"].find("./link/successor").attrib["elementId"] == mapbuilder.stable_road_id("connector")
    assert road_by_name["connector"].find("./link/successor").attrib["elementId"] == mapbuilder.stable_road_id("outgoing")


def test_scene_corridor_selects_trajectory_and_one_hop_closure(tmp_path, monkeypatch) -> None:
    class CorridorMap(_TopologyMap):
        def discretize_lanes(self, tokens, resolution_m):
            return {
                "incoming": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
                "connector": [(10.0, 0.0, 0.0), (15.0, 0.0, 0.0)],
                "outgoing": [(15.0, 0.0, 0.0), (25.0, 0.0, 0.0)],
            }

    monkeypatch.setattr(mapbuilder, "_load_nuscenes_map", lambda root, name: CorridorMap())
    scenario = _corridor_scenario()

    manifest = build_scene_local_corridor(tmp_path, scenario, output_path=tmp_path / "corridor.xodr", buffer_m=40.0)

    assert manifest["manifest_version"] == "cp1-scene-corridor-v1"
    assert manifest["buffer_m"] == 40.0
    assert manifest["topology_closure"] == "one_hop_incident_connectivity"
    assert set(manifest["selected_tokens"]) == {"incoming", "connector", "outgoing"}


def test_scene_corridor_rejects_out_of_contract_buffer_and_frame(tmp_path, monkeypatch) -> None:
    with pytest.raises(ValueError, match="between 30 and 50"):
        build_scene_local_corridor(tmp_path, _corridor_scenario(), output_path=tmp_path / "x.xodr", buffer_m=10.0)
