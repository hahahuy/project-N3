import pytest

from r2s_web.preview_time import resolve_preview_time


TIMESTAMPS = (1_000_000, 1_500_000, 2_000_000)


def test_preview_time_is_relative_to_source_window_start():
    result = resolve_preview_time(0.0, TIMESTAMPS)

    assert result.index == 0
    assert result.timestamp_us == 1_000_000
    assert result.resolved_time_s == 0.0
    assert result.delta_s == 0.0


def test_nearest_preview_time_reports_signed_delta():
    result = resolve_preview_time(0.4, TIMESTAMPS)

    assert result.timestamp_us == 1_500_000
    assert result.resolved_time_s == 0.5
    assert result.delta_s == pytest.approx(0.1)
    assert result.policy == "nearest"


def test_at_or_before_never_selects_a_future_record():
    result = resolve_preview_time(0.9, TIMESTAMPS, policy="at-or-before")

    assert result.timestamp_us == 1_500_000
    assert result.resolved_time_s == 0.5
    assert result.delta_s == pytest.approx(-0.4)


@pytest.mark.parametrize(
    ("timestamps", "error"),
    [
        ((), "preview_timestamps_unavailable"),
        ((1_000_000, 1_000_000), "preview_timestamps_not_strictly_increasing"),
    ],
)
def test_preview_time_fails_closed(timestamps, error):
    with pytest.raises(ValueError, match=error):
        resolve_preview_time(0.0, timestamps)


def test_preview_time_rejects_unknown_policy():
    with pytest.raises(ValueError, match="unsupported_preview_time_policy"):
        resolve_preview_time(0.0, TIMESTAMPS, policy="future")


def test_nearest_ties_choose_the_earlier_record():
    result = resolve_preview_time(0.25, TIMESTAMPS)

    assert result.timestamp_us == 1_000_000
