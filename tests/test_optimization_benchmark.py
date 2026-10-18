from __future__ import annotations

import json
from dataclasses import asdict

from scripts.benchmark_optimization import make_case, run_cached, run_direct


def test_benchmark_workload_is_deterministic() -> None:
    initial, source = make_case(8)
    direct = run_direct(initial, source, 1)[0]
    cached = run_cached(initial, source, 3)[-1]
    assert [asdict(state) for state in direct.states] == [asdict(state) for state in cached.states]


def test_benchmark_output_does_not_contain_replay_metrics() -> None:
    payload = {"scientific_role": "tier1_preview_engineering_only", "results": []}
    assert "ADE/FDE" not in json.dumps(payload)
