import pytest

from real2scenario import State, integrate_dynamic_single_track


def test_constant_speed_straight_profile_is_deterministic():
    initial = State(0, 0, 0, 0, 8)
    first = integrate_dynamic_single_track(initial, actor_id="car", duration_s=1.0)
    second = integrate_dynamic_single_track(initial, actor_id="car", duration_s=1.0)
    assert first == second
    assert first.status == "valid"
    assert first.states[-1].x_m == pytest.approx(8.0, abs=0.02)
    assert first.states[-1].y_m == pytest.approx(0.0, abs=0.02)


def test_low_speed_is_explicitly_unsupported():
    result = integrate_dynamic_single_track(State(0, 0, 0, 0, 0.5), actor_id="car", duration_s=1.0)
    assert result.status == "unsupported"
    assert result.violations[0].code == "dynamic_single_track_low_speed_model_guard"


def test_invalid_profile_is_rejected():
    with pytest.raises(ValueError, match="times must strictly increase"):
        integrate_dynamic_single_track(State(0, 0, 0, 0, 5), actor_id="car", duration_s=1, steering_profile=((0, 0), (0, 0.1)))
