"""Curated OpenDRIVE template selection for local replay approximations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .models import Scenario


TEMPLATE_REGISTRY_VERSION = "opendrive-template-registry-v1"
STRAIGHT_ROAD_TOPOLOGY = "straight_road"


@dataclass(frozen=True, slots=True)
class OpenDriveTemplate:
    """A supported local OpenDRIVE reconstruction template."""

    template_id: str
    version: str
    topology: str
    relative_path: str
    description: str

    def path(self) -> Path:
        """Return the installed template path without embedding machine-specific paths."""
        return Path(str(files("real2scenario") / self.relative_path))


_STRAIGHT_ROAD_TEMPLATE = OpenDriveTemplate(
    template_id="straight-two-lane",
    version="1.0",
    topology=STRAIGHT_ROAD_TOPOLOGY,
    relative_path="templates/straight-two-lane-v1.xodr",
    description="Two-lane straight road used as a local road-aligned approximation.",
)


def select_opendrive_template(
    scenario: Scenario, *, topology: str
) -> tuple[Scenario, OpenDriveTemplate]:
    """Select an explicit supported template and record the approximation decision."""
    if scenario.coordinate_frame != "local_road_aligned":
        raise ValueError(
            "OpenDRIVE template selection requires a scenario in the "
            "'local_road_aligned' coordinate frame."
        )
    if topology != STRAIGHT_ROAD_TOPOLOGY:
        raise ValueError(
            f"Unsupported road topology {topology!r}; supported topologies: "
            f"{STRAIGHT_ROAD_TOPOLOGY!r}."
        )
    template = _STRAIGHT_ROAD_TEMPLATE
    if not template.path().is_file():
        raise ValueError(f"OpenDRIVE template {template.template_id!r} is not installed.")

    provenance = {
        **scenario.provenance,
        "map_reconstruction_mode": "local-template-approximation",
        "map_reconstruction_version": TEMPLATE_REGISTRY_VERSION,
        "opendrive_template_id": template.template_id,
        "opendrive_template_version": template.version,
        "opendrive_template_topology": template.topology,
        "opendrive_template_selection_reason": (
            "explicit_supported_topology:straight_road; "
            "local_road_aligned_approximation"
        ),
    }
    selected = Scenario(
        scenario_id=scenario.scenario_id,
        duration_s=scenario.duration_s,
        ego_actor_id=scenario.ego_actor_id,
        actors=scenario.actors,
        coordinate_frame=scenario.coordinate_frame,
        provenance=provenance,
    )
    return selected, template
