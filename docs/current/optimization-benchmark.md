# Project - N3 Optimization Benchmark

Status: `PHASE 2 COMPLETE / PHASE 3 EXPERIMENTAL BOUNDARY`

This report compares engineering execution only. It is not ADE/FDE evidence, map-accuracy evidence or safety/TTC evidence. Browser/WASM and recorded display layers are excluded from native replay, `replay.csv`, ADE/FDE, gates and reports by DEC-018.

## Protocol

- Run from the optimization worktree.
- Record commit, Python/Node versions, workload, seed, environment and whether data is synthetic or local-private.
- Repeat each case three times where practical; report median and range.
- Compare status, output hash, counts and reasons before comparing speed.
- Do not include raw nuScenes artifacts or absolute dataset paths in committed reports.

## Current baseline

The repository baseline at `a295648` passed docs consistency, 397 Python tests, 71 frontend tests and the frontend production build. A runnable synthetic performance harness is now available so all four comparison columns use the same cases.

## Synthetic result: 512 samples, 20 repeats, seed 7

| Implementation | Median wall time | Min-max wall time | Peak RSS delta | Status |
|---|---:|---:|---:|---|
| Current Python | 0.047797 s | 0.037838-0.050447 s | 728,764 KiB high-water mark | completed/parity match |
| Low-risk cache | 0.002392 s | 0.002358-0.002441 s | 728,764 KiB high-water mark | completed/parity match |
| Medium-risk async orchestration | 0.036179 s | 0.031695-0.036457 s | 728,764 KiB high-water mark | completed/parity match |
| C++/WebGPU/async | n/a | n/a | n/a | unavailable: no approved parity runner |

All completed implementations produced the same output SHA-256 prefix `189b407c...3c7595`. The harness now records the actual Git revision and parity status; RSS is explicitly a process high-water mark, not a per-implementation delta.

## Synthetic result: 2048 samples, 20 repeats, seed 7

| Implementation | Median wall time | Min-max wall time | Peak RSS delta | Status |
|---|---:|---:|---:|---|
| Current Python | 0.172190 s | 0.154925-0.198610 s | 780,880 KiB high-water mark | completed/parity match |
| Low-risk cache | 0.017448 s | 0.017089-0.018665 s | 780,880 KiB high-water mark | completed/parity match |
| Medium-risk async orchestration | 0.242004 s | 0.160108-0.275360 s | 780,880 KiB high-water mark | completed/parity match |
| C++/WebGPU/async | n/a | n/a | n/a | unavailable: no approved parity runner |

All completed implementations produced the same output SHA-256 prefix `d384c75e...8bfd0`. The run used the actual source checkout with `PYTHONPATH` pinned to this worktree.

The cache result is a cache-hit engineering measurement, not a claim that the first computation became faster. The async result is orchestration-only and is slower for these CPU-bound workloads; a larger genuinely concurrent service workload is required before considering bounded async execution. No browser/WASM output or recorded display payload entered this benchmark's replay/metric/report path.

## Local-private benchmark status

No private nuScenes payload was written to the repository. Cold metadata, map, LiDAR and camera measurements remain pending because they require a controlled private-data runtime and must record RSS/latency without publishing raw or derived artifacts.

## Batch admission result

`scripts/benchmark_batch_admission.py` exercises a synthetic batch with one worker, one pending slot and zero acceptance grace. The first request is admitted and returns `202` while work is running; the second request is rejected immediately with `429 batch_limit_reached`; completion is observed through the status endpoint. This measures HTTP orchestration only. It does not invoke native replay metrics and does not produce scientific evidence.

The configured defaults are deliberately conservative: `R2S_BATCH_MAX_WORKERS=1`, `R2S_BATCH_MAX_PENDING=1`, and `R2S_BATCH_ACCEPT_GRACE_S=0.05`. These values are not a claim about the host's final capacity; the existing non-interference mission still requires a private multi-service load run before increasing them.

Measured synthetic admission run with `max_workers=1`, `max_pending=1`, `accept_grace_s=0`:

| Measurement | Result |
|---|---:|
| First request response | `202`, status `running` |
| Second request response | `202`, admitted to the one-slot pending capacity |
| Third request response | `429`, reason `batch_limit_reached` |
| Time to accept first request | `0.019176 s` |
| Time to observe completion | `0.029546 s` |

This is an in-process synthetic benchmark. It does not establish the final safe cap for the production host or non-interference with other services.
