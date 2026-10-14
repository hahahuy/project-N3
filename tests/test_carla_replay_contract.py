from dataclasses import replace
from pathlib import Path

import pytest

from real2scenario import (
    AlignmentCorrespondence,
    BlueprintRule,
    map_blueprints,
    BlueprintMapping,
    CarlaAlignmentArtifact,
    ExactPoseBatch,
    ReplayGrid,
    build_exact_pose_batches,
    build_exact_pose_plan,
    build_replay_grid,
    interpolate_trajectory,
    require_execution_identity,
    execute_exact_pose,
)
from real2scenario.xosc_subset import parse_xosc_subset


def _xosc() -> str:
    return """<OpenSCENARIO><RoadNetwork><LogicFile filepath='map.xodr'/></RoadNetwork><Entities><ScenarioObject name='ego'/></Entities><Storyboard><Init><Actions><Private entityRef='ego'><PrivateAction><TeleportAction><Position><WorldPosition x='0' y='0' z='0' h='0'/></Position></TeleportAction></PrivateAction></Private></Actions></Init><Story><Act><ManeuverGroup><Actors><EntityRef entityRef='ego'/></Actors><Maneuver><Event><Action><PrivateAction><RoutingAction><FollowTrajectoryAction><Trajectory><Shape><Polyline><Vertex time='0' lon='0' lat='0' sync="true"><Position><WorldPosition x='0' y='0' z='0' h='3.1'/></Position></Vertex><Vertex time='1' lon='0' lat='0' sync="true"><Position><WorldPosition x='10' y='0' z='0' h='-3.1'/></Position></Vertex></Polyline></Shape></Trajectory></FollowTrajectoryAction></RoutingAction></PrivateAction></Action></Event></Maneuver></ManeuverGroup></Act></Story></Storyboard></OpenSCENARIO>"""


def _full_subset_xosc() -> str:
    """A minimal in-subset XOSC with Init, Story/Act, triggers and time reference."""
    def group(name: str, y: float) -> str:
        return (
            f"<ManeuverGroup name='{name}_trajectory' maximumExecutionCount='1'>"
            f"<Actors selectTriggeringEntities='false'><EntityRef entityRef='{name}'/></Actors>"
            f"<Maneuver name='{name}_follow'><Event name='{name}_start' priority='overwrite'>"
            f"<Action name='{name}_follow_trajectory'><PrivateAction><RoutingAction><FollowTrajectoryAction>"
            f"<Trajectory name='{name}_recorded' closed='false'><Shape><Polyline>"
            f"<Vertex time='0'><Position><WorldPosition x='0' y='{y}' z='0' h='3.1'/></Position></Vertex>"
            f"<Vertex time='1'><Position><WorldPosition x='10' y='{y}' z='0' h='3.1'/></Position></Vertex>"
            f"</Polyline></Shape></Trajectory><TimeReference><Timing domainAbsoluteRelative='relative' scale='1' offset='0'/></TimeReference>"
            f"</FollowTrajectoryAction></RoutingAction></PrivateAction></Action>"
            f"<StartTrigger><ConditionGroup><Condition name='simulation_time' delay='0' conditionEdge='none'>"
            f"<ByValueCondition><SimulationTimeCondition value='0' rule='greaterThan'/></ByValueCondition>"
            f"</Condition></ConditionGroup></StartTrigger></Event></Maneuver></ManeuverGroup>"
        )

    return (
        "<OpenSCENARIO><RoadNetwork><LogicFile filepath='map.xodr'/></RoadNetwork>"
        "<Entities><ScenarioObject name='ego'/><ScenarioObject name='lead'/></Entities>"
        "<Storyboard><Init><Actions>"
        "<Private entityRef='ego'><PrivateAction><TeleportAction><Position><WorldPosition x='0' y='0' z='0' h='3.1'/>"
        "</Position></TeleportAction></PrivateAction></Private>"
        "<Private entityRef='lead'><PrivateAction><TeleportAction><Position><WorldPosition x='0' y='20' z='0' h='3.1'/>"
        "</Position></TeleportAction></PrivateAction></Private>"
        "</Actions></Init>"
        "<Story name='baseline_replay'><Act name='recorded_trajectories'>"
        + group("ego", 0.0)
        + group("lead", 20.0)
        + "<StartTrigger><ConditionGroup><Condition name='story_start' delay='0' conditionEdge='none'>"
        "<ByValueCondition><SimulationTimeCondition value='0' rule='greaterThan'/></ByValueCondition>"
        "</Condition></ConditionGroup></StartTrigger>"
        "</Act>"
        "<StopTrigger><ConditionGroup><Condition name='story_end' delay='0' conditionEdge='none'>"
        "<ByValueCondition><SimulationTimeCondition value='1' rule='greaterThan'/></ByValueCondition>"
        "</Condition></ConditionGroup></StopTrigger>"
        "</Story></Storyboard></OpenSCENARIO>"
    )


def _alignment() -> CarlaAlignmentArtifact:
    return CarlaAlignmentArtifact(
        source_dataset="nuScenes", source_dataset_version="v1.0-trainval", source_scene="scene-0061",
        source_coordinate_frame="local_road_aligned", canonical_coordinate_frame="carla_world",
        carla_world="Town04", carla_release="0.9.16", carla_server_version="0.9.16",
        translation_x_m=0, translation_y_m=0, translation_z_m=0, yaw_rad=0,
        max_position_residual_m=0.01, max_heading_residual_rad=0.01,
        position_tolerance_m=0.5, heading_tolerance_rad=0.2,
        actor_origin_convention="bounding_box_center", map_reconstruction_mode="built-in-world",
        fidelity_claim="built-in-world approximation; not lossless source-map conversion",
        correspondences=(AlignmentCorrespondence("a", 0, 0, 0, 0, 0, 0, 0.01, 0.01),),
    )


def test_replay_grid_includes_exact_endpoint() -> None:
    assert build_replay_grid(1.0, 0.3).times_s == (0.0, 0.3, 0.6, 0.9, 1.0)


def test_yaw_interpolation_uses_shortest_path() -> None:
    result = interpolate_trajectory(((0.0, 0, 0, 3.1, 1), (1.0, 10, 0, -3.1, 1)), 0.5)
    assert abs(abs(result[3]) - 3.14159) < 0.1


def test_alignment_rejects_residual_exceeding_tolerance() -> None:
    artifact = _alignment()
    bad = replace(artifact, max_position_residual_m=1.0)
    with pytest.raises(ValueError, match="alignment_residual_exceeded"):
        from real2scenario.carla_replay import validate_alignment

        validate_alignment(bad)


def test_exact_plan_rejects_missing_xodr(tmp_path: Path) -> None:
    xosc = tmp_path / "scenario.xosc"
    xosc.write_text(_xosc(), encoding="utf-8")
    parsed = parse_xosc_subset(xosc, None)
    mapping = (BlueprintMapping("ego", "car", "vehicle.tesla.model3", "bounding_box_center", None, None),)
    with pytest.raises(ValueError, match="map_asset_missing"):
        build_exact_pose_plan(xosc, tmp_path / "missing.xodr", parsed, _alignment(), mapping, timestep_s=0.05)


def test_alignment_serial_plan_rehashes_inputs(tmp_path: Path) -> None:
    xosc = tmp_path / "scenario.xosc"
    xodr = tmp_path / "map.xodr"
    xosc.write_text(_xosc(), encoding="utf-8")
    xodr.write_text("<OpenDRIVE/>", encoding="utf-8")
    parsed = parse_xosc_subset(xosc, xodr)
    mapping = (BlueprintMapping("ego", "car", "vehicle.tesla.model3", "bounding_box_center", None, None),)
    plan = build_exact_pose_plan(xosc, xodr, parsed, _alignment(), mapping, timestep_s=0.25)
    require_execution_identity(plan)
    xosc.write_text(xosc.read_text() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="xosc_hash_mismatch"):
        require_execution_identity(plan)


class _FakeRuntime:
    def __init__(self):
        self.calls = []

    def configure(self, timestep_s):
        self.calls.append(("configure", timestep_s))

    def spawn(self, mappings):
        self.calls.append(("spawn", tuple(mapping.entity_name for mapping in mappings)))

    def apply_batch_sync(self, batch):
        self.calls.append(("batch", batch))

    def tick(self):
        self.calls.append(("tick",))
        return len([call for call in self.calls if call[0] == "tick"])

    def cleanup(self):
        self.calls.append(("cleanup",))


def test_fake_exact_pose_runtime_batches_then_ticks_and_cleans_up(tmp_path: Path) -> None:
    xosc = tmp_path / "scenario.xosc"
    xodr = tmp_path / "map.xodr"
    xosc.write_text(_xosc(), encoding="utf-8")
    xodr.write_text("<OpenDRIVE/>", encoding="utf-8")
    parsed = parse_xosc_subset(xosc, xodr)
    mapping = (BlueprintMapping("ego", "car", "vehicle.tesla.model3", "bounding_box_center", None, None),)
    plan = build_exact_pose_plan(xosc, xodr, parsed, _alignment(), mapping, timestep_s=0.25)
    runtime = _FakeRuntime()

    frames = execute_exact_pose(runtime, plan, parsed)

    assert frames == (1, 2, 3, 4, 5)
    assert [call[0] for call in runtime.calls] == ["configure", "spawn", "batch", "tick", "batch", "tick", "batch", "tick", "batch", "tick", "batch", "tick", "cleanup"]
    batches = [call[1] for call in runtime.calls if call[0] == "batch"]
    assert all(batch.do_tick is False for batch in batches)
    assert all(command.physics_enabled is False for batch in batches for command in batch.commands)


def test_execution_interpretation_feeds_blueprint_mapping_and_batches(tmp_path: Path) -> None:
    from real2scenario import XOSC_INTERPRETER_VERSION, interpret_for_execution

    xosc = tmp_path / "scenario.xosc"
    xosc.write_text(_full_subset_xosc(), encoding="utf-8")
    xodr = tmp_path / "map.xodr"
    xodr.write_text("<OpenDRIVE/>", encoding="utf-8")

    scenario, interpretation = interpret_for_execution(xosc, xodr)
    registry = {
        "car": BlueprintRule("vehicle.car", "vehicle.tesla.model3", "bounding_box_center"),
    }
    mappings = map_blueprints(scenario, registry)
    plan = build_exact_pose_plan(
        xosc, xodr, scenario, _alignment(), mappings, timestep_s=0.5
    )
    batches = build_exact_pose_batches(plan, scenario)

    assert interpretation.interpretation_to_dict["interpreter_version"] == (
        XOSC_INTERPRETER_VERSION
    )
    assert scenario.entity_names == ("ego", "lead")
    assert scenario.trajectories["lead"] == interpretation.by_name("lead").trajectory
    assert interpretation.story_stop_conditions[0].value == 1.0
    assert {mapping.entity_name for mapping in mappings} == {"ego", "lead"}
    assert all(
        command.physics_enabled is False
        for batch in batches
        for command in batch.commands
    )
    assert plan.execution_identity.xosc_sha256 == interpretation.identity.xosc_sha256
