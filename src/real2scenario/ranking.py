"""Risk and novelty features for validated scenario ranking."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, sin

from .models import Scenario
from .validation import FeasibilityReport


RANKING_VERSION = "risk-ranking-v1"


@dataclass(frozen=True, slots=True)
class RankingWeights:
    """Versioned weights for the transparent ranking score."""

    risk_signal: float = 1.0
    novelty: float = 1.0
    replay_quality: float = 0.0
    feasibility_penalty: float = 1.0
    version: str = RANKING_VERSION

    def __post_init__(self) -> None:
        values = (self.risk_signal, self.novelty, self.replay_quality, self.feasibility_penalty)
        if not all(isfinite(value) and value >= 0 for value in values):
            raise ValueError("Ranking weights must be finite and non-negative.")
        if not self.version:
            raise ValueError("RankingWeights version must not be empty.")


@dataclass(frozen=True, slots=True)
class RiskFeatures:
    """Raw, interpretable risk and novelty features."""

    minimum_distance_m: float | None
    minimum_ttc_s: float | None
    novelty: float
    risk_signal: float


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Score components retained for review and reproducibility."""

    risk_signal: float
    novelty: float
    replay_quality: float
    feasibility_penalty: float
    total: float


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Ranking result that distinguishes invalid variants from valid scores."""

    scenario_id: str
    ranking_version: str
    valid: bool
    rankable: bool
    features: RiskFeatures
    breakdown: ScoreBreakdown | None


def compute_risk_features(
    scenario: Scenario,
    *,
    parent_scenario: Scenario | None = None,
    collision_distance_m: float = 0.0,
    ttc_horizon_s: float = 10.0,
) -> RiskFeatures:
    """Compute minimum pairwise distance, conservative TTC, and novelty."""
    if collision_distance_m < 0 or not isfinite(collision_distance_m):
        raise ValueError("collision_distance_m must be finite and non-negative.")
    if ttc_horizon_s <= 0 or not isfinite(ttc_horizon_s):
        raise ValueError("ttc_horizon_s must be finite and positive.")
    minimum_distance, minimum_ttc = _pairwise_features(scenario, ttc_horizon_s)
    novelty = _scenario_novelty(scenario, parent_scenario)
    risk_signal = 0.0 if minimum_distance is None else (
        max(0.0, collision_distance_m - minimum_distance)
        if collision_distance_m
        else 1.0 / (1.0 + minimum_distance)
    )
    if minimum_ttc is not None:
        risk_signal += 1.0 / (1.0 + minimum_ttc)
    return RiskFeatures(
        minimum_distance_m=minimum_distance,
        minimum_ttc_s=minimum_ttc,
        novelty=novelty,
        risk_signal=risk_signal,
    )


def rank_scenario(
    scenario: Scenario,
    feasibility: FeasibilityReport,
    *,
    parent_scenario: Scenario | None = None,
    weights: RankingWeights = RankingWeights(),
    replay_quality: float = 0.0,
) -> RankingResult:
    """Rank a valid scenario, or return an explicitly non-rankable result."""
    if not isfinite(replay_quality):
        raise ValueError("replay_quality must be finite.")
    features = compute_risk_features(scenario, parent_scenario=parent_scenario)
    if not feasibility.valid:
        return RankingResult(
            scenario_id=scenario.scenario_id,
            ranking_version=weights.version,
            valid=False,
            rankable=False,
            features=features,
            breakdown=None,
        )
    breakdown = ScoreBreakdown(
        risk_signal=weights.risk_signal * features.risk_signal,
        novelty=weights.novelty * features.novelty,
        replay_quality=weights.replay_quality * replay_quality,
        feasibility_penalty=0.0,
        total=(
            weights.risk_signal * features.risk_signal
            + weights.novelty * features.novelty
            + weights.replay_quality * replay_quality
        ),
    )
    return RankingResult(
        scenario_id=scenario.scenario_id,
        ranking_version=weights.version,
        valid=True,
        rankable=True,
        features=features,
        breakdown=breakdown,
    )


def _pairwise_features(scenario: Scenario, horizon_s: float) -> tuple[float | None, float | None]:
    minimum_distance: float | None = None
    minimum_ttc: float | None = None
    for first_index, first_actor in enumerate(scenario.actors):
        for second_actor in scenario.actors[first_index + 1 :]:
            for first_state in first_actor.trajectory:
                second_state = min(
                    second_actor.trajectory,
                    key=lambda state: abs(state.time_s - first_state.time_s),
                )
                if abs(second_state.time_s - first_state.time_s) > 1e-9:
                    continue
                dx = second_state.x_m - first_state.x_m
                dy = second_state.y_m - first_state.y_m
                distance = _distance(0.0, 0.0, dx, dy)
                minimum_distance = distance if minimum_distance is None else min(minimum_distance, distance)
                if distance == 0:
                    minimum_ttc = 0.0
                    continue
                relative_vx = second_state.speed_mps * cos(second_state.yaw_rad) - first_state.speed_mps * cos(first_state.yaw_rad)
                relative_vy = second_state.speed_mps * sin(second_state.yaw_rad) - first_state.speed_mps * sin(first_state.yaw_rad)
                closing_rate = -(relative_vx * dx + relative_vy * dy) / distance
                if closing_rate > 0:
                    ttc = min(horizon_s, distance / closing_rate)
                    minimum_ttc = ttc if minimum_ttc is None else min(minimum_ttc, ttc)
    return minimum_distance, minimum_ttc


def _scenario_novelty(scenario: Scenario, parent_scenario: Scenario | None) -> float:
    if parent_scenario is None:
        return 0.0
    deltas: list[float] = []
    parent_actors = {actor.actor_id: actor for actor in parent_scenario.actors}
    for actor in scenario.actors:
        parent = parent_actors.get(actor.actor_id)
        if parent is None:
            continue
        for state, parent_state in zip(actor.trajectory, parent.trajectory):
            deltas.append(
                _distance(state.x_m, state.y_m, parent_state.x_m, parent_state.y_m)
            )
    return sum(deltas) / len(deltas) if deltas else 0.0


def _distance(first_x: float, first_y: float, second_x: float, second_y: float) -> float:
    return ((first_x - second_x) ** 2 + (first_y - second_y) ** 2) ** 0.5
