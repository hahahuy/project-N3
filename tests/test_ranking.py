import pytest

from real2scenario import (
    RANKING_VERSION,
    Actor,
    FeasibilityLimits,
    RankingWeights,
    Scenario,
    State,
    VariantConfig,
    compute_risk_features,
    perturb_scenario,
    rank_scenario,
    validate_feasibility,
)


def _scenario() -> Scenario:
    return Scenario(
        scenario_id="ranking-fixture",
        duration_s=2.0,
        ego_actor_id="ego",
        actors=(
            Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 10.0), State(2.0, 20.0, 0.0, 0.0, 10.0))),
            Actor("lead", "vehicle", (State(0.0, 20.0, 0.0, 0.0, 5.0), State(2.0, 30.0, 0.0, 0.0, 5.0))),
        ),
        coordinate_frame="local_road_aligned",
    )


def test_risk_features_compute_distance_ttc_and_novelty() -> None:
    parent = _scenario()
    variant = perturb_scenario(parent, VariantConfig(initial_gap_delta_m=-2.0))

    features = compute_risk_features(variant, parent_scenario=parent)

    assert features.minimum_distance_m == pytest.approx(8.0)
    assert features.minimum_ttc_s == pytest.approx(1.6)
    assert features.novelty == pytest.approx(1.0)
    assert features.risk_signal == pytest.approx(1 / 9 + 1 / 2.6)


def test_valid_scenario_has_transparent_score_breakdown() -> None:
    scenario = _scenario()
    feasibility = validate_feasibility(scenario, FeasibilityLimits(max_acceleration_mps2=0.0))
    result = rank_scenario(
        scenario,
        feasibility,
        weights=RankingWeights(risk_signal=2.0, novelty=3.0, replay_quality=4.0, version="rank-test-v1"),
        replay_quality=0.5,
    )

    assert result.valid
    assert result.rankable
    assert result.ranking_version == "rank-test-v1"
    assert result.breakdown is not None
    assert result.breakdown.risk_signal == pytest.approx(2.0 * (1 / 11 + 1 / 3))
    assert result.breakdown.novelty == 0.0
    assert result.breakdown.replay_quality == pytest.approx(2.0)
    assert result.breakdown.total == pytest.approx(2.0 + 2.0 * (1 / 11 + 1 / 3))


def test_invalid_scenario_is_not_rankable() -> None:
    baseline = _scenario()
    scenario = Scenario(
        baseline.scenario_id,
        baseline.duration_s,
        baseline.ego_actor_id,
        (
            Actor(
                "ego",
                "vehicle",
                (State(0.0, 0.0, 0.0, 0.0, 10.0), State(2.0, 20.0, 0.0, 0.0, 14.0)),
            ),
            baseline.actors[1],
        ),
        baseline.coordinate_frame,
    )
    feasibility = validate_feasibility(scenario, FeasibilityLimits(max_acceleration_mps2=1.0))

    result = rank_scenario(scenario, feasibility)

    assert not result.valid
    assert not result.rankable
    assert result.breakdown is None
    assert result.features.minimum_distance_m == pytest.approx(10.0)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"risk_signal": -1.0}, "non-negative"),
        ({"novelty": float("nan")}, "non-negative"),
        ({"version": ""}, "version"),
    ],
)
def test_ranking_weights_reject_invalid_values(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        RankingWeights(**kwargs)  # type: ignore[arg-type]


def test_ranking_rejects_invalid_feature_parameters() -> None:
    with pytest.raises(ValueError, match="collision_distance_m"):
        compute_risk_features(_scenario(), collision_distance_m=-1.0)
    with pytest.raises(ValueError, match="ttc_horizon_s"):
        compute_risk_features(_scenario(), ttc_horizon_s=0.0)
    with pytest.raises(ValueError, match="replay_quality"):
        rank_scenario(_scenario(), validate_feasibility(_scenario()), replay_quality=float("nan"))


def test_default_ranking_version_is_explicit() -> None:
    assert RankingWeights().version == RANKING_VERSION
