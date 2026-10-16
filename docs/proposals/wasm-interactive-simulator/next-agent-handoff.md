# WASM / esminiJS Side MVP — Handoff Prompt for the Next Agent

> This document is a prompt. Everything above this line is project-manager
> context. Send the agent the "Prompt" section.

Status: `P0 COMPLETE / P2 PARTIAL / FIXED-STEP HARDENED / ISOLATED FROM MAIN APP / NEW CAPABILITY`
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
`0.01`, 1 active object, 2 lane surfaces, 2 road marks.

**P2 — partial.** A Worker protocol, a Three.js renderer and playback controls
exist and work. The playback Worker now owns a fixed `dt = 0.01` clock matching
native; seek remains out of scope until reset-and-reintegrate behavior is added.

**Isolated from the main app.** `wasm-playback` was **removed** from
`VIEW_REGISTRY` in `frontend/src/view-panels.ts`. It is reachable only at
`/wasm-smoke`. This is deliberate and good — do not re-add it to the workspace
view registry without an owner decision.

**Real scenarios work, on the smoke page only.** `WasmPlaybackView` accepts
`scenarioId` and calls `POST /wasm-pair`, which materializes a private XOSC/XODR
pair under `reports/wasm-pairs/<sha>/` and serves it through the existing
confined artifact route. `WasmSmokePage` passes it; the main app does not.

### Known defects and risks — fix or record these

1. **`project()` was dead code.** Removed along with the unused SVG bounds helpers.

2. **`useEffect` dependency was incorrect.** The loading effect now depends on
   `scenarioId`; the smoke-page key remains harmless but is no longer required for
   correctness.

3. **Provenance warning was inaccurate for real scenarios.** It now distinguishes
   real scenario playback from the synthetic fixture while retaining the preview
   and Tier 0 boundary warning.

4. **WASM-pair cache key ignored exporter version.** Fixed by including
   `openscenario-exporter-v2` in the cache-key namespace.

5. **`dist/` is gitignored.** A fresh clone **cannot run this at all** until
   someone rebuilds with `frontend/wasm-esmini/build.sh`. Say this in the README
   if it is not already obvious to a newcomer.

6. **Worker protocol coverage was missing.** Added
   `WasmPlaybackView.test.tsx`, covering init, play, pause, step and reset
   messages. The backend `wasm-pair` route remains covered by
   `tests/test_web_api.py:121`.

7. **Proposal README was stale.** Reconciled with the current build seam, Worker,
   smoke page and raw Three.js renderer.

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

### Owner decisions — answered 2026-10-16, binding

These replace the questions in the previous revision of this document. Do not
re-ask them.

**Q1 — Approved, with a gate.** WASM was proposed by external experts and is
**approved as the intended replacement for the project's current runner**. Before
any replacement work, the priority is **testing**. Treat build/test hardening as
the next increment, not feature completion.

**Q2 — Diagnostic-only for now.** WASM stays at `/wasm-smoke` and stays out of
`VIEW_REGISTRY`. Promotion to a real workspace view type requires a separate
explicit owner approval after joint review with the WASM agent. Do not re-add it
to the registry on your own judgement.

**Q3 — Fusion means recorded nuScenes sensor data alongside WASM actors.**
Render recorded sensor evidence next to engine actors. **Not** sensor output from
the WASM engine, which has no sensor channel. Note this keeps Sensor Evidence
semantics intact: recorded nuScenes data is recorded nuScenes data, and must
never be presented as engine-generated output.

**Q4 — STILL OPEN. Not answered, not deferred-by-abandonment.** See
"Retained open question Q4" below. Do not build cross-panel focus sync in this
increment, and do not lift `selectedId` out of `ThreePlaybackCanvas`.

**Q5 — Worker-driven fixed-step is REQUIRED, and seek is in scope with one hard
condition.**
- Fixed step driven by the Worker, **not** a UI interval and not rAF. This is a
  parity requirement, not a preference: native runs `--fixed_timestep 0.01`, and
  the timestep is measurably load-bearing — `0.05 → 0.01` moved ADE mean
  `0.1829 → 0.0411 m` (4.2x). A variable-step or rAF integrator is a different
  integrator and will not agree with native. Pin `dt = 0.01`. `dt = 0.005` was
  bit-identical, so `0.01` is converged and safe.
- **Seek must be `reset` + re-integrate from `t = 0` to the target step.** A
  naive "jump to nearest cached frame" breaks parity, because state depends on
  integration history.
- **If seek slips, ship play/step/reset + a timestamp readout, and do not claim
  correlation.** Without seek you cannot line a frame up with a LiDAR sweep, so
  correlation is impossible. A truthful clock without seek is still useful; an
  untruthful seek silently poisons the comparison.

**Q6 — Not needed. Leave both engines on the full track population.** Applying
`min_track_duration_s` to one engine only would break parity, because the two
engines would then score different track populations and the numbers would not be
comparable. Three reasons to leave it alone:
- The policy exists to trim tracks the simulator cannot converge onto — 2-4
  keyframe fragments at scene end. After both timing fixes it is nearly moot:
  only **47/3215 tracks (1.5 %)** are under 2 s and residual is ~`0.035 m`.
- Its value at `dt 0.05` was ADE mean `1.1378 → 0.5539`, but at `dt 0.01` the
  whole residual is already `0.0411`, so there is no accuracy pressure left.
- It is a population-alignment rule, not an accuracy tweak. Any future cut must be
  applied identically to both engines and chosen on physical grounds, never
  fitted to a metric.
- **Verify before assuming parity:** confirm whether esminiJS uses the same
  position-following controller as native. If it is a simpler kinematic
  interpolator it may not have the convergence problem at all, in which case
  excluding short tracks would **discard good data**.
- Revisit only if convergence failure actually appears in the browser, and then
  change both engines together.

---

## Retained open question — Q4: synchronized cross-panel focus

Status: `OPEN — DELIBERATELY NOT ANSWERED YET`
Owner decision required. This is **not** a task for the next agent to guess.

### The question, stated in full

**When a viewer selects an object in the WASM 3D playback view, which other
views should respond, and what exactly does "respond" mean?**

Concretely, three linked decisions:

1. **What is the identity key?** The WASM engine returns its own entity `id`
   (see `WasmObjectState.id` in `types.ts`). The workspace uses nuScenes
   `instance_token` / `actor_id`. These are different key spaces. Sync needs a
   stable mapping, and engine IDs are **not** guaranteed stable across `reset()`
   — the proposal's own analysis warns that engine entity IDs must be
   "validated/remapped after reset". So the key question is: do we map WASM
   engine IDs onto canonical actor identity once and cache it, or re-derive it on
   every reset?

2. **Which panels consume the selection?** Candidates in this repository:
   - the workspace **actor timeline** (`workspace-actor-timeline-v1`, already
     time-indexed and already synchronized with the playhead);
   - the **gate lane** (`workspace-gate-timeline-v1`, G1-G7 status segments);
   - the **LiDAR canvas** (recorded `LIDAR_TOP` payload view);
   - the existing **Top-down** authoring view (already has `selectedActor` and
     `onSelectActor`);
   - the **Sensor Evidence** view.

   Top-down already has actor selection wired, so it is the natural first
   candidate — but it is also the authoring view, and per project boundary it
   must stay the authoring/map/trajectory pane. Whether WASM selection should be
   allowed to drive it is exactly the kind of thing that needs an explicit answer.

3. **Is sync one-way or bidirectional, and does it touch scenario state?**
   - One-way (WASM → other panels) is a pure view concern and is cheap.
   - Bidirectional (clicking a timeline track focuses the WASM camera) needs a
     camera command path into `ThreePlaybackCanvas`.
   - **Does selection drive scenario state?** For example does focusing an actor
     also move the shared `playhead`, or run a constrained maneuver? If yes, that
     is a **behaviour** concern, not a view concern, and it touches the disabled
     Behavior/Validate/Replay boundaries (DEC-016) and the recipe contract. That
     would be a scope increase and needs its own approval.

### Why it is being held

The owner's guidance on 2026-10-16 was "decide later". This section exists so
that "later" is a tracked item with a restated question rather than a silence.

The reason it is worth holding rather than building opportunistically: the
identity-key problem in (1) is the same class of problem as the recent replay
defects. Actor identity across engine/canonical boundaries is precisely where
this codebase has already shipped bugs — the recorded `LIDAR_TOP`
sample-vs-`sample_data` token confusion, and the timing anchor that drove actors
before their recorded track began. Building cross-panel sync before the key
mapping is settled risks a visually convincing panel that highlights the wrong
actor, which is exactly the "looks connected but is wrong" failure mode this
project forbids.

### Interim instruction — binding until Q4 is answered

- Do **not** lift `selectedId` out of `ThreePlaybackCanvas`. Keep selection local.
- Do **not** add cross-panel listeners, stores or props for selection.
- If you refactor selection for any other reason, preserve it as local state and
  leave a short note here saying what you preserved and what Q4 still needs.
- You **may** clean up selection internals (highlight colour, mesh lookup) as
  long as no cross-panel surface is introduced.

### What an answer needs to contain

Whoever answers Q4 must specify: the identity key and its reset behaviour; the
panels to consume selection and in which direction; whether playhead or scenario
state is affected; and the exact acceptance bar. A decision that only says "sync
the panels" is not sufficient and should be sent back.

### Revisit when

Any one of these becomes true:

- the `dt` parity fix has landed and the clock is trustworthy (Q5);
- Q2 promotion to a real workspace view type is approved (a sync target must
  exist first);
- sensor fusion under Q3 ships, because fusion makes "which object is selected"
  materially more important.

---

### Highest-priority defect: fixed-step parity

The owner decision on Q5 makes this concrete and urgent:

```text
native   src/real2scenario/simulation.py:58   fixed_timestep_s = 0.01   ✅
WASM     frontend/src/wasm-playback/worker.ts           dt: 0.01          ✅
WASM     frontend/src/wasm-smoke/worker.ts              dt: 0.01          ✅
```

The browser engine was integrating at the timestep that the owner measured as
**4.2x worse**. This increment corrected the integration timestep and moved clock
ownership into the Worker. Any correlation claim remains withheld until seek and
sensor fusion are implemented and reviewed.

The view now sends `play`, `pause` and single fixed-step `step` commands; it does
not run a UI interval or animation-frame integrator.

### Definition of done for any increment you ship

Highest-priority items, in order: **(1)** Worker `dt` is `0.01` and the Worker
owns the clock; **(2)** Q5 parity behaviours implemented or explicitly deferred
with the correlation claim withheld; **(3)** provenance labels accurate; **(4)**
at least one automated test for the Worker protocol contract.

- [ ] Worker integration timestep is `0.01`, matching native, and the Worker owns
      the clock.
- [ ] Seek, if present, is `reset` + re-integrate from `t = 0` — never a cached
      frame jump.
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

1. Whether the `dt` parity fix landed, with the before/after you measured.
2. The defect list in "Known defects and risks" re-verified, fixed or explained.
3. A proposed increment — small enough to review — with its own acceptance bar.
4. An explicit statement of what stays preview-only no matter what you ship.
5. Your reading of whether esminiJS uses native's position-following controller
   (Q6 verification). That answer decides whether short-track exclusion ever
   applies to the browser engine at all.

**The boundary is now approved and the six questions are answered. Build — but
build in the order above, and never let a browser number reach a report.**
