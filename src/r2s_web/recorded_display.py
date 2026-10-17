"""Packed, display-only recorded actor timeline helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from real2scenario import Actor


@dataclass(frozen=True, slots=True)
class RecordedDisplayObject:
    actor_id: str
    actor_type: str
    first_seen_time_s: float
    last_seen_time_s: float
    states: tuple[dict[str, float | int | str | None], ...]

    def active_at(self, time_s: float) -> bool:
        return self.first_seen_time_s <= time_s <= self.last_seen_time_s


@dataclass(frozen=True, slots=True)
class RecordedDisplayTimeline:
    contract_version: str
    objects: tuple[RecordedDisplayObject, ...]
    state_count: int

    def active_at(self, time_s: float) -> tuple[RecordedDisplayObject, ...]:
        return tuple(item for item in self.objects if item.active_at(time_s))


def build_recorded_display_timeline(actors: Iterable[Actor]) -> RecordedDisplayTimeline:
    objects = []
    for actor in actors:
        if not actor.trajectory:
            continue
        objects.append(RecordedDisplayObject(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            first_seen_time_s=actor.trajectory[0].time_s,
            last_seen_time_s=actor.trajectory[-1].time_s,
            states=tuple({
                "time_s": state.time_s,
                "x_m": state.x_m,
                "y_m": state.y_m,
                "yaw_rad": state.yaw_rad,
                "speed_mps": state.speed_mps,
                "source_timestamp_us": state.source_timestamp_us,
                "source_record_token": state.source_record_token,
            } for state in actor.trajectory),
        ))
    return RecordedDisplayTimeline(
        contract_version="recorded-display-timeline-v1",
        objects=tuple(objects),
        state_count=sum(len(item.states) for item in objects),
    )
