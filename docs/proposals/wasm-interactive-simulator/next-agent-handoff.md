# WASM / esminiJS Side MVP — Handoff Prompt for the Next Agent

> This document is a prompt. Everything above this line is project-manager
> context. Send the agent the "Prompt" section.

Status: `P0 COMPLETE / P2 PARTIAL / ISOLATED FROM MAIN APP / NEW CAPABILITY`
Written by: Project Manager, 2026-10-16
Baseline: `aa9cf45` / `ee68ecf`
Working tree: **clean** at time of writing.

---

## ⚠️ Read this before you accept the brief

The task as originally framed says OrbitControls, raycasting, camera tween/focus
and cuboid rendering are **not implemented**. **That is wrong — read
`frontend/src/wasm-playback/ThreePlaybackCanvas.tsx` before you plan anything.**

| Item | Actual state |
|---|---|
| OrbitControls | ✅ **Implemented** — damping 0.08, import from `three/examples/jsm` |
| Raycasting / click-select | ✅ **Implemented** — `Raycaster` + `Vector2`, `intersectObjects` on `pointerdown` |
| Camera tween / focus | ✅ **Implemented** — `FocusAnimation`, cubic ease-out lerp, `resetView` |
| Cuboid actor rendering | ✅ **Implemented** — `BoxGeometry`, scaled by width/height/length, `rotation.y = -h` |
| **LiDAR / radar fusion** | ❌ **Not started** |
| **Synchronized cross-panel focus** | ❌ **Not started** |
| Playback control (Play/Step/Reset) | ✅ Implemented (`WasmPlaybackView.tsx`) |
| Scenario switching (fixture vs real) | ✅ Implemented via backend `wasm-pair` endpoint |

Do **not** re-implement the first four. Extend them. Wasting a day rebuilding
OrbitControls is the main failure mode this section exists to prevent.

---

## Prompt (copy from here)

### Your mission

Continue the **WASM / esminiJS side MVP** — an in-browser 3D playback surface
built on an Emscripten build of esmini running in a Web Worker. P0 (feasibility)
is done and P2 (playback slice) is partially done. You are picking up an
in-progress capability, not starting from scratch.

This is **new capability work in the WASM/esminiLib phase**. It is explicitly
**not** part of the view-panel structural cleanup. Keep those separate.

Read `AGENTS.md`-level discipline from `docs/current/technical-contracts.md`:
run GitNexus `impact` before editing any symbol and `detect_changes` before
committing.

### What actually exists right now

```text
frontend/wasm-esmini/            build seam (upstream source lives OUTSIDE repo)
  build.sh                       wrapper: copies fmt headers, applies patch, runs emscripten
  BUILD.md                       provenance: esmini v3.10.0 @ 06065f9, emsdk 6.0.10
  README.md                      what the artifact must expose
  smoke.mjs                      Node-side diagnostic harness
  dist/ build/                   GITIGNORED — not committed, must be built locally

frontend/src/wasm-smoke/         owner visual-review page, served at /wasm-smoke
  WasmSmokePage.tsx              page + scenario picker + P0 result panel
  worker.ts                      P0 probe: init fixture, step_frame(0), report counts
  fixture.xosc fixture.xodr      inline synthetic scenario, committed
  esmini.d.ts                    ambient module declaration

frontend/src/wasm-playback/      the actual playback slice
  worker.ts                      Worker: init / step / reset / dispose protocol
  types.ts                       WasmFrame, WasmObjectState, WasmRoadGeometry, protocol types
  WasmPlaybackView.tsx           React wrapper: loads scenario, Play/Step/Reset
  ThreePlaybackCanvas.tsx        Three.js scene (see table above)
  playback.css

src/r2s_web/app.py:213           POST /api/workspace/scenarios/{id}/wasm-pair
```

`main.tsx` routes `/wasm-smoke` to `WasmSmokePage`; every other path renders the
normal `App`.

### Current state, precisely

**P0 — done.** esminiJS builds as an ES module (`EXPORT_ES6=1`, `MODULARIZE=1`,
`ENVIRONMENT=web,worker`) and loads in a real browser Worker. Verified: sim time
`0.05`, 1 active object, 2 lane surfaces, 2 road marks.

**P2 — partial.** A Worker protocol, a Three.js renderer and playback controls
exist and work. Playback is currently a `window.setInterval` at `DT = 0.05`
posting `step` messages, not a fixed-step clock driven by simulation time.

**Isolated from the main app.** `wasm-playback` was **removed** from
`VIEW_REGISTRY` in `frontend/src/view-panels.ts`. It is reachable only at
`/wasm-smoke`. This is deliberate and good — do not re-add it to the workspace
view registry without an owner decision.

**Real scenarios work, on the smoke page only.** `WasmPlaybackView` accepts
`scenarioId` and calls `POST /wasm-pair`, which materializes a private XOSC/XODR
pair under `reports/wasm-pairs/<sha>/` and serves it through the existing
confined artifact route. `WasmSmokePage` passes it; the main app does not.

### Known defects and risks — fix or record these

1. **`project()` is dead code.** `WasmPlaybackView.tsx:38` defines an SVG
   projection helper left over from the pre-Three.js renderer. Nothing calls it.
   Remove it and the now-unused `frameBounds`/`bounds` if they are only feeding it.

2. **`useEffect` dependency is `[]` but reads `scenarioId`.** Reloading works
   only because `WasmSmokePage` passes `key={scenarioId || "fixture"}` to force a
   remount. That is fragile and non-obvious. Make the dependency correct.

3. **The warning text lies when a real scenario is loaded.**
   `WasmPlaybackView` always renders "Synthetic playback fixture" even when
   `scenarioId` is a real nuScenes scenario. Make it conditional. This matters
   more than it looks — a panel that mislabels its own provenance is exactly the
   failure mode this project forbids.

4. **WASM-pair cache key ignores exporter version.**
   `pair_key = sha256(f"wasm:{scenario_id}")`. The exporter changed at
   `b52d423`, so a pair generated before that is stale and will be silently
   reused. Add an exporter-version component to the key, or invalidate. Currently
   `reports/wasm-pairs/` is empty on this host, so nothing is poisoned yet.

5. **`dist/` is gitignored.** A fresh clone **cannot run this at all** until
   someone rebuilds with `frontend/wasm-esmini/build.sh`. Say this in the README
   if it is not already obvious to a newcomer.

6. **No frontend test covers any of this.** `wasm-smoke` and `wasm-playback`
   have zero frontend test coverage. The backend `wasm-pair` route does have one
   (`tests/test_web_api.py:121`). Add at least a protocol test for the Worker
   message contract.

7. **`docs/proposals/wasm-interactive-simulator/README.md` is stale.** It says
   `Status: PROPOSAL — P0 NOT STARTED` and "the repository does not yet contain
   the esminiJS source, Emscripten build, WASM artifact, Worker protocol or
   renderer". All of that is now false. Update it.

### Non-negotiable boundaries

1. **Browser WASM is preview/interaction only. It must never feed ADE/FDE,
   `replay.csv`, gates or any report.** Native esmini remains the sole sanctioned
   metric source. This is DEC-018 in `docs/current/decisions.md`.
2. **Never present a browser frame as an esmini-native artifact.** If the WASM
   engine and native esmini disagree, native is authoritative.
3. **Parity target is `followingMode="position"`, pre-trigger hold and
   `AbsoluteTargetSpeed=0`.** Do **not** add non-standard `Vertex/@speed`. Native
   esmini 3.9.0 ignores it; adding it in WASM would create a parity gap. This was
   already tried and reverted — see `BUILD.md`.
4. **An unavailable capability must be shown as unavailable.** No placeholder
   that reads as success.
5. **No new dependency without an approved decision.** `three@^0.180.0` is
   already added. Adding `react-three-fiber`, `drei` or a physics engine needs
   sign-off — the proposal explicitly says not to add speculative renderer deps
   before P0 succeeds, and P0 has now succeeded, so that gate has moved but the
   decision has not been made.
6. **Keep `docs/architecture/boundary-map.md` intact.** Frontend presents; it
   must not invent domain truth.
7. Raw nuScenes data and derived artifacts stay local/private.

### Questions you must answer before building

**Q1 — Is this capability approved for the MVP, or exploratory?** Nothing in
`docs/reports/tracks-1-6-disposition.md` covers WASM. It is neither in the seven
acceptance tracks nor explicitly deferred. This is an owner decision and it
blocks planning.

**Q2 — Where does WASM playback belong in the product?** It is currently only at
`/wasm-smoke`, a diagnostic page. Options: keep it diagnostic-only (status quo),
promote it to a real workspace view type, or something else. Promoting it changes
the view registry, the capability contracts and the claim boundaries.

**Q3 — LiDAR/radar fusion: what exactly?** The Worker currently returns
`object_states` and `road_geometry` only. There is no sensor channel from the
WASM engine. Fusion would mean either rendering recorded nuScenes sensor data
alongside WASM actors, or getting sensor output from the engine. These are very
different amounts of work and only the first is honest about the engine's role.

**Q4 — Synchronized cross-panel focus: sync with what?** `selectedId` is local
state inside `ThreePlaybackCanvas` and is not lifted. Synchronizing means lifting
it and having at least one other panel consume it. Which panel — the workspace
actor timeline, the gate lane, the LiDAR canvas? And does selection need to drive
scenario state, or only view state?

**Q5 — Fixed-step clock.** Should playback be driven by simulation time from the
Worker rather than by a UI interval? The proposal asks for fixed-step playback and
seek. Is seek in scope, or only play/step/reset?

**Q6 — Is `min_track_duration_s` needed here too?** It is open in
`docs/reports/residual-replay-error-composition.md` for native replay. Does the
same policy apply to the browser engine, or is the engine's behaviour different?

### Definition of done for any increment you ship

- [ ] No WASM-derived number appears in any report, metric, gate or `replay.csv`.
- [ ] Provenance labels are accurate: fixture vs real scenario vs native.
- [ ] Dead code removed; `useEffect` deps correct.
- [ ] At least one automated test for the Worker protocol contract.
- [ ] `npm test -- --run` and `npm run build` pass.
- [ ] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` passes.
- [ ] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py` passes.
- [ ] `docs/proposals/wasm-interactive-simulator/README.md` reconciled with reality.
- [ ] `BUILD.md` updated if the build changed.
- [ ] Your report answers Q1–Q6 and adds anything I did not ask.

### How to actually run it

```bash
# 1. build the WASM artifact (REQUIRED — dist/ is not committed)
source "$EMSDK_DIR/emsdk_env.sh"          # set EmsDK to your local checkout
ESMINI_SOURCE_DIR="$PWD/../esmini" frontend/wasm-esmini/build.sh

# 2. API (host uvicorn; vite proxies to 127.0.0.1:8000)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m uvicorn r2s_web.app:app \
  --app-dir src --port 8000

# 3. frontend
cd frontend && npm run dev

# 4. owner review page
#    http://localhost:5173/wasm-smoke
```

The upstream esmini checkout at `../esmini` and the emsdk are **outside** this
repository. If they are missing on your machine, you cannot build, and nothing
in this subsystem will run. Check before you start.

### Current verification baseline

Python `336 passed` · frontend `49 passed` · build clean · docs consistency PASS.
Re-measure it; the count moves.

---

### What I most want back

1. Confirmation of Q1–Q6 before any feature work.
2. The defect list in "Known defects and risks" re-verified, fixed or explained.
3. A proposed increment — small enough to review — with its own acceptance bar.
4. An explicit statement of what stays preview-only no matter what you ship.

**Ask before you build. This subsystem has an approved boundary and a proposal
that contradicts it in places; sorting that out first is cheaper than a
rollback.**