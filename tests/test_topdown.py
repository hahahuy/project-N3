from r2s_web.topdown import TopDownService


def test_topdown_state_uses_requested_time_for_canonical_actor_state():
    service = TopDownService(
        actor_state_at=lambda time_s: ({"actor_id": "ego", "time_s": time_s, "yaw_rad": 0.5},),
        map_name="singapore-onenorth",
        map_layers={"lane": []},
    )

    state = service.state(1.25)

    assert state.contract_version == "workspace-top-down-state-v1"
    assert state.resolved_time_s == 1.25
    assert state.actors[0]["time_s"] == 1.25
    assert state.map_layers == {"lane": []}
    assert state.provenance["actor_source"] == "canonical_scenario_states"
