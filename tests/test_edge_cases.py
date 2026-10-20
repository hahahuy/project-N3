"""Boundary cases for the simulator-independent scenario contracts."""

import pytest

from real2scenario import Actor, InteractionEvent, Scenario, State, VariantConfig


def _state(time_s: float = 0.0) -> State:
    return State(time_s, 0.0, 0.0, 0.0, 0.0)


def _actor(actor_id: str = "ego") -> Actor:
    return Actor(actor_id, "vehicle", (_state(),))


EDGE_CASES = [
    # State: finite numeric values, nonnegative time and source identity.
    pytest.param(lambda: State(float("nan"), 0, 0, 0, 0), "finite", id="state-time-nan"),
    pytest.param(lambda: State(float("inf"), 0, 0, 0, 0), "finite", id="state-time-infinite"),
    pytest.param(lambda: State(-1, 0, 0, 0, 0), "non-negative", id="state-negative-time"),
    pytest.param(lambda: State(0, float("nan"), 0, 0, 0), "finite", id="state-x-nan"),
    pytest.param(lambda: State(0, float("inf"), 0, 0, 0), "finite", id="state-x-infinite"),
    pytest.param(lambda: State(0, 0, float("nan"), 0, 0), "finite", id="state-y-nan"),
    pytest.param(lambda: State(0, 0, 0, float("inf"), 0), "finite", id="state-yaw-infinite"),
    pytest.param(lambda: State(0, 0, 0, 0, float("nan")), "finite", id="state-speed-nan"),
    pytest.param(lambda: State(0, 0, 0, 0, 0, True), "non-negative integer", id="state-bool-timestamp"),
    pytest.param(lambda: State(0, 0, 0, 0, 0, 1.5), "non-negative integer", id="state-fractional-timestamp"),
    pytest.param(lambda: State(0, 0, 0, 0, 0, -1), "non-negative integer", id="state-negative-timestamp"),
    pytest.param(lambda: State(0, 0, 0, 0, 0, source_record_token=""), "must not be empty", id="state-empty-record-token"),
    # Actor: identity, strict time ordering and physical dimensions.
    pytest.param(lambda: Actor("", "vehicle", (_state(),)), "actor_id", id="actor-empty-id"),
    pytest.param(lambda: Actor("car", "", (_state(),)), "actor_type", id="actor-empty-type"),
    pytest.param(lambda: Actor("car", "vehicle", ()), "at least one state", id="actor-empty-trajectory"),
    pytest.param(lambda: Actor("car", "vehicle", (_state(1), _state(1))), "strictly increase", id="actor-duplicate-time"),
    pytest.param(lambda: Actor("car", "vehicle", (_state(2), _state(1))), "strictly increase", id="actor-descending-time"),
    pytest.param(lambda: Actor("car", "vehicle", (_state(),), length_m=0), "finite and positive", id="actor-zero-length"),
    pytest.param(lambda: Actor("car", "vehicle", (_state(),), width_m=-0.1), "finite and positive", id="actor-negative-width"),
    pytest.param(lambda: Actor("car", "vehicle", (_state(),), height_m=float("inf")), "finite and positive", id="actor-infinite-height"),
    pytest.param(lambda: Actor("car", "vehicle", (_state(),), length_m=float("nan")), "finite and positive", id="actor-nan-length"),
    # Variant configuration: positive scale, finite offsets and integer seed.
    pytest.param(lambda: VariantConfig(speed_multiplier=0), "finite and positive", id="variant-zero-speed-scale"),
    pytest.param(lambda: VariantConfig(speed_multiplier=-1), "finite and positive", id="variant-negative-speed-scale"),
    pytest.param(lambda: VariantConfig(speed_multiplier=float("nan")), "finite and positive", id="variant-nan-speed-scale"),
    pytest.param(lambda: VariantConfig(speed_multiplier=float("inf")), "finite and positive", id="variant-infinite-speed-scale"),
    pytest.param(lambda: VariantConfig(initial_gap_delta_m=float("nan")), "finite", id="variant-nan-gap-offset"),
    pytest.param(lambda: VariantConfig(initial_gap_delta_m=float("inf")), "finite", id="variant-infinite-gap-offset"),
    pytest.param(lambda: VariantConfig(timing_offset_s=float("nan")), "finite", id="variant-nan-timing-offset"),
    pytest.param(lambda: VariantConfig(timing_offset_s=float("inf")), "finite", id="variant-infinite-timing-offset"),
    pytest.param(lambda: VariantConfig(seed=True), "integer", id="variant-boolean-seed"),
    pytest.param(lambda: VariantConfig(seed=2.5), "integer", id="variant-fractional-seed"),
    # Interaction event: participant list, interval and confidence boundaries.
    pytest.param(lambda: InteractionEvent("", ("ego",), 0, 0), "label", id="event-empty-label"),
    pytest.param(lambda: InteractionEvent("merge", (), 0, 0), "actor_ids", id="event-no-participants"),
    pytest.param(lambda: InteractionEvent("merge", ("ego", "ego"), 0, 0), "unique", id="event-duplicate-participant"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), -0.1, 0), "non-negative", id="event-negative-start"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), 1, 0), "must not precede", id="event-reversed-interval"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), float("nan"), 1), "finite", id="event-nan-start"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), 0, float("inf")), "finite", id="event-infinite-end"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), 0, 0, derivation=""), "derivation", id="event-empty-derivation"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), 0, 0, confidence=-0.01), r"\[0, 1\]", id="event-confidence-below-zero"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), 0, 0, confidence=1.01), r"\[0, 1\]", id="event-confidence-above-one"),
    pytest.param(lambda: InteractionEvent("merge", ("ego",), 0, 0, confidence=True), r"\[0, 1\]", id="event-boolean-confidence"),
    # Scenario: required population and consistency across actor references.
    pytest.param(lambda: Scenario("", 1, "ego", (_actor(),), "local"), "scenario_id", id="scenario-empty-id"),
    pytest.param(lambda: Scenario("s", 0, "ego", (_actor(),), "local"), "finite and positive", id="scenario-zero-duration"),
    pytest.param(lambda: Scenario("s", 1, "ego", (_actor(),), ""), "coordinate_frame", id="scenario-empty-frame"),
    pytest.param(lambda: Scenario("s", 1, "ego", (), "local"), "at least one actor", id="scenario-no-actors"),
    pytest.param(lambda: Scenario("s", 1, "missing", (_actor(),), "local"), "must identify an actor", id="scenario-ego-absent"),
    pytest.param(lambda: Scenario("s", 0.5, "ego", (Actor("ego", "vehicle", (_state(1),)),), "local"), "must cover", id="scenario-duration-shorter-than-track"),
    pytest.param(lambda: Scenario("s", 1, "ego", (_actor(), _actor()), "local"), "unique", id="scenario-duplicate-actor-id"),
    pytest.param(
        lambda: Scenario(
            "s", 1, "ego", (_actor(),), "local",
            interaction_events=(InteractionEvent("merge", ("ghost",), 0, 0),),
        ),
        "unknown actors",
        id="scenario-event-references-unknown-actor",
    ),
]


@pytest.mark.parametrize(("build", "message"), EDGE_CASES)
def test_contract_rejects_edge_case(build, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build()
