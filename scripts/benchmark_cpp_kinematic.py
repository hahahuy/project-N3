#!/usr/bin/env python3
"""Compare the approved Tier 1 Python kernel with the native C++ kernel."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
import time
from pathlib import Path

from real2scenario.kinematic import integrate_kinematic_open_loop
from real2scenario.models import State
from real2scenario.source_state import SOURCE_STATE_VERSION, SourceState, SourceStateExtension


def make_input(count: int = 512) -> tuple[str, State, SourceStateExtension]:
    initial = State(0.0, 0.0, 0.0, 0.0, 8.0)
    source = SourceStateExtension(
        SOURCE_STATE_VERSION,
        tuple(SourceState(index * 50_000, ((index % 11) - 5) * 0.1, ((index % 7) - 3) * 0.01, "finite_difference", "finite_difference") for index in range(count)),
        {"source": "synthetic-cpp-parity", "artifact_visibility": "public"},
    )
    lines = [f"{initial.x_m} {initial.y_m} {initial.yaw_rad} {initial.speed_mps} 0.05 {len(source.states)}"]
    lines.extend(f"{item.timestamp_us} {item.acceleration_mps2} {item.yaw_rate_radps}" for item in source.states)
    return "\n".join(lines) + "\n", initial, source


def main() -> int:
    root = Path(__file__).parents[1]
    binary = root / "build" / "cpp" / "kinematic" / "r2s-kinematic-cli"
    if not binary.is_file():
        raise SystemExit(f"missing C++ runner: {binary}; run cmake --build build/cpp/kinematic")
    text, initial, source = make_input()
    python_started = time.perf_counter()
    python_preview = integrate_kinematic_open_loop(initial, source)
    python_s = time.perf_counter() - python_started
    cpp_started = time.perf_counter()
    completed = subprocess.run((str(binary),), input=text, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"C++ runner failed ({completed.returncode}): {completed.stderr.strip()}")
    cpp_s = time.perf_counter() - cpp_started
    cpp_rows = []
    for line in completed.stdout.splitlines():
        values = line.split()
        if len(values) != 5 or not all(math.isfinite(float(value)) for value in values):
            raise SystemExit("C++ runner emitted malformed output")
        cpp_rows.append(tuple(float(value) for value in values))
    python_rows = [(state.time_s, state.x_m, state.y_m, state.yaw_rad, state.speed_mps) for state in python_preview.states]
    if len(cpp_rows) != len(python_rows):
        raise SystemExit(f"C++/Python row-count mismatch: python={len(python_rows)} cpp={len(cpp_rows)}")
    max_error = max(abs(left - right) for left_row, right_row in zip(python_rows, cpp_rows) for left, right in zip(left_row, right_row))
    output_hash = hashlib.sha256(completed.stdout.encode()).hexdigest()
    print(json.dumps({
        "benchmark_version": "cpp-kinematic-parity-v1",
        "implementation": "cpp-native",
        "samples": len(source.states),
        "python_wall_s": round(python_s, 6),
        "cpp_wall_s": round(cpp_s, 6),
        "state_count_python": len(python_rows),
        "state_count_cpp": len(cpp_rows),
        "max_abs_error": max_error,
        "parity_status": "match" if max_error <= 1e-12 else "mismatch",
        "output_sha256": output_hash,
        "scientific_role": "tier1_preview_engineering_only",
        "dec_018": "C++ preview never feeds native replay, replay.csv, ADE/FDE, gates or reports",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
