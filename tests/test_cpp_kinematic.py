from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from real2scenario.kinematic import integrate_kinematic_open_loop
from scripts.benchmark_cpp_kinematic import make_input


def test_cpp_matches_python_kernel_if_binary_exists() -> None:
    binary = Path(__file__).parents[1] / "build" / "cpp" / "kinematic" / "r2s-kinematic-cli"
    if not binary.is_file():
        pytest.skip("C++ kinematic binary is not present")
    text, initial, source = make_input(8)
    result = subprocess.run((str(binary),), input=text, text=True, capture_output=True, check=True)
    cpp_rows = [tuple(float(value) for value in line.split()) for line in result.stdout.splitlines()]
    python_rows = [(state.time_s, state.x_m, state.y_m, state.yaw_rad, state.speed_mps) for state in integrate_kinematic_open_loop(initial, source).states]
    assert len(cpp_rows) == len(python_rows)
    assert all(len(row) == 5 for row in cpp_rows)
    for expected, actual in zip(python_rows, cpp_rows):
        assert actual == pytest.approx(expected, abs=1e-12)
