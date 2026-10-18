import pytest

from real2scenario import State, compare_trajectory


def test_experiment_metrics_align_candidate_to_reference_grid():
    reference = (State(0, 0, 0, 0, 1), State(1, 1, 0, 0, 1), State(2, 2, 0, 0, 1))
    candidate = (State(0, 0, 0, 0, 1), State(1, 1.1, 0, 0, 1), State(2, 2.1, 0, 0, 1))
    metrics = compare_trajectory(reference, candidate)
    assert metrics.coverage_status == "complete"
    assert metrics.position_fde_m == pytest.approx(0.1)
    assert metrics.position_ade_m == pytest.approx(0.0666666667)


def test_partial_coverage_has_no_fde():
    reference = (State(0, 0, 0, 0, 1), State(1, 1, 0, 0, 1), State(2, 2, 0, 0, 1))
    candidate = (State(0, 0, 0, 0, 1), State(1, 1, 0, 0, 1))
    metrics = compare_trajectory(reference, candidate)
    assert metrics.coverage_status == "partial"
    assert metrics.position_fde_m is None
