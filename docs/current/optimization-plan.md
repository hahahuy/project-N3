# Project - N3 Optimization Plan

Status: `PHASE 2 COMPLETE / PHASE 3 EXPERIMENTAL BOUNDARY`
Base commit: `a295648`
Worktree: `optimize/project-n3-phased`

## Binding guardrails

- DEC-018 is unchanged: browser/WASM and recorded display layers are preview/evidence only.
- They must never feed native replay, `replay.csv`, ADE/FDE, gates, reports or acceptance claims.
- Native esmini remains the only sanctioned replay metric source.
- Canonical scenario, actor selection, timestamps, transforms, exporter semantics and fixed timesteps are immutable during optimization unless a separately approved decision is added.
- Raw and derived nuScenes artifacts remain local/private.

## Three phases

### Phase 1: low risk

Completed frontend display/runtime optimizations: abortable fetches, 75 ms seek coalescing, non-mutating cache inspection, and shared runtime source mismatch protection. Existing behavior and output parity are protected by tests.

### Phase 2: medium risk

Implemented bounded batch orchestration with configurable worker/pending limits, fast `429 batch_limit_reached` rejection, truthful background `202` responses and settings visibility. No backend semantic recorded-evidence cache was promoted without private-data parity evidence.

### Phase 3: experimental acceleration

The bounded executor is measured as orchestration, separately from the synchronous Python kernel. C++/WebGPU is not promoted: no approved parity runner exists, and browser/WASM remains display-only under DEC-018. The harness records this as `unavailable` rather than inventing a speedup.

## Benchmark matrix

| Column | Meaning | Scientific role |
|---|---|---|
| 1 | Current Python | Baseline implementation |
| 2 | Low-risk | Same Python semantics with bounded cache/coalescing |
| 3 | Medium-risk | Bounded async orchestration candidate |
| 4 | C++/WebGPU/async | Experimental acceleration; not authoritative replay |

## Execution log

| Time | Phase | Action | Result | Artifact |
|---|---|---|---|---|
| 2026-10-18 | baseline | docs consistency | PASS | terminal output |
| 2026-10-18 | baseline | Python tests | 397 passed | terminal output |
| 2026-10-18 | baseline | frontend tests | 71 passed | terminal output |
| 2026-10-18 | baseline | frontend build | PASS; chunk warning only | terminal output |
| 2026-10-18 | setup | created optimization worktree from `a295648` | PASS | `../project-N3-optimize` |
| 2026-10-18 | phase 1 | frontend seek coalescing, abort signals, cache peek and runtime source guard | 74 frontend tests + build PASS | frontend source/tests |
| 2026-10-18 | benchmark | synthetic 512 samples x 20 repeats | parity stable; current 0.047797s, cache 0.002392s, async 0.036179s, C++/WebGPU unavailable; RSS high-water explicitly labelled | `scripts/benchmark_optimization.py` |
| 2026-10-18 | verification | full post-change suites | docs PASS; Python 398 passed/1 skipped; frontend 74 passed/build PASS | terminal output |
| 2026-10-18 | benchmark | synthetic 2048 samples x 20 repeats | parity stable; current 0.172190s, cache 0.017448s, async 0.242004s, C++/WebGPU unavailable | `docs/current/optimization-benchmark.md` |
| 2026-10-18 | phase 2 | bounded batch executor, settings contract and admission test | Python 399 passed; excess request rejected with `429 batch_limit_reached` | `src/r2s_web/jobs.py`, `tests/test_web_api.py` |
| 2026-10-18 | phase 3 | service admission benchmark | accepted/running/completed/rejected timings recorded; no replay metrics involved | `scripts/benchmark_batch_admission.py` |

## Final disposition

Phase 1 and Phase 2 are implemented and verified on synthetic/local test workloads. The default production-safe admission policy is one worker plus one pending slot; it is configurable and remains an engineering default, not an owner-approved host-capacity claim. Phase 3 remains experimental/unavailable for C++/WebGPU and shows async overhead on the CPU-bound synthetic kernel. Native replay and its scientific baseline are untouched.
