import pytest

from real2scenario import Actor, ActorMotionEdit, Scenario, State, VariantConfig, preview_variant


def _state(time_s: float = 0.0) -> State:
    return State(time_s=time_s, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0)


def _ego_actor() -> Actor:
    return Actor(actor_id="ego", actor_type="vehicle", trajectory=(_state(),))


def test_scenario_accepts_a_valid_ego_trajectory() -> None:
    ego = Actor(
        actor_id="ego",
        actor_type="vehicle",
        trajectory=(
            State(time_s=0.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=1.0),
            State(time_s=1.0, x_m=1.0, y_m=0.0, yaw_rad=0.0, speed_mps=1.0),
        ),
    )

    scenario = Scenario(
        scenario_id="scene-001",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(ego,),
        coordinate_frame="local_enu",
        provenance={"dataset": "fixture"},
    )

    assert scenario.ego_actor_id == "ego"
    assert scenario.actors[0].trajectory[-1].x_m == 1.0


def test_actor_rejects_non_monotonic_timestamps() -> None:
    states = (
        State(time_s=1.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0),
        State(time_s=1.0, x_m=1.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0),
    )

    with pytest.raises(ValueError, match="strictly increase"):
        Actor(actor_id="ego", actor_type="vehicle", trajectory=states)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_state_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        State(time_s=0.0, x_m=value, y_m=0.0, yaw_rad=0.0, speed_mps=0.0)


def test_state_rejects_negative_time() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _state(-0.1)


def test_state_accepts_optional_raw_source_provenance() -> None:
    state = State(
        time_s=0.0,
        x_m=0.0,
        y_m=0.0,
        yaw_rad=0.0,
        speed_mps=0.0,
        source_timestamp_us=123,
        source_record_token="annotation-token",
    )

    assert state.source_timestamp_us == 123
    assert state.source_record_token == "annotation-token"


@pytest.mark.parametrize(
    ("actor_id", "actor_type", "trajectory", "message"),
    [
        ("", "vehicle", (_state(),), "actor_id"),
        ("ego", "", (_state(),), "actor_type"),
        ("ego", "vehicle", (), "at least one"),
    ],
)
def test_actor_rejects_empty_required_fields(
    actor_id: str, actor_type: str, trajectory: tuple[State, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Actor(actor_id=actor_id, actor_type=actor_type, trajectory=trajectory)


@pytest.mark.parametrize("dimension", [0.0, -1.0, float("nan")])
def test_actor_rejects_invalid_dimensions(dimension: float) -> None:
    with pytest.raises(ValueError, match="dimensions"):
        Actor(
            actor_id="ego",
            actor_type="vehicle",
            trajectory=(_state(),),
            length_m=dimension,
        )


def test_scenario_rejects_missing_ego() -> None:
    actor = Actor(
        actor_id="lead",
        actor_type="vehicle",
        trajectory=(State(time_s=0.0, x_m=0.0, y_m=0.0, yaw_rad=0.0, speed_mps=0.0),),
    )

    with pytest.raises(ValueError, match="ego_actor_id"):
        Scenario(
            scenario_id="scene-001",
            duration_s=1.0,
            ego_actor_id="ego",
            actors=(actor,),
            coordinate_frame="local_enu",
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"scenario_id": ""}, "scenario_id"),
        ({"duration_s": 0.0}, "duration_s"),
        ({"coordinate_frame": ""}, "coordinate_frame"),
        ({"actors": ()}, "at least one"),
    ],
)
def test_scenario_rejects_invalid_required_fields(kwargs: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "scenario_id": "scene-001",
        "duration_s": 1.0,
        "ego_actor_id": "ego",
        "actors": (_ego_actor(),),
        "coordinate_frame": "local_enu",
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        Scenario(**values)  # type: ignore[arg-type]


def test_scenario_rejects_duplicate_actor_ids() -> None:
    ego = _ego_actor()
    duplicate = Actor(actor_id="ego", actor_type="vehicle", trajectory=(_state(),))

    with pytest.raises(ValueError, match="unique"):
        Scenario(
            scenario_id="scene-001",
            duration_s=1.0,
            ego_actor_id="ego",
            actors=(ego, duplicate),
            coordinate_frame="local_enu",
        )


def test_scenario_rejects_trajectory_beyond_duration() -> None:
    ego = Actor(actor_id="ego", actor_type="vehicle", trajectory=(_state(2.0),))

    with pytest.raises(ValueError, match="cover"):
        Scenario(
            scenario_id="scene-001",
            duration_s=1.0,
            ego_actor_id="ego",
            actors=(ego,),
            coordinate_frame="local_enu",
        )


def test_variant_config_requires_a_positive_speed_multiplier() -> None:
    with pytest.raises(ValueError, match="positive"):
        VariantConfig(speed_multiplier=0.0)


@pytest.mark.parametrize("field", ["initial_gap_delta_m", "timing_offset_s"])
def test_variant_config_rejects_non_finite_offsets(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        VariantConfig(**{field: float("nan")})


def test_preview_variant_is_actor_scoped_deterministic_and_immutable() -> None:
    ego = Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 2.0), State(1.0, 2.0, 0.0, 0.0, 2.0)))
    lead = Actor("lead", "vehicle", (State(0.0, 5.0, 0.0, 0.0, 3.0), State(1.0, 8.0, 0.0, 0.0, 3.0)))
    parent = Scenario("scene", 1.0, "ego", (ego, lead), "local", {"dataset_name": "fixture"})
    edit = ActorMotionEdit("lead", speed_multiplier=1.2, heading_offset_rad=0.1, initial_gap_delta_m=-1.0)

    first = preview_variant(parent, (edit,), seed=7)
    second = preview_variant(parent, (edit,), seed=7)

    assert first == second
    assert first.scenario_id.startswith("scene--preview-")
    assert parent.actors == (ego, lead)
    assert first.actors[0] == ego
    assert first.actors[1].trajectory[0].x_m == 4.0
    assert first.actors[1].trajectory[0].yaw_rad == 0.1
