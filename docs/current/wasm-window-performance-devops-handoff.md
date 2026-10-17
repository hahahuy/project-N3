# WASM/ViewPane Performance Handoff

Status: `IN PROGRESS — items 7 and 9 implemented and measured`
Scope: reduce browser/API CPU, memory, request fan-out and perceived lag for the
WASM, 3D, top-down, sensor-evidence and Real Camera windows.

Scientific boundary: browser/WASM remains preview-only. These changes must not
feed native esmini replay, `replay.csv`, ADE/FDE, gates or reports.

## Progress log

### Items 7 and 9 — implemented

`GroundService.full_layers` no longer rebuilds the map per process. It writes a
gzipped, versioned artifact to
`{PROJECT_N3_METADATA_CACHE}/map-cache/map-{dataset_version}-{map_name}-{transform_hash}-{signature}-full-map-v1.json.gz`,
written via a temp file and `os.replace`, guarded by a per-key lock, and read
through a four-entry in-process LRU. A dataset-signature or transform-hash
mismatch regenerates rather than reuses. Measured: extraction ~26s to 0.03s.

The static geometry is now served on its own at
`GET /api/workspace/scenarios/{id}/top-down-map` with an `ETag` and
`Cache-Control: private, max-age=3600`, and `top-down-state` takes
`include_map` (default `true`, so existing callers are unaffected). The
frontend fetches the map once per scenario and asks for slim state per
playhead. Measured in the browser: per-playhead state went from 1,764,266
bytes to 5,192 bytes, about 99.7 percent less.

Normalizing `full_layers` output also fixed a latent defect: the preview reads
`polygon.exterior` while `full_layers` emitted `geometry`, so the top-down map
had never actually drawn. The response now exposes `exterior`/`holes` and drops
the raw `geometry` ring to avoid shipping every coordinate twice.

### Blocking defect found and fixed

`top-down-state` returned 500 with `TypeError: string indices must be integers`
because it iterated the layer mapping as if it were a list of records. It paid
the full map cost and then failed. Fixed, with a regression test.

### Remaining bottleneck, not yet addressed

`NuScenesDatasetAdapter.recorded_annotations_window` takes roughly 25-40s and
dominates the cold top-down request. The map cache removed the other half.
This is the next thing to measure and is not covered by items 1-11 as written.

### Operational hazard observed

Both stacks run a single uvicorn worker with synchronous, CPU-bound nuScenes
devkit handlers. A burst of large preview requests can starve the event loop
until even `/api/health` times out and Docker marks the container unhealthy,
while individual requests still eventually succeed. Item 11 (bounded
concurrency) is the intended mitigation and should be treated as a stability
fix, not only a throughput one.

### Root cause of the dev 502s and OOM kills: duplicated devkit metadata

Measured 2026-10-17: a single `NuScenes(v1.0-trainval)` load holds **7.74GB**
resident. Three call sites each constructed their own object:

- `NuScenesDatasetAdapter.nusc` (was cached per adapter),
- `ArtifactAdapter._map_name`, which built an entire second devkit just to read
  one location string per scene,
- `real2scenario.devkit._load_nuscenes`, which had no cache at all.

That is roughly 23GB before any other allocation. Because dev runs
`--reload`, each save started a fresh worker that paid the cost again, and a
session reached a **28.7GB peak**. The kernel OOM-killed the worker, and
because `--reload` does not respawn a dead worker the container stayed `Up`
while nothing listened on 8000: the Vite proxy answered **502** and Docker
marked the api unhealthy while the product stack shared the same 32GB host.

All three now share one process-wide instance via
`r2s_web.nuscenes_adapter.shared_nuscenes`. Verified in both stacks: after
exercising the scenario-detail, camera-evidence, top-down-state and top-down-map
paths, resident memory is flat at ~7.6GB with a single metadata object.

Both stacks are now bounded at 12G / 4 CPUs. Unbounded dev was a
host-availability hazard rather than a dev annoyance. Note the baseline cost:
7.74GB of the 12G budget is the metadata object, so the remaining headroom is
about 4GB and is worth watching during recorded-annotation work.

## Current Hotspots

### Frontend

- `frontend/src/App.tsx` owns one global playhead, but `RealCameraView` and
  `TopDownView` currently fetch on every playhead change. Dragging the timeline
  can produce one request per slider event per open pane.
- Each embedded `WasmPlaybackView` creates its own Worker and each
  `ThreePlaybackCanvas` creates its own WebGL renderer, scene, grid, lights and
  animation loop. Opening third-person and sensor-evidence therefore duplicates
  WASM state and GPU resources.
- `WasmPlaybackView` prefetches every listed LIDAR sweep at full density
  (`decimation=1`) and keeps decoded `Float32Array` clouds in an unbounded
  per-component Map. This is the largest browser memory risk.
- Controlled `seek` resets the WASM scenario and steps from time zero to the
  requested time. Large timeline jumps are O(target time / fixed dt), and two
  panes can issue the same seek independently.
- `ThreePlaybackCanvas` renders continuously with `requestAnimationFrame`, even
  when the pane is hidden, backgrounded or unchanged. It also maintains a full
  renderer per pane.
- Real Camera currently overlays projected LiDAR points and recorded cuboids
  as SVG elements. A dense point cloud can create thousands of DOM/SVG nodes.
- Top-down full-map geometry is returned as JSON and rendered in SVG. The
  current full-map cache is process-local in `GroundService`, so multiple API
  workers duplicate memory and a restart rebuilds it.

### Backend

- `NuScenesDatasetAdapter` correctly caches the `NuScenes` object per process,
  but camera/LiDAR projection still reads and transforms point clouds per
  request.
- `GroundService._full_cache` is an in-memory cache keyed by map and local
  transform. It has no byte bound, persistent artifact, TTL or cross-worker
  sharing.
- Camera evidence requests can return thousands of projected LiDAR points and
  full annotation payloads for every playhead change.
- LIDAR payloads are binary, but there is no server-side response cache header
  keyed by sample token/decimation and no bounded decoded-cloud cache.
- `compose.dev.yml` already persists the metadata SQLite cache at
  `/var/cache/real2scenario`, but no explicit CPU/memory budget or request
  concurrency policy is configured for expensive map/projection work.
- `docs/guides/datastreaming.md` recommends persistent metadata cache, SQLite
  reuse, startup readiness and avoiding repeated metadata rebuilds. Preserve
  that design; do not replace SQLite with a new database for this task.

## P0: Prevent Browser Resource Spikes

### 1. Make WAW runtime shared per scenario

Create an App-level `WasmPlaybackRuntime`/context keyed by `scenario_id`:

- one Worker per scenario, not one Worker per pane;
- one authoritative frame/playhead state;
- one XOSC/XODR load and one ground/path/sweep index load;
- panes subscribe to frames and render their own view only;
- sensor-evidence may use the same runtime but must keep its LiDAR visibility
  policy separate from third-person.

The two panes can still have separate orbit cameras, but must not duplicate the
simulation Worker or decoded source data.

Acceptance:

- opening both WAW panes creates exactly one Worker and one `init` request;
- changing playhead sends one seek request to the shared runtime;
- closing one pane does not dispose the runtime while another pane is mounted;
- runtime disposes when the last subscriber closes or scenario changes.

### 2. Replace O(t) seek with checkpoints

Keep `FIXED_DT=0.01` and `ENGINE_PRIME_DT=0` unchanged. Add Worker checkpoints:

- capture a lightweight checkpoint every configurable interval, initially 1 s;
- seek from the nearest checkpoint at or before target time;
- cap catch-up steps per message and coalesce newer seek requests;
- never process stale queued seeks after a newer playhead arrives.

Do not change motion/timing semantics. Checkpointing is an execution optimization
for the same WASM state, not a new trajectory source.

Acceptance:

- a 10 s seek does not replay from zero when a checkpoint exists;
- rapid slider movement results in only the newest pending seek being rendered;
- existing worker prime/reset/fixed-step tests remain unchanged and pass.

### 3. Bound LIDAR prefetch and decoded memory

- Default browser preview fetch should use a bounded decimation such as 4x or 8x;
  keep 1x as an explicit audit/high-detail mode.
- Fetch only the current sweep plus a small look-ahead/look-behind window, not
  every sweep in the scene.
- Use an LRU cache by `sample_data_token + decimation`, with a byte/entry cap.
- Evict decoded `Float32Array` buffers when the cap is reached.
- Cancel in-flight fetches on scenario change, mode change or playhead jump.
- Expose cache status in debug/provenance UI, not as scientific evidence.

Acceptance:

- memory remains bounded during a 20 s scene review;
- no more than N configured sweep payloads are retained per scenario;
- third-person never fetches LiDAR when its visibility is suppressed.

## P1: Reduce Request and Render Churn

### 4. Debounce time-addressed evidence requests

For camera and top-down:

- debounce playhead requests by 100-150 ms while the range input is dragged;
- immediately request on release/step button;
- abort the previous request with `AbortController`;
- ignore stale responses using request sequence IDs;
- optionally quantize sensor requests to the nearest recorded sample timestamp.

The displayed actor/playhead UI may remain smooth locally; only evidence payload
requests should be throttled.

### 5. Use canvas for dense camera overlays

Keep the recorded image as an `<img>` layer and draw LiDAR/cuboid overlays on a
single `<canvas>` positioned above it. Do not create one SVG DOM node per point.

- cap rendered LiDAR points by deterministic stride or pixel occupancy;
- keep the full projected count in metadata;
- draw recorded boxes from devkit `corners_2d`;
- keep canonical and recorded layers independently togglable;
- use `devicePixelRatio` cap of 1-2 for overlay canvas.

### 6. Pause inactive renderers

- Use `IntersectionObserver`/visibility state to pause Three.js animation loops
  when a pane is hidden, minimized or outside the viewport.
- Render one frame after data/props change when orbit is idle instead of running
  a permanent RAF loop where possible.
- Dispose renderer, geometries, materials and textures on pane/runtime cleanup.
- Keep shared Worker alive only while at least one subscriber exists.

## P1: Backend Cache and Streaming

### 7. Persist full-map geometry as a versioned artifact — DONE

Replace unbounded process-local-only map reuse with a cache artifact under the
configured output/cache root:

```text
map-cache/
  {dataset_version}-{map_name}-{transform_hash}-full-map-v1.json.gz
```

Recommended payload:

- map name and transform provenance;
- layer name;
- compressed coordinate arrays;
- bounds and geometry counts;
- contract version;
- source dataset signature.

Use atomic write and a lock. Keep a small process-local LRU for hot maps. Do not
cache per-playhead actor data in the static map artifact.

Acceptance:

- first request builds one artifact;
- concurrent requests do not write partial files;
- subsequent API/container restarts reuse the artifact when dataset signature
  and transform hash match;
- stale artifacts are regenerated, never silently reused.

### 8. Add HTTP cache validators

For immutable/private display artifacts:

- `ETag` based on token/decimation/version/hash;
- `Last-Modified` where useful;
- `Cache-Control: private, max-age=...` for local browser use;
- `304 Not Modified` support if the framework path permits it.

Suggested keys:

- LIDAR: sample-data token + decimation + payload contract version;
- camera image: sample-data token;
- full map: map name + transform hash + dataset signature;
- camera projection: camera token + matching LiDAR token + projection version.

Never cache a variant as if it were a generated sensor frame. Preserve parent
recorded-evidence labeling and DEC-018 provenance.

### 9. Separate static and dynamic payloads — DONE

Avoid returning full map geometry and all actor annotations on every playhead
request. Prefer:

```text
GET /top-down-map/{scenario_id-or-transform-hash}
GET /top-down-state/{scenario_id}?time_s=...
GET /camera-evidence?...&time_s=...
```

The static map response is cached; the state response contains only the nearest
recorded annotation sample and actor overlays.

## P2: Deployment/Operations

### 10. Keep current persistent cache wiring

Do not remove these existing compose settings:

- `PROJECT_N3_METADATA_CACHE=/var/cache/real2scenario`
- named volume `project-n3-metadata-cache`
- read-only `/mnt/backup/nuscenes` mount

Add operational visibility:

- `/api/health` fields for metadata index readiness;
- map-cache hit/miss/build time and byte size;
- camera/LiDAR projection latency and cache hit rate;
- current decoded-cloud count/bytes;
- Worker/runtime count exposed only in local debug diagnostics.

### 11. Add bounded concurrency

Expensive operations should use a small executor/semaphore:

- max one full-map build per map/transform key;
- max one camera LiDAR projection per scenario/channel/sample at a time;
- queued duplicate requests coalesce;
- return explicit `busy`/`unavailable` status rather than spawning unlimited
  `NuScenes`/point-cloud work.

Do not add a background queue for normal timeline interaction unless profiling
shows it is necessary; request coalescing and bounded caches are sufficient for
the local single-user product.

## Observability Targets

DevOps should measure before/after:

- first scene selection latency;
- playhead drag request count per second;
- camera evidence p50/p95 latency;
- top-down state p50/p95 latency;
- LiDAR payload bytes and decoded bytes retained;
- browser main-thread frame time;
- WebGL renderer count and Worker count;
- API RSS and container memory peak;
- full-map build time and artifact size.

Suggested local thresholds after optimization:

- one Worker per active scenario;
- one WebGL renderer per visible 3D pane, zero for hidden panes;
- no unbounded LiDAR prefetch;
- no more than one camera/top-down request per 100 ms during drag;
- static full-map cache hit after first successful build;
- no increase in native replay or metric workload.

## Non-Goals / Guardrails

- Do not change actor selection, motion, timing, triggers or canonical replay
  population.
- Do not use browser/WASM output for ADE/FDE, `replay.csv`, gates or reports.
- Do not replace SQLite metadata indexing with Postgres or a remote database.
- Do not bake overlays into camera images when a separate overlay payload is
  sufficient.
- Do not ship full raw nuScenes point clouds to the browser when decimated,
  viewport-relevant points provide the same inspection result.

## Files to Touch

- Frontend runtime/cache: `frontend/src/wasm-playback/WasmPlaybackView.tsx`,
  `worker.ts`, `ThreePlaybackCanvas.tsx`, `App.tsx`, `api.ts`.
- Backend cache/projection: `src/r2s_web/ground.py`,
  `nuscenes_adapter.py`, `camera.py`, `lidar.py`, `app.py`.
- Deployment: `compose.dev.yml`, optional production compose/Dockerfile only
  if the same cache/resource settings are needed there.
- Tests: focused frontend worker/runtime tests, API cache/ETag tests,
  projection/map cache tests, and a resource-bounded smoke test.

## Definition Of Done

- Both WAW panes share one Worker/runtime per scenario.
- Camera/top-down requests are debounced, abortable and stale-response safe.
- LiDAR decoded memory and prefetch are bounded.
- Full-map geometry survives API restart through a versioned compressed cache.
- Camera overlay uses one canvas, not thousands of SVG point nodes.
- Hidden panes pause rendering and dispose correctly.
- Metrics/replay/gates/reports remain byte-for-byte behaviorally isolated.
- Existing Python and frontend test suites pass, plus new performance contract
  tests and a documented before/after profile.
