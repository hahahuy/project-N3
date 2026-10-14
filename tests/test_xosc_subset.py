from pathlib import Path

import pytest

from real2scenario.xosc_subset import (
    XOSC_SUBSET_VERSION,
    build_execution_identity,
    parse_xosc_subset,
)


def _xosc() -> str:
    return """<OpenSCENARIO><FileHeader revMajor='1' revMinor='1'/><RoadNetwork><LogicFile filepath='map.xodr'/></RoadNetwork><Entities><ScenarioObject name='ego'><Vehicle vehicleCategory='car'><BoundingBox><Center x='1' y='0' z='0'/><Dimensions width='2' length='4' height='1.5'/></BoundingBox></Vehicle></ScenarioObject></Entities><Storyboard><Init><Actions><Private entityRef='ego'><PrivateAction><TeleportAction><Position><WorldPosition x='0' y='0' z='0' h='0' p='0' r='0'/></Position></TeleportAction></PrivateAction></Private></Actions></Init></Storyboard></OpenSCENARIO>"""


def test_parser_returns_validated_plan_and_identity(tmp_path: Path) -> None:
    xosc = tmp_path / "scenario.xosc"
    xodr = tmp_path / "map.xodr"
    xosc.write_text(_xosc(), encoding="utf-8")
    xodr.write_text("<OpenDRIVE/>\n", encoding="utf-8")

    plan = parse_xosc_subset(xosc, xodr)
    identity = build_execution_identity(xosc, xodr)

    assert plan.subset_version == XOSC_SUBSET_VERSION
    assert plan.entity_names == ("ego",)
    assert identity.xosc_sha256
    assert identity.xodr_sha256
    assert plan.initial_positions["ego"] == (0.0, 0.0, 0.0, 0.0)


def test_trace_state_requires_finite_normalized_values() -> None:
    from real2scenario.carla_trace import CarlaTraceState

    state = CarlaTraceState("run", "carla", "0.9.16", "waypoint", 0.0, 0, "ego", 0, 0, 0, 0, 0, 0, 0)
    assert state.coordinate_frame == "carla_world"


def test_parser_fails_closed_for_unsupported_feature(tmp_path: Path) -> None:
    xosc = tmp_path / "scenario.xosc"
    xosc.write_text(_xosc().replace("<Entities>", "<Environment><Weather/></Environment><Entities>"), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported_xosc_feature"):
        parse_xosc_subset(xosc, None)


def _write_xosc(tmp_path: Path, *, mutate=None) -> Path:
    from real2scenario import Actor, Scenario, State, artifact_to_json, baseline_artifact_to_dict, write_openscenario, select_opendrive_template, STRAIGHT_ROAD_TOPOLOGY

    scenario = Scenario(
        "interpret-me",
        2.0,
        "ego",
        (
            Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 5.0), State(1.0, 5.0, 0.0, 0.0, 5.0), State(2.0, 10.0, 0.0, 0.0, 5.0)), 4.0, 2.0),
            Actor("lead", "vehicle", (State(0.0, 0.0, 20.0, 0.0, 5.0), State(1.0, 5.0, 20.0, 0.0, 5.0), State(2.0, 10.0, 20.0, 0.0, 5.0)), 4.0, 2.0),
        ),
        "local_road_aligned",
    )
    del artifact_to_json, baseline_artifact_to_dict
    selected, template = select_opendrive_template(scenario, topology=STRAIGHT_ROAD_TOPOLOGY)
    path = tmp_path / "scenario.xosc"
    write_openscenario(selected, template, path)
    if mutate is not None:
        text = path.read_text(encoding="utf-8")
        path.write_text(mutate(text), encoding="utf-8")
    return path


def test_interpreter_resolves_init_act_triggers_and_identity(tmp_path: Path) -> None:
    from real2scenario import XOSC_INTERPRETER_VERSION, interpret_xosc_subset

    path = _write_xosc(tmp_path)

    interpretation = interpret_xosc_subset(path, None)
    payload = interpretation.interpretation_to_dict

    assert payload["interpreter_version"] == XOSC_INTERPRETER_VERSION
    assert payload["act_name"] == "recorded_trajectories"
    assert {entity["name"] for entity in payload["entities"]} == {"ego", "lead"}
    for entity in payload["entities"]:
        assert entity["state_count"] == 3
        assert entity["duration_s"] == 2.0
        assert entity["starts_at_zero"] is True
        assert entity["start_time_s"] == 0.0
        assert entity["time_reference"]["domain"] == "relative"
        assert entity["start_conditions"][0]["rule"] == "greaterThan"
    assert interpretation.by_name("lead").trajectory[0][1:3] == (0.0, 20.0)
    assert len(payload["execution_identity"]["xosc_sha256"]) == 64


def test_interpreter_requires_stop_triggers(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    path = _write_xosc(
        tmp_path,
        mutate=lambda text: text.replace("<StopTrigger>", "<StopTriggerX>").replace(
            "</StopTrigger>", "</StopTriggerX>"
        ),
    )

    with pytest.raises(ValueError, match="story has no StopTrigger"):
        interpret_xosc_subset(path, None)


def test_interpreter_rejects_unsupported_trigger_conditions(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    path = _write_xosc(
        tmp_path,
        mutate=lambda text: text.replace(
            "<SimulationTimeCondition", "<ReachPositionCondition", 1
        ).replace("</SimulationTimeCondition>", "</ReachPositionCondition>"),
    )

    with pytest.raises(ValueError, match="ReachPositionCondition"):
        interpret_xosc_subset(path, None)


def test_interpreter_rejects_entity_without_maneuver_group(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    path = _write_xosc(
        tmp_path,
        mutate=lambda text: text.replace('entityRef="lead"', 'entityRef="ghost"'),
    )

    with pytest.raises(ValueError, match="must match"):
        interpret_xosc_subset(path, None)


def test_interpreter_rejects_non_monotonic_trajectory_times(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    path = _write_xosc(
        tmp_path,
        mutate=lambda text: text.replace('time="1"', 'time="-1"', 1),
    )

    with pytest.raises(ValueError, match="strictly increase"):
        interpret_xosc_subset(path, None)


def test_interpreter_rejects_missing_time_reference(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    def strip_reference(text: str) -> str:
        start = text.index("<TimeReference>")
        end = text.index("</TimeReference>") + len("</TimeReference>")
        return text[:start] + text[end:]

    path = _write_xosc(tmp_path, mutate=strip_reference)

    with pytest.raises(ValueError, match="requires a TimeReference"):
        interpret_xosc_subset(path, None)


def test_interpreter_requires_the_map_asset_when_one_is_declared(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    path = _write_xosc(tmp_path)

    with pytest.raises(ValueError, match="map_asset_missing"):
        interpret_xosc_subset(path, tmp_path / "absent.xodr")


def test_interpreter_accepts_a_timing_shifted_trajectory(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    path = _write_xosc(
        tmp_path,
        mutate=lambda text: text.replace('time="0"', 'time="0.5"', 1).replace(
            'time="1"', 'time="1.5"', 1
        ),
    )

    interpretation = interpret_xosc_subset(path, None)
    ego = interpretation.by_name("ego")

    assert ego.starts_at_zero is False
    assert ego.trajectory[0][0] == 0.5
    assert ego.duration_s == 2.0
    assert [vertex[0] for vertex in ego.trajectory] == [0.5, 1.5, 2.0]


def test_interpreter_rejects_multiple_acts(tmp_path: Path) -> None:
    from real2scenario import interpret_xosc_subset

    path = _write_xosc(tmp_path, mutate=lambda text: text.replace("</Story>", '<Act name="second"></Act></Story>'))

    with pytest.raises(ValueError, match="multiple Acts"):
        interpret_xosc_subset(path, None)
