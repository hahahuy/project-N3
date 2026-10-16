# Handoff — Interactive 3D Scenario Simulator (esmini-WASM)

**Status:** PROPOSAL — implementation handoff for a specialised agent
**Scope:** U5 / Tier 1 slot. Does **not** change Tier 0 measurement.
**Author context:** prepared after an audit of this repository and of the upstream
`esmini` source tree (v3.10.0, `EnvironmentSimulator/Libraries/esminiJS`).

---

## 1. Read this first

This document tells you what to **delete**, what to **replace**, and **why**, then
gives the build and wiring sequence. It is written so that an agent who has never
seen this codebase can execute it without re-deriving the analysis.

Three facts frame everything below:

1. **`kinematic-open-loop-v1` (Tier 1) has not been implemented.** There is no
   module named `open_loop` or `kinematic` under `src/`. The only trace of the
   contract is threshold names in `src/real2scenario/validation.py`. So this work
   lands in an **empty slot** — there is no Tier 1 engine to tear down.
2. **The behaviour executor is an explicit, intentional stub.**
   `PreviewService.preview()` in `src/r2s_web/jobs.py` returns
   `status="unsupported"` with `reason="behavior executor is not implemented"`
   when `request.behavior == "behavior"`. That stub is the designed seam this
   work fills.
3. **The 3D view is an explicit, intentional placeholder.** `docs/current/ui-mvp-flow-spec.md`
   line 117 defines `U5 | 3rd-person POV, xodr map layer, 3D actor boxes`, and the
   frontend currently renders `not in this build - 3D foundation is U5`.

So the "what do I break" question has a smaller answer than expected. Most of the
demolition is frontend chrome and hygiene, not engine code.

---

## 2. What this replaces, and with what

The engine being added is **esmini compiled to WebAssembly** (upstream calls it
`esminiJS`), driven from the browser with a WebGL renderer. This replaces the
*unbuilt* Tier 1 placeholder with a real OpenSCENARIO 1.x engine, and it replaces
the static top-down SVG plot with a live 3D scene.

| # | Current thing | Location | Action | Replaced by |
|---|---|---|---|---|
| D1 | `ViewType` union has only `top-down` usable | `frontend/src/App.tsx:5` | keep enum, extend | `top-down`, `third-person`, `lidar` all functional except LiDAR |
| D2 | `addView()` hard-blocks non-top-down | `frontend/src/App.tsx:124` — `if (views.length >= 4 \|\| type !== "top-down") return;` | **delete the guard clause** | normal view creation |
| D3 | `ViewPane` renders an "unavailable" placeholder for any non-top-down view | `frontend/src/App.tsx:294-295` | **delete the placeholder branch** | `<Scenario3DCanvas/>` |
| D4 | `AddViewMenu` renders `disabled` 3D buttons with reasons | `frontend/src/App.tsx:283` | **delete the 3DPOV button only** | enabled button |
| D5 | Two API helpers pointing at non-existent routes | `frontend/src/api.ts:106-107` — `fetchWorkspaceDocument`, `fetchWorkspaceScenario` hit `/api/workspace/...`, always 404 | **delete both functions** | nothing; they are dead |
| D6 | Every dependency pinned to `"latest"` | `frontend/package.json` | **pin every version**; add `three`, `@react-three/fiber`, `@react-three/drei`, `vite-plugin-top-level-await` | reproducible builds |
| D7 | Version skew between the two esmini engines | native binary pinned in `compose.dev.yml` via `ESMINI_BIN` | **pick one version for both** | single esmini version everywhere |
| D8 | `App.tsx` is a 331-line single-file shell | `frontend/src/App.tsx` | **split**, do not extend | component tree under `frontend/src/` |
| D9 | Behaviour executor returns `unsupported` | `src/r2s_web/jobs.py:391-397` | **keep the stub contract, fill the gap** | behaviour preview backed by WASM engine |

D5 is worth calling out as free: those two functions are documented as broken in
`docs/current/frontend-workspace-handbook.md` lines 141-151 and are pure dead
weight.

### 2.1 What must NOT be deleted

This is the hard boundary. Do not "simplify" any of the following:

| Component | Location | Why it survives |
|---|---|---|
| `run_esmini()` native subprocess | `src/real2scenario/simulation.py` | Tier 0 instrument; sole source of ADE/FDE |
| `dat2csv` post-processing | same call site | produces `replay.csv`, the replay trace |
| `POST /api/replays` + job polling | `src/r2s_web/app.py:186-195` | async Tier 0 entry point |
| `GET /api/scenarios/{id}/trajectory` | `src/r2s_web/app.py:270` | trace consumption by the UI |
| `src/r2s_web/esmini.py` | whole file | capability probe (`GET /api/esmini`) and job store |

`docs/current/technical-contracts.md` line 255 states: *"Tier 0 is the
measurement path. It must not be replaced by Tier 1 or Tier 2 when reporting
replay fidelity."* `docs/current/decisions.md` DEC-014 repeats it. A browser WASM
trace **must never** be used as a fidelity claim. If you find yourself tempted to
have the browser compute ADE/FDE, that is a hard stop.

### 2.2 The boundary, stated as a table

Keep this visible in code comments and in the PR description.

| | WASM engine (browser) | Native esmini (backend) |
|---|---|---|
| Role | interaction, preview, teaching | measurement |
| Input | scenario + user actions | frozen scenario |
| Output | render frames | `replay.csv`, ADE/FDE |
| May feed the other | **no** | — |
| Runtime | browser, Worker | backend subprocess |

---

## 3. Prerequisites and setup

The upstream repo is **not** vendored in this repository. Clone it beside the
project (sibling directory, not inside `src/`), at the tag matching the version
chosen in D7:

```
git clone --depth 1 --branch v3.10.0 https://github.com/esmini/esmini
cd esmini && git submodule update --init --depth 1 externals/fmt
```

`externals/fmt` is mandatory: the WASM build script patches it for the Emscripten
sysroot. A shallow clone without `--recurse-submodules` leaves it empty and the
build fails with a confusing fmt include error.

Emscripten SDK **6.0.10** is the tested version (see `esminiJS/README.md`):

```
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk && ./emsdk install 6.0.10 && ./emsdk activate 6.0.10
source ./emsdk_env.sh
```

Host prerequisites: `cmake`, `ninja-build`, `patch`, `bzip2`.

---

## 4. Build — and the one deviation you must make

The stock script is `EnvironmentSimulator/Libraries/esminiJS/build.sh`, which
builds a **classic script** (`var Module = ...`) and copies it into
`esminiJS/example/`. That output is useless here: a classic script cannot be
`import`ed by Vite, and `esminiJS/example/viewer.js` resolves bare specifiers via
an importmap pointing at a CDN.

**Build it as an ES module instead.** Configure with:

- `-sMODULARIZE=1`
- `-sEXPORT_ES6=1`
- `-sEXPORT_NAME=createEsminiModule`
- `-sENVIRONMENT=web,worker`
- `-sALLOW_MEMORY_GROWTH=1`
- `-sEXPORTED_RUNTIME_METHODS=['FS','callMain','UTF8ToString']`
- `-sFETCH=1` (only if you serve `.wasm` separately and rely on streaming fetch)
- keep `-sFMT_OVERRIDE_INCLUDE_DIR` pointing at the patched fmt tree, as
  `build.sh` does

Then place the artifacts as committed build inputs:

```
frontend/wasm-esmini/
├── build.sh              # adapted from upstream, ES-module flags
├── esminiJS/             # upstream esminijs.{hpp,cpp}, embind.cpp, esminijs.cpp
│   └── patches/          # any local patch, committed
├── esmini.js             # generated, committed
└── esmini.wasm           # generated, committed
```

Commit the generated `.js`/`.wasm`. Rationale: building WASM requires a ~1 GB
emsdk toolchain that the runtime image does not have, and
`scripts/verify_release.py` scans committed artifacts. Generated-but-not-committed
means CI cannot reproduce it.

**Record the exact commit SHA and the Emscripten version in a
`frontend/wasm-esmini/BUILD.md`.** Without it the artifact is unauditable.

---

## 5. Wire it into the frontend

`vite.config.ts` needs a top-level-await plugin (Emscripten's ES module output
uses top-level await in `MODULARIZE` mode):

```ts
import topLevelAwait from 'vite-plugin-top-level-await'
// ...
plugins: [react(), topLevelAwait()],
optimizeDeps: { exclude: ['three', '@react-three/fiber'] },
assetsInclude: ['**/*.wasm'],
```

`assetsInclude` matters: Vite otherwise refuses to treat `.wasm` as an asset.

Suggested component layout (this is the D8 split):

```
frontend/src/
├── sim/
│   ├── esminiModule.ts        # lazy singleton: await createEsminiModule()
│   ├── simWorker.ts           # Worker: owns the WASM instance, runs the loop
│   ├── simClient.ts           # main-thread typed RPC wrapper over the Worker
│   └── protocol.ts            # request/response message types
├── three/
│   ├── Scenario3DCanvas.tsx   # react-three-fiber <Canvas> host
│   ├── RoadMesh.tsx           # lane surfaces from get_road_geometry()
│   ├── ActorBoxes.tsx         # actor boxes + labels
│   ├── Trails.tsx
│   └── cameras.ts             # orbit / follow-ego / top presets
└── panels/
    ├── TimelinePanel.tsx      # scrub, play, pause, step, speed
    └── BehaviourPanel.tsx     # inject speed / lane change, set variable
```

### 5.1 Run the engine in a Worker

Do not run WASM on the main thread. Scrubbing at high speed will freeze the tab.

Use a **plain Worker with `postMessage`**, not `SharedArrayBuffer`. This is
deliberate: SAB requires `Cross-Origin-Opener-Policy` and
`Cross-Origin-Embedder-Policy` headers, which must be set in **two** places
(`vite.config.ts` `server.headers` for dev *and* a FastAPI middleware for prod).
Missing one causes dev/prod divergence that is invisible until deployment.
Message-copying state per frame is cheap for tens of actors and avoids the whole
class of problem.

Protocol sketch:

```ts
// main -> worker
{ type: 'init', xoscName, xodrName, files: Record<string, ArrayBuffer>, dt }
{ type: 'step', dt }
{ type: 'seek', t }          // reset() + step forward; deterministic
{ type: 'injectSpeed', id, speed, shape, dim, value }
{ type: 'setVariable', name, value }
{ type: 'reset' }
// worker -> main
{ type: 'ready', road: ScenarioRoadGeometry }
{ type: 'frame', frame: ScenarioFrame }
{ type: 'error', message }
```

`seek` is `reset()` followed by N fixed steps. The engine is deterministic, so this
reproduces state exactly. Do not attempt incremental seek.

### 5.2 Files must be mounted into the Emscripten FS

The engine reads from an in-memory filesystem, not from URLs. The Worker receives
both files as `ArrayBuffer`, writes them with `FS.writeFile`, then constructs:

```ts
const scenario = new OpenScenario('/scenario.xosc', { dt, max_loop: 0 })
```

**Both `.xosc` and `.xodr` are needed.** Fetch them from
`GET /api/scenarios/{id}/artifacts`, which already returns the `ArtifactLink`
entries for both, including the generated `scenario.xosc`. No new endpoint is
required.

Note for the UI text: `ArtifactLink` carries a `map_warning`, and the shipped
template `src/real2scenario/templates/straight-two-lane-v1.xodr` is a 1000 m
straight two-lane road with no curves, no junctions and no elevation profile. The
3D view will render a flat ribbon. This is expected and correct — the map is
template-approximate by design and that limitation must stay visible in the UI,
not be hidden by the renderer.

---

## 6. Extend the engine surface

`esminiJS` exposes only what `embind.cpp` registers. Nothing else is reachable
from JavaScript.

### 6.1 What exists today

`embind.cpp` lines 144-157 register: `step`, `step_frame`, `reset`,
`get_object_count`, `get_object_states`, `get_object_state_by_index`,
`get_road_geometry`, `get_simulation_time`, `is_quit`, `get_object_state`,
`get_object_state_by_second`, `time_to_collision`.

That is **playback only**. There is no way to change behaviour at runtime. This is
the gap that prevents genuine interaction.

### 6.2 What to add

The good news: the injection machinery is already constructed. In
`EnvironmentSimulator/Modules/PlayerBase/playerbase.cpp` line 79 the
`ScenarioPlayer` constructor unconditionally does
`player_server_ = std::make_unique<PlayerServer>(this)` regardless of the
`launch_server` option, and `playerbase.hpp` line 250-251 exposes `player_server_`
as a **public** member. `esminijs.cpp` line 565 already calls
`SetInjectedActionsPtr()`.

So the work is small. Add to `esminijs.hpp` / `esminijs.cpp`:

```cpp
void inject_speed(int id, double speed, int transition_shape, int transition_dim, double transition_value);
void inject_lane_change(int id, int mode, int target, int transition_shape, int transition_dim, double transition_value);
void inject_lane_offset(int id, double offset, int mode, int target, int transition_shape, int transition_dim, double transition_value);
void set_paused(bool paused);
int  set_variable(const std::string& name, double value);
int  get_variable(const std::string& name, double* out);
int  injected_action_ongoing(int action_type);
```

Implementation, using the already-public members:

```cpp
void OpenScenario::inject_speed(int id, double speed, int shape, int dim, double value)
{
    scenarioengine::SpeedActionStruct action{id, speed, shape, dim, value};
    player_->player_server_->InjectSpeedAction(action);
}

void OpenScenario::set_paused(bool paused)
{
    player_->SetState(paused ? scenarioengine::PlayerState::PLAYER_STATE_PAUSE
                             : scenarioengine::PlayerState::PLAYER_STATE_PLAYING);
}
```

Backing declarations: `InjectSpeedAction`, `InjectLaneChangeAction`,
`InjectLaneOffsetAction`, `InjectedActionOngoing` at
`EnvironmentSimulator/Modules/PlayerBase/PlayerServer.hpp` lines 98-101;
`SetState` at `playerbase.hpp` line 219; `SetVariableValue` overloads at
`playerbase.hpp` lines 205-214.

Then register each one in `embind.cpp`:

```cpp
.function("inject_speed", &OpenScenario::inject_speed)
.function("inject_lane_change", &OpenScenario::inject_lane_change)
.function("set_paused", &OpenScenario::set_paused)
.function("set_variable", &OpenScenario::set_variable)
```

**Use scalar parameters, not `value_object<SpeedActionStruct>`.** Registering the
struct means importing `PlayerServer.hpp` types into the embind surface and makes
the JS call site awkward. Five scalars is friendlier and costs nothing.

Rebuild the WASM after every change in this group and commit the new artifact.

---

## 7. Serving and deployment

1. **`.wasm` MIME type.** `create_app()` in `src/r2s_web/app.py` mounts
   `StaticFiles(directory=frontend_dist, html=True)` at `/` (line 344). The
   runtime image is `python:3.11-slim`, where `.wasm` MIME registration is not
   guaranteed. Add near the top of `create_app()`:

   ```python
   import mimetypes
   mimetypes.add_type("application/wasm", ".wasm")
   ```

   Without it, `WebAssembly.instantiateStreaming` throws. Fallback is
   `arrayBuffer()` + `WebAssembly.instantiate`, which is acceptable but async-loads
   slower.

2. **No SPA fallback.** `StaticFiles(html=True)` serves `index.html` for
   directories but has no catch-all route, so an unknown path 404s. This does not
   matter once the 3D view is a routed React view rather than a standalone page.

3. **`.dockerignore`.** `dist` and `frontend/dist` are excluded, which is correct
   because `Dockerfile` rebuilds the frontend from source. Committed WASM artifacts
   under `frontend/wasm-esmini/` are **not** excluded and will be copied.

4. **Dev vs prod asset staleness.** In `compose.dev.yml` the API container
   bind-mounts the whole repo, so the static mount serves whatever `frontend/dist`
   the host last built. After changing WASM you must run `npm run build` locally
   for the backend to serve the new artifact. Vite dev picks it up live.

---

## 8. Repository hygiene — required, not optional

- **`.gitignore` excludes `dist/` and `frontend/dist/`.** Never commit the WASM
  artifact into `dist/`. It must live in `frontend/wasm-esmini/`.
- **`scripts/verify_release.py`** scans the committed tree for binary patterns
  (`*.bin, *.npy, *.png, *.jpg, *.pcd, *.bag`) and the nuScenes trainval token. A
  multi-megabyte `.wasm` will be picked up and manifest-hashed. Add it to the
  allowlist with an explicit comment, or CP5 release verification will fail.
- **`NOTICE` / third-party terms.** esmini is MPL-2.0; three.js is MIT;
  `@react-three/fiber` is MIT. All are compatible with this repository's Apache-2.0
  code licence. Add attribution for all three plus Emscripten.
- **Data licence unchanged.** Rendered content — `.xodr`, `.xosc`, trajectories —
  remains derived from nuScenes and stays local-only and non-commercial
  (`README.md` lines 205-210, DEC-005 in `docs/current/decisions.md` line 34). The
  simulator changes nothing about this.
- **Commit the WASM artifact with provenance.** Without `BUILD.md` recording the
  esmini commit SHA and Emscripten version, `verify_release.py` will flag an
  unexplained binary in the tree.

---

## 9. Sequencing

Do these in order. P0 can fail and invalidate everything downstream, so it goes
alone and first.

| Phase | Work | Done when |
|---|---|---|
| **P0** | Build upstream `esminiJS` as an ES module; load it in a bare page; confirm `step_frame` returns object states and `get_road_geometry` returns lane surfaces | a screenshot of a running step_frame loop exists, with the exact build command recorded |
| **P1** | Repo hygiene only: D5, D6, D7. No UI work | `npm ci` twice resolves identical trees; single esmini version recorded |
| **P2** | D8 split, D1-D4, `Scenario3DCanvas` with road mesh, actor boxes, orbit/follow/top, timeline scrub and step-frame. **Playback only, no injection yet** | third-person view renders the shipped scenario and scrubs smoothly |
| **P3** | Section 6 extensions, rebuild WASM, `BehaviourPanel` | injecting a speed change visibly alters subsequent frames |
| **P4** | Boundary enforcement: browser traces never written to `replay.csv`, never consumed by metric code; `NOTICE`, `verify_release.py` allowlist | grep for browser-side metric paths returns nothing; release script passes |

Do not start P2 before P0 passes. Do not start P3 before P2 scrubs smoothly — a
janky renderer makes injection debugging miserable.

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| WASM build fails on host glibc | High | P0 exists precisely to surface this; the upstream fmt patch is the usual culprit |
| Renderer jank at high scrub speed | Medium | Worker + `postMessage`; fixed `dt` decoupled from render rate |
| Browser trace leaks into fidelity claims | Medium | Section 2.2 boundary, P4, plus a test asserting the metric code has no import path to the Worker |
| Artifacts bloat the release | Medium | One ES-module build, committed once; no per-scenario bundles |
| UI implies the map is real | **High** | `map_warning` from `ArtifactLink` must be rendered in the 3D view, not swallowed. `ui-mvp-flow-spec.md` line 38: *"3D renders only recorded or pipeline-produced data. No decorative reality."* |
| 3D view perceived as a second product | Medium | Implement as a view type inside the existing view-pane chrome, not a separate page |

---

## 11. Escalation points

Stop and raise these rather than improvising:

1. Anyone proposes removing `run_esmini()` / `dat2csv` / `POST /api/replays`
   because the browser engine "does the same thing". It does not: it is Tier 1.
2. Anyone proposes computing ADE/FDE in the browser.
3. The render is being dressed up to look like a real captured map.
4. A `.xodr` with curves or junctions appears without a documented provenance
   change — that alters the `map_warning` semantics.

---

## 12. Documentation debt you are creating

This handoff does not update `docs/current/`. Before merge, note that the
following will still be inconsistent and someone must reconcile them:

- `docs/current/ui-mvp-flow-spec.md` line 180 states react-three-fiber is the
  default 3D stack — this work **aligns** with it, no change needed.
- `docs/current/technical-contracts.md` line 274 states Tier 1 acceptance
  requires "no new heavy runtime dependency". A WASM engine is heavier than the
  Tier 1 contract describes. Either amend the contract to name the WASM engine as
  the Tier 1 implementation, or record an explicit exception.
- `docs/current/active-work.md`, `docs/current/frontend-workspace-log.md` and
  `docs/current/backend-workspace-contract-log.md` should each gain a row.
  Merges in this repository have previously dropped frontend work when the log
  did not record it.

Run `scripts/check_docs_consistency.py` before merge; this handoff is written to
satisfy it (no absolute host paths, no broken links).