"""Display-only top-down state composition for workspace previews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class TopDownState:
    contract_version: str
    requested_time_s: float
    resolved_time_s: float
    coordinate_frame: str
    map_name: str
    map_layers: Mapping[str, Any]
    actors: tuple[Mapping[str, Any], ...]
    provenance: Mapping[str, str]


class TopDownService:
    """Combine static local map geometry with canonical state at one playhead."""

    CONTRACT_VERSION = "workspace-top-down-state-v1"

    def __init__(
        self,
        *,
        actor_state_at: Callable[[float], Sequence[Mapping[str, Any]]],
        map_name: str,
        map_layers: Mapping[str, Any],
        coordinate_frame: str = "local_road_aligned",
    ) -> None:
        self._actor_state_at = actor_state_at
        self._map_name = map_name
        self._map_layers = map_layers
        self._coordinate_frame = coordinate_frame

    def state(self, time_s: float) -> TopDownState:
        actors = tuple(dict(actor) for actor in self._actor_state_at(time_s))
        return TopDownState(
            contract_version=self.CONTRACT_VERSION,
            requested_time_s=float(time_s),
            resolved_time_s=float(time_s),
            coordinate_frame=self._coordinate_frame,
            map_name=self._map_name,
            map_layers=self._map_layers,
            actors=actors,
            provenance={
                "map_source": "nuscenes-devkit-NuScenesMap",
                "actor_source": "canonical_scenario_states",
                "artifact_visibility": "local_private",
            },
        )
