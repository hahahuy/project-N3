#!/usr/bin/env python3
"""Reproducible engineering benchmark for the phased optimization track.

This intentionally benchmarks Tier 1 preview computation, not native replay.
It never creates replay.csv and never emits ADE/FDE, gate or report evidence.
The experimental column is reported as unavailable unless an explicitly
configured external runner is supplied.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import resource
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from real2scenario.kinematic import integrate_kinematic_open_loop
from real2scenario.models import State
from real2scenario.source_state import SourceState, SourceStateExtension, SOURCE_STATE_VERSION


def make_case(samples: int, seed: int = 7) -> tuple[State, SourceStateExtension]:
    states = tuple(
        SourceState(
            timestamp_us=index * 50_000,
            acceleration_mps2=((index + seed) % 11 - 5) * 0.1,
            yaw_rate_radps=((index * 3 + seed) % 7 - 3) * 0.01,
            acceleration_source="finite_difference",
            yaw_rate_source="finite_difference",
        )
        for index in range(samples)
    )
    return State(0.0, 0.0, 0.0, 0.0, 8.0), SourceStateExtension(
        SOURCE_STATE_VERSION,
        states,
        {"source": "benchmark-synthetic", "artifact_visibility": "public"},
    )


def run_direct(initial: State, source: SourceStateExtension, repeats: int):
    return [integrate_kinematic_open_loop(initial, source) for _ in range(repeats)]


def run_cached(initial: State, source: SourceStateExtension, repeats: int):
    cache: dict[str, object] = {}
    key = hashlib.sha256(repr((asdict(initial), tuple(asdict(item) for item in source.states))).encode()).hexdigest()
    output = []
    for _ in range(repeats):
        if key not in cache:
            cache[key] = integrate_kinematic_open_loop(initial, source)
        output.append(cache[key])
    return output


async def run_async(initial: State, source: SourceStateExtension, repeats: int, concurrency: int):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        tasks = [loop.run_in_executor(pool, integrate_kinematic_open_loop, initial, source) for _ in range(repeats)]
        return await asyncio.gather(*tasks)


def summarize(name: str, runner, *, repeats: int, samples: int, expected_hash: str | None = None) -> dict[str, object]:
    timings = []
    output_hash = ""
    peak_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for _ in range(3):
        started = time.perf_counter()
        outputs = runner()
        timings.append(time.perf_counter() - started)
        last = outputs[-1]
        output_hash = hashlib.sha256(repr(tuple(asdict(state) for state in last.states)).encode()).hexdigest()
    peak_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "implementation": name,
        "samples": samples,
        "repeats": repeats,
        "median_wall_s": round(statistics.median(timings), 6),
        "min_wall_s": round(min(timings), 6),
        "max_wall_s": round(max(timings), 6),
        "peak_rss_high_water_kib": max(peak_before, peak_after),
        "output_sha256": output_hash,
        "parity_status": "match" if expected_hash is None or output_hash == expected_hash else "mismatch",
        "status": "completed",
        "scientific_role": "tier1_preview_engineering_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 2 or args.repeats < 1 or args.concurrency < 1:
        raise SystemExit("samples >= 2, repeats >= 1 and concurrency >= 1 are required")
    initial, source = make_case(args.samples)
    baseline = summarize("current-python", lambda: run_direct(initial, source, args.repeats), repeats=args.repeats, samples=args.samples)
    expected_hash = str(baseline["output_sha256"])
    results = [baseline,
        summarize("low-risk-cache", lambda: run_cached(initial, source, args.repeats), repeats=args.repeats, samples=args.samples, expected_hash=expected_hash),
        summarize("medium-risk-async-orchestration", lambda: asyncio.run(run_async(initial, source, args.repeats, args.concurrency)), repeats=args.repeats, samples=args.samples, expected_hash=expected_hash),
        {
            "implementation": "cpp-webgpu-async",
            "samples": args.samples,
            "repeats": args.repeats,
            "status": "unavailable",
            "reason": "no approved parity runner configured; native replay boundary preserved",
            "scientific_role": "preview-or-experimental-only",
        },
    ]
    payload = {
        "benchmark_version": "optimization-benchmark-v1",
        "requested_base_commit": os.environ.get("R2S_BENCHMARK_BASE", "a295648"),
        "actual_commit": _git_revision(),
        "workload": {"kind": "synthetic", "samples": args.samples, "repeats": args.repeats, "seed": 7},
        "dec_018": "browser/WASM and recorded display layers never feed native replay, replay.csv, ADE/FDE, gates or reports",
        "results": results,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


def _git_revision() -> str:
    try:
        return subprocess.check_output(("git", "rev-parse", "HEAD"), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
