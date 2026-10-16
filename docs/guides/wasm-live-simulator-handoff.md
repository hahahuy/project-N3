# Handoff — Browser-Local WASM Scenario Simulator

**Status:** PROPOSAL — implementation handoff
**Authority:** DEC-017 in `docs/current/decisions.md`
**Scope:** interactive preview and authoring. **Not** measurement.

---

## 1. Read this first

This supersedes the earlier WebAssembly deferral in the Live Esmini Adapter
Contract. Two runtimes now exist and they are not interchangeable:

| | Native adapter (unchanged) | WASM runtime (this handoff) |
|---|---|---|
| Contract | `esmini-live-session-v1` | `esmini-wasm-session-v1` (proposed) |
| Module | `src/r2s_web/live_session.py` | `frontend/src/sim/` |
| Role | authoritative stepping | interactive preview |
| State precision | `double` | **`float32` at the WASM boundary** |
| Produces ADE/FDE? | **yes, Tier 0** | **no, ever** |
| Blocked by | missing native library in this environment | nothing |

Two facts from the current tree shape this work.

**The native path is already partly blocked.** `docs/current/project-status.md`
records the live session as `IMPLEMENTED PARTIAL`, and
`CtypesEsminiBinding.control()` in `src/r2s_web/live_session.py` raises
`RuntimeError("esminiLib_control_abi_unavailable")`. Interaction is blocked on
environment, not on design. The WASM runtime removes that dependency.

**Tier 1 already exists.** `src/real2scenario/kinematic.py` implements
`kinematic-open-loop-v1` with `KinematicLimits`, `KinematicViolation` and
`check_footprint_collisions`. It is `IMPLEMENTED/TESTED/DIAGNOSTIC` in
`docs/current/active-work.md`. There is no empty slot to fill and nothing in the
simulation engine to remove.

---

## 2. What to change

### 2.1 Backend

Nothing. This is deliberate and it is the point.

`/api/scenarios/{id}/artifacts` already returns artifact links including the
generated `.xosc` and `.xodr`. The browser fetches both, mounts them into the
Emscripten filesystem and runs. No new endpoint, no session registry, no
`MAX_SESSIONS` cap.

Do **not** remove `src/r2s_web/live_session.py`. It is the authoritative path
when a native binding exists, and it is the only one that may measure.

### 2.2 Frontend

The frontend has no 3D dependency today. `frontend/package.json` lists
`@vitejs/plugin-react`, `jsdom`, `react`, `react-dom`, `typescript`, `vite`,
`vitest`, plus dev deps `@testing-library/*`, `@types/*`, `react-grab`. No
`three`, no `@react-three/fiber`.

`frontend/src/App.tsx` is 1019 lines. Its `ViewType` is
`"top-down" | "third-person" | "in-car" | "lidar" | "sensor-evidence"`
(line 63), and `third-person` is described in the add-view menu as
`"esmini runner render, main pane"`. That is the browser-native render path the
contract already describes, currently served by state and SVG rather than WebGL.

So the change is **replacing the presentation layer of an existing view type**,
not adding a view type. `top-down`, `sensor-evidence`, `lidar` and the authoring
surface are untouched.

Suggested layout:

```
frontend/src/sim/
├── esminiModule.ts       # lazy singleton: await createEsminiModule()
├── wasmSession.ts        # worker-facing session, replay + action log
├── simWorker.ts          # owns the WASM instance, runs the fixed-step loop
├── protocol.ts           # message types
└── contract.ts           # esmini-wasm-session-v1 constants

frontend/src/three/
├── Scenario3DCanvas.tsx  # r3f <Canvas> host
├── RoadMesh.tsx          # lane surfaces from get_road_geometry()
├── ActorBoxes.tsx        # actor boxes, labels, picking
├── Trails.tsx
└── cameras.ts            # third-person / in-car / orbit presets
```

### 2.3 Toolchain changes

`vite.config.ts`:

```ts
import topLevelAwait from 'vite-plugin-top-level-await'

plugins: [react(), topLevelAwait()],
optimizeDeps: { exclude: ['three', '@react-three/fiber'] },
assetsInclude: ['**/*.wasm'],
```

`assetsInclude` is required — Vite will not treat `.wasm` as an asset without it.
`vite-plugin-top-level-await` is required because Emscripten's `MODULARIZE` output
uses top-level await.

---

## 3. Build

The upstream repo is not vendored. Clone beside the project, not inside `src/`.

```
git clone --depth 1 --branch v3.10.0 https://github.com/esmini/esmini
cd esmini && git submodule update --init --depth 1 externals/fmt
```

`externals/fmt` is mandatory; the WASM build script patches it for the Emscripten
sysroot. Emscripten SDK **6.0.10** is the tested version per the upstream
`esminiJS/README.md`. Host prerequisites: `cmake`, `ninja-build`, `patch`,
`bzip2`.

### 3.1 The deviation you must make

The stock `build.sh` in the upstream `esminiJS` directory produces a **classic
script** and copies it into the upstream `example/` folder. That output cannot be
imported by Vite, and the upstream `example/viewer.js` resolves bare specifiers
through a CDN importmap. Neither is acceptable here.

Configure with `-sMODULARIZE=1 -sEXPORT_ES6=1 -sEXPORT_NAME=createEsminiModule`
and `-sENVIRONMENT=web,worker`. Keep the `-sFMT_OVERRIDE_INCLUDE_DIR` patch step
from the stock script.

Commit the artifacts under `frontend/wasm-esmini/` — not under `dist/`, which is
gitignored in both `.gitignore` and `.dockerignore`:

```
frontend/wasm-esmini/
├── build.sh
├── esminiJS/             # upstream sources + any local patch
├── esmini.js             # generated, committed
├── esmini.wasm           # generated, committed
└── BUILD.md              # esmini commit SHA + emsdk version
```

`BUILD.md` is not optional. Without it the binary is an unexplained blob to
`scripts/verify_release.py`.

### 3.2 Why the artifact is committed

The runtime image is `python:3.11-slim`; it has no Emscripten toolchain, so it
cannot build the artifact. CI cannot either without a ~1 GB emsdk install. The
artifact is a build input, like a vendored binary.

---

## 4. Worker, not main thread

Scrubbing a scenario at high speed will freeze the tab if the engine runs on the
main thread.

Use a plain Worker with `postMessage`. Do **not** use `SharedArrayBuffer`: that
requires `Cross-Origin-Opener-Policy` and `Cross-Origin-Embedder-Policy` headers
set in two places — `vite.config.ts` `server.headers` for dev, and a FastAPI
middleware for production. Missing one causes a silent dev/prod divergence. The
esmini WASM build is single-threaded anyway, so there is no compute argument for
SAB. Copying a few dozen object states per frame is not a bottleneck.

Protocol:

```ts
// main -> worker
{ type: 'init', xoscName, xodrName, files: Record<string, ArrayBuffer>, dt }
{ type: 'step', dt }
{ type: 'seek', t }
{ type: 'injectSpeed', targetId, mps, shape, dim, value }
{ type: 'injectLaneChange', targetId, mode, target, shape, dim, value }
{ type: 'setParameter', name, value }
{ type: 'reset' }
// worker -> main
{ type: 'ready', road: ScenarioRoadGeometry }
{ type: 'frame', frame: ScenarioFrame }
{ type: 'error', message }
```

`seek` is `reset()` plus N fixed steps. The engine is deterministic under a fixed
seed and timestep; do not attempt incremental seek.

---

## 5. Files must be mounted into the Emscripten filesystem

The engine reads from an in-memory filesystem, not from URLs. The Worker receives
the `.xosc` and `.xodr` as `ArrayBuffer`, writes them with `FS.writeFile`, then
constructs the scenario. Both files are required.

The current map is a template approximation: `src/real2scenario/templates/straight-two-lane-v1.xodr`
is a 1000 m straight two-lane road with no curves, no junctions and no elevation
profile, and artifact links carry a `map_warning`. The 3D view will render a flat
ribbon. That is correct. `ui-mvp-flow-spec.md` line 45 requires that 3D render
only pipeline-produced data with no decorative reality — surface the
`map_warning`, do not hide it.

---

## 6. Engine surface is minimal today

`embind.cpp` in the upstream `esminiJS` directory is the only file that decides
what JavaScript can call. It is a pure registration table, no logic.

Currently registered on `OpenScenario`: `step`, `step_frame`, `reset`,
`get_object_count`, `get_object_states`, `get_object_state_by_index`,
`get_road_geometry`, `get_simulation_time`, `is_quit`, `get_object_state`,
`get_object_state_by_second`, `time_to_collision`.

That is playback only. There is no way to change behaviour. Adding that is
specified in `docs/guides/interactive-object-selection-analysis.md`.

---

## 7. Deployment requirements

1. **`.wasm` MIME.** `create_app()` in `src/r2s_web/app.py` mounts
   `StaticFiles(directory=frontend_dist, html=True)` at `/`. The runtime image is
   `python:3.11-slim`, where `.wasm` MIME registration is not guaranteed. Add near
   the top of `create_app()`:

   ```python
   import mimetypes
   mimetypes.add_type("application/wasm", ".wasm")
   ```

2. **No SPA fallback.** `StaticFiles(html=True)` has no catch-all route. Irrelevant
   here because the view is routed inside the existing React app, not a standalone
   page.

3. **Dev vs prod staleness.** In `compose.dev.yml` the API container bind-mounts
   the repo, so the static mount serves whatever `frontend/dist` the host last
   built. After changing the WASM artifact, run `npm run build` locally. Vite dev
   picks changes up live.

4. **Release verification.** `scripts/verify_release.py` scans the committed tree
   for binary patterns and hashes manifests. The `.wasm` artifact will be picked
   up. Add it to the allowlist with an explicit comment or CP5 verification fails.

5. **Attribution.** esmini is MPL-2.0, three.js and `@react-three/fiber` are MIT,
   Emscripten is its own licence. All are compatible with this repository's
   Apache-2.0 code licence. Add all of them to `NOTICE`.

6. **Data licence is unchanged.** Rendered `.xodr`, `.xosc` and trajectories remain
   derived from nuScenes and stay local-only, non-commercial.

---

## 8. Sequence

| Phase | Work | Done when |
|---|---|---|
| **P0** | Build upstream `esminiJS` as an ES module; load in a bare page; confirm `step_frame` and `get_road_geometry` | a running loop, screenshot saved, exact build command recorded in `BUILD.md` |
| **P1** | Add pinned `three`, `@react-three/fiber`, `vite-plugin-top-level-await`; wire `vite.config.ts`; pin existing `"latest"` deps | `npm ci` twice resolves an identical tree |
| **P2** | `Scenario3DCanvas` replacing the current `third-person` presentation layer: road mesh, actor boxes, cameras, timeline | the existing third-person view renders the road instead of a flat projection |
| **P3** | Picking and the `embind.cpp` extensions | injecting a speed change on a clicked actor visibly alters later frames |
| **P4** | Action log, replay-on-seek, boundary enforcement | scrubbing back reproduces the exact run including user interventions |

Do not start P2 before P0 passes. P0 is the only phase that can invalidate the rest.

---

## 9. Non-negotiable boundary

**The WASM runtime may not produce measurement.**

Object state crosses the WASM boundary as `float32` — `esminijs.hpp` declares
`float` for `x`, `y`, `z`, `h`, `p`, `r`, `s`, `speed` and the rest. At road-scale
coordinates that is roughly 0.1 mm resolution, which is fine for rendering and not
fine for metrics that are compared in centimetres.

Therefore:

- ADE/FDE, gates G1-G7 and every fidelity claim continue to come only from
  `src/real2scenario/simulation.py` via the native Tier 0 path.
- WASM and native runs must be distinguishable by filename, trace contract id and
  UI label. They must never share a trace file.
- The 3D surface must state that it is a kinematic preview, not a dynamics
  prediction. esmini integrates a **kinematic** bicycle model — see
  `EnvironmentSimulator/Modules/Controllers/vehicle.cpp` in the upstream tree,
  where the comment reads *"Calculate vehicle kinematics according to simple
  bicycle model"*, with `speed += max_acc * throttle * dt` and no tyre, suspension
  or rigid-body model. `--vehicle_dynamics` is presentation only.

Enforce this with a test, not a comment: assert that no module reachable from
`metrics.py` imports from `frontend/src/sim/`, and that browser-side runs write to
a distinct trace prefix.