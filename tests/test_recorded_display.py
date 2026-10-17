from r2s_web.recorded_display import build_recorded_display_timeline
from real2scenario.models import Actor, State


def test_recorded_display_tracks_lifecycle_without_mutating_actor_population():
    actor = Actor(
        actor_id="recorded-1",
        actor_type="vehicle.car",
        trajectory=(State(1.0, 1.0, 2.0, 0.0, 1.0), State(2.0, 2.0, 2.0, 0.0, 1.0)),
    )
    timeline = build_recorded_display_timeline((actor,))
    assert timeline.contract_version == "recorded-display-timeline-v1"
    assert timeline.active_at(0.5) == ()
    assert len(timeline.active_at(1.5)) == 1
    assert timeline.active_at(2.1) == ()
