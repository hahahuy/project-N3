import json

import pytest

from real2scenario import Actor, Scenario, SelectionConfig, State, select_interaction_actors


def _actor(actor_id: str, positions: tuple[float, float], speed_mps: float = 0.0) -> Actor:
    return Actor(
        actor_id=actor_id,
        actor_type="vehicle",
        trajectory=tuple(
            State(time_s=float(index), x_m=x_m, y_m=0.0, yaw_rad=0.0, speed_mps=speed_mps)
            for index, x_m in enumerate(positions)
        ),
    )


def _scenario(*actors: Actor) -> Scenario:
    return Scenario(
        scenario_id="selection-fixture",
        duration_s=1.0,
        ego_actor_id="ego",
        actors=(_actor("ego", (0.0, 10.0), speed_mps=10.0), *actors),
        coordinate_frame="nuscenes_global",
        provenance={"dataset": "synthetic"},
    )


def test_selector_uses_distance_and_records_rejection_reason() -> None:
    scenario = _scenario(_actor("near", (15.0, 25.0)), _actor("far", (100.0, 100.0)))

    selected = select_interaction_actors(
        scenario, SelectionConfig(max_distance_m=20.0, max_ttc_s=0.0)
    )
    decisions = json.loads(selected.provenance["interaction_selection_decisions"])

    assert [actor.actor_id for actor in selected.actors] == ["ego", "near"]
    assert selected.provenance["selected_actor_ids"] == "near"
    assert decisions == [
        {
            "actor_id": "near",
            "decision": "selected",
            "reason": "distance",
            "minimum_distance_m": 15.0,
            "minimum_ttc_s": 1.5,
        },
        {
            "actor_id": "far",
            "decision": "rejected",
            "reason": "outside_distance_and_ttc_thresholds",
            "minimum_distance_m": 90.0,
            "minimum_ttc_s": 9.0,
        },
    ]


def test_selector_uses_ttc_when_distance_threshold_does_not_match() -> None:
    scenario = _scenario(_actor("closing", (50.0, 55.0), speed_mps=0.0))

    selected = select_interaction_actors(
        scenario, SelectionConfig(max_distance_m=10.0, max_ttc_s=6.0)
    )

    assert [actor.actor_id for actor in selected.actors] == ["ego", "closing"]
    decision = json.loads(selected.provenance["interaction_selection_decisions"])[0]
    assert decision["reason"] == "ttc"
    assert decision["minimum_ttc_s"] == 4.5


def test_selector_breaks_metric_ties_by_actor_id_and_caps_output() -> None:
    scenario = _scenario(
        _actor("charlie", (10.0, 20.0)),
        _actor("alpha", (10.0, 20.0)),
        _actor("bravo", (10.0, 20.0)),
    )

    selected = select_interaction_actors(
        scenario, SelectionConfig(max_distance_m=10.0, max_ttc_s=0.0, max_actors=2)
    )
    decisions = json.loads(selected.provenance["interaction_selection_decisions"])

    assert [actor.actor_id for actor in selected.actors] == ["ego", "alpha", "bravo"]
    assert next(item for item in decisions if item["actor_id"] == "charlie") == {
        "actor_id": "charlie",
        "decision": "rejected",
        "reason": "max_actors_limit",
        "minimum_distance_m": 10.0,
        "minimum_ttc_s": 1.0,
    }


def test_manual_override_preserves_order_bypasses_thresholds_and_does_not_mutate_source() -> None:
    scenario = _scenario(_actor("near", (15.0, 25.0)), _actor("far", (100.0, 100.0)))

    selected = select_interaction_actors(
        scenario,
        SelectionConfig(max_distance_m=1.0, max_ttc_s=0.0, manual_actor_ids=("far", "near")),
    )

    assert [actor.actor_id for actor in selected.actors] == ["ego", "far", "near"]
    assert [actor.actor_id for actor in scenario.actors] == ["ego", "near", "far"]
    assert json.loads(selected.provenance["interaction_selection_decisions"])[0]["reason"] == "manual_override"


@pytest.mark.parametrize(
    "config",
    [
        SelectionConfig(manual_actor_ids=("ego",)),
        SelectionConfig(manual_actor_ids=("missing",)),
    ],
)
def test_manual_override_rejects_invalid_actor_ids(config: SelectionConfig) -> None:
    with pytest.raises(ValueError, match="manual_actor_ids"):
        select_interaction_actors(_scenario(_actor("near", (15.0, 25.0))), config)
