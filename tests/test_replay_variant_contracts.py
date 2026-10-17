"""Contracts for replay metrics, feasibility checks, variant generation and XOSC export.

Every expected value is computed by hand from a small synthetic scenario, so a
failure points at the code under test rather than at recorded data. Tests
marked ``xfail`` pin known defects; they flip to XPASS once the defect is fixed.
"""

import json
import math
import xml.etree.ElementTree as ET

import pytest

from real2scenario.exporter import build_openscenario_xml
from real2scenario.generation import (
    ActorMotionEdit,
    batch_manifest_to_json,
    generate_grid_variants,
    generate_random_variants,
    perturb_scenario,
    preview_variant,
)
from real2scenario.metrics import aggregate_replay_metrics, compute_replay_metrics
from real2scenario.models import Actor, Scenario, State, VariantConfig
from real2scenario.serialization import scenario_from_dict, scenario_to_dict
from real2scenario.templates import select_opendrive_template
from real2scenario.validation import FeasibilityLimits, validate_feasibility


def _line(x0, y0, vx, vy, *, t0=0.0, steps=13, dt=0.5, yaw=None):
    """States of a constant-velocity actor sampled every ``dt`` seconds."""
    heading = math.atan2(vy, vx) if yaw is None else yaw
    speed = math.hypot(vx, vy)
    return tuple(
        State(t0 + i * dt, x0 + vx * i * dt, y0 + vy * i * dt, heading, speed) for i in range(steps)
    )


def _scenario(*actors, scenario_id="s", duration_s=6.0):
    return Scenario(scenario_id, duration_s, actors[0].actor_id, tuple(actors), "local_road_aligned")


def _ego():
    return Actor("ego", "vehicle.ego", _line(0.0, 0.0, 10.0, 0.0), 4.5, 1.9)


def _lead():
    return Actor("lead", "vehicle.car", _line(30.0, 0.0, 10.0, 0.0), 4.5, 1.9)


def _cross():
    return Actor("cross", "vehicle.car", _line(40.0, -20.0, 0.0, 5.0), 4.5, 1.9)


def _actor(scenario, actor_id):
    return next(actor for actor in scenario.actors if actor.actor_id == actor_id)


def _xml(scenario):
    selected, template = select_opendrive_template(scenario, topology="straight_road")
    return ET.fromstring(build_openscenario_xml(selected, template).split("\n", 1)[1])


def test_identical_replay_has_zero_error_and_complete_coverage():
    states = _line(0.0, 0.0, 10.0, 0.0)
    metrics = compute_replay_metrics(states, states)
    assert metrics.position_rmse_m == 0.0
    assert metrics.ade_m == 0.0
    assert metrics.fde_m == 0.0
    assert metrics.heading_mae_rad == 0.0
    assert metrics.speed_mae_mps == 0.0
    assert metrics.coverage_status == "complete"
    assert metrics.sample_count == len(states)


def test_constant_lateral_offset_sets_rmse_ade_and_fde_to_the_offset():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    replayed = _line(0.0, 0.5, 10.0, 0.0)
    metrics = compute_replay_metrics(recorded, replayed)
    assert metrics.position_rmse_m == pytest.approx(0.5)
    assert metrics.ade_m == pytest.approx(0.5)
    assert metrics.fde_m == pytest.approx(0.5)
    assert metrics.final_displacement_m == pytest.approx(0.5)


def test_denser_replay_is_interpolated_at_recorded_times():
    recorded = _line(0.0, 0.0, 10.0, 0.0)
    replayed = _line(0.0, 0.0, 10.0, 0.0, steps=25, dt=0.25)
    metrics = compute_replay_metrics(recorded, replayed)
    assert metrics.ade_m == pytest.approx(0.0, abs=1e-9)
    assert metrics.sample_count == len(recorded)


def test_heading_error_wraps_across_the_pi_boundary():
    recorded = _line(0.0, 0.0, 10.0, 0.0, yaw=math.pi - 0.01)
    replayed = _line(0.0, 0.0, 10.0, 0.0, yaw=-math.pi + 0.01)
    metrics = compute_replay_metrics(recorded, replayed)
    assert metrics.heading_mae_rad == pytest.approx(0.02, abs=1e-9)
