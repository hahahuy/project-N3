# Optimization Main-vs-Branch Benchmark

Date: `2026-10-18`
Scope: engineering/runtime comparison only; not scientific replay evidence.

## Runtimes

| Runtime | Source | Endpoint | Artifact state |
|---|---|---|---|
| Canonical dev | existing `main` checkout/container | `:8001` | 84 scenarios, existing dev artifacts |
| Detached main baseline | commit `3f216bd` | `:18001` | detached benchmark volume; one imported scene during the run |
| Optimization branch | `optimize/project-n3-phased` | `:18002` | detached optimization volumes; one imported scene during the run |
| Public production | `https://project-n3.hahuy.cloud` | gateway | not authenticated in this run; application payload unverified |

Production was not restarted or modified. Public production requests remained behind the configured Basic Auth boundary.

## API parity

The detached main and optimization API OpenAPI documents matched:

```text
b663a6999b97fbf24aa89d1666e762ed13567d3570d6c6b32dd3356235a91dbc
```

Both stacks reported `850` source scenes. The detached main artifact root was initially empty; the same `scene-0001` source scene was imported into both isolated benchmark volumes before scenario-level comparison.

## Native C++ parity

Workload: synthetic Tier 1 kinematic input, `512` source samples, fixed timestep `0.05 s`.

| Metric | Result |
|---|---:|
| Python state rows | 512 |
| C++ state rows | 512 |
| Maximum absolute error | `0.0` |
| Parity status | `match` |
| Scientific role | `tier1_preview_engineering_only` |

This is Python Tier 1 versus native C++ Tier 1 parity. It is not native esmini parity and does not produce replay evidence.

## Native C++ scale smoke

Measured standalone CLI wall time on the same host/toolchain. Each case includes process startup and text I/O.

| Samples | Output rows | Wall time |
|---:|---:|---:|
| 128 | 128 | `0.002413 s` |
| 512 | 512 | `0.002541 s` |
| 2048 | 2048 | `0.008834 s` |
| 4096 | 4096 | `0.014678 s` |

These numbers are not browser frame times, GPU timings or production API latency.

## Warm API smoke

After the heavy dataset workload completed, the optimization API remained healthy with approximately `6.2 GiB` resident memory. Repeated warm `/api/health` calls on the optimization API were approximately `2-3 ms` locally. The canonical dev API was also healthy, but its process/resource state is separate and not a clean production baseline.

The optimization API settings reported:

```text
dataset_version: v1.0-trainval
source_scene_count: 850
batch_max_workers: 1
batch_max_pending: 1
artifact_root_exists: true
dataset_root_exists: true
```

## Browser C++/WASM/WebGPU smoke

Optimization frontend endpoint: `http://127.0.0.1:15182/cpp-wasm`.

Observed:

- C++ WASM Worker status: `available`.
- `navigator.gpu`: exposed by the browser.
- WebGPU adapter: unavailable (`No available adapters`).
- Renderer: SVG fallback.
- Browser console errors: none.
- DEC-018 isolation text visible.

The browser did not provide an adapter, so no active WebGPU performance number is claimed. SVG fallback is the expected safe behavior.

## Limitations

- Production authenticated API/catalog/live-session measurements were not available because the Basic Auth credential was not present in this session.
- The detached main and optimization volumes were not identical before import; both received the same `scene-0001` import for the scenario smoke, but artifact catalog size is not a full production comparison.
- No multi-actor browser frame benchmark, multi-pane benchmark, GPU memory benchmark or authenticated production load test was completed in this run.
- The optimization API retains the large nuScenes metadata object; bounded batch admission limits work admission but does not eliminate the dataset memory footprint.

## Workload stability result

After the heavy dataset workload, the detached `main` API container reported:

```text
status=running
health=unhealthy
oom=true
exit=0
```

The optimization API container reported:

```text
status=running
health=healthy
oom=false
exit=0
```

Observed Docker memory after the run was approximately `14.9 MiB` for the
unhealthy main container and `6.2 GiB` for the healthy optimization container;
the main process had already been OOM-killed/restarted or was no longer serving
the workload. This is operational evidence that the optimization branch's
bounded/lifecycle changes avoided the observed failure mode in this run. It is
not a complete capacity guarantee or authenticated production benchmark.

## DEC-018

Browser/WASM/WebGPU output remained preview-only. No browser output, recorded display layer or C++ preview output entered native replay, `replay.csv`, ADE/FDE, gates or scientific reports.
