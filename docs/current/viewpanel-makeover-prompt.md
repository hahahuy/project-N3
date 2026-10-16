# View Panel Makeover — Handoff Prompt for the Next Agent

> This document is a prompt. Paste the whole "Prompt" section below to the next
> agent. Everything before it is context for the project manager.

Status: `READY FOR NEXT AGENT`
Written by: Project Manager, 2026-10-16
Baseline commit: `e9ad9b8`
Scope: **frontend view-panel architecture only** — no new capabilities, no new
backend features, no scientific claims.

---

## Prompt (copy from here)

### Your mission

Redesign the **view panel system** in `frontend/src/App.tsx`. It currently works
in places but is structurally messy and, in several specific places, wired
wrongly. Your job is to understand it completely, restructure it cleanly, and
**tell me exactly what you need decisions on** before you guess.

**Do not add features.** This is a structural cleanup. Preserve every existing
capability contract and every unavailable/fail-closed state exactly as-is.

---

### Step 0 — Read these first

1. `AGENTS.md` — **mandatory GitNexus workflow**. Run
   `impact` before editing any symbol and `detect_changes` before any commit.
2. `docs/current/project-status.md` — current claims and boundaries.
3. `docs/current/technical-contracts.md` — the API contracts.
4. `docs/contracts/web-availability.md` and `docs/contracts/api-surface.md` — new,
   written by the parallel in-flight effort; use them.
5. `docs/proposals/wasm-interactive-simulator/README.md` — read the
   "Current Reconciliation" table. It already lists stale claims; do not trust
   the proposal's description of the repo.

**Note: `git status` is dirty.** There is uncommitted parallel work (a WASM
playback subsystem, new docs trees). Do not discard it, do not revert it, and
do not commit on top of it without telling me. Start by running `git status` and
`git diff` and understanding what is not yours.

---

### Step 1 — The current state (verified by the PM, but re-verify yourself)

**Files:** `frontend/src/App.tsx` (1020 lines — everything is in this one file),
`frontend/src/api.ts`, `frontend/src/icons.tsx`, `frontend/src/styles.css`.

#### 1.1 View type registry

```ts
type ViewType = "top-down" | "third-person" | "in-car" | "lidar"
              | "sensor-evidence" | "wasm-playback";
const MAIN_VIEW: ViewType = "third-person";
const MAX_VIEWS = 3;
```

**6 types exist. `AddViewMenu` only offers 4** (`top-down`, `sensor-evidence`,
`third-person`, `wasm-playback`). `in-car` and `lidar` are **unreachable from the
UI** but still exist in `ViewType`, still have labels/icons, and are still
handled in the render tree. This is a dead-code and dead-UX problem.

#### 1.2 Add-view menu — CONFIRMED BUG

```tsx
const slot = (index) => atLimit ? `maximum ${MAX_VIEWS} views reached`
                              : `view panel ${index} of ${MAX_VIEWS}`;
```

The slot numbers are **hardcoded and wrong**: `top-down`→`slot(2)`,
`sensor-evidence`→`slot(3)`, `third-person`→`slot(1)`, `wasm-playback`→`slot(1)`.
Two buttons claim panel 1, the ordering is arbitrary, and `slot()` is a pure
function of the literal, not of actual insertion position. `viewCount` is
accepted as a prop and **never used** for the label. Verify and fix.

#### 1.3 Render dispatch — the core messiness

`ViewPane` renders content through **one deeply nested ternary chain**
(~600 chars on a single line) that branches on view type, then falls through to
live-vs-frame-vs-unavailable:

```
top-down        → TopDownView
sensor-evidence → SensorEvidenceView
lidar           → LidarView
wasm-playback   → WasmPlaybackView
   ...everything else falls through to:
     liveState running/paused/reset → LivePOVView
     frame                          → POVView
     else                           → unavailable-view
```

**Consequence you must fix:** `third-person` currently conflates **three
different renderers** — native esmini live state, internal transform POV, and
esmini image artifact — decided by silent precedence in one expression. The
user cannot tell which one they are looking at. Same for `in-car`.

#### 1.4 `ViewPane` prop signature

`ViewPane` takes **22 props** and re-destructures them inline in the type
annotation. Every pane receives every prop regardless of whether it uses it.

#### 1.5 Per-pane "Start native session" button

```tsx
{view.type !== "top-down" && view.type !== "lidar"
  && view.type !== "sensor-evidence" && view.type !== "wasm-playback" && <button .../>}
```

A **growing exclusion list**. Each new view type requires editing this boolean
chain or the button silently appears/disappears. This already happened with
`wasm-playback`.

#### 1.6 WASM Playback — READ THIS CAREFULLY, IT IS A BLOCKING PROBLEM

`frontend/src/wasm-playback/worker.ts` imports
`fixture.xosc` and `fixture.xodr` via `?raw`, writes them to the WASM filesystem,
and steps them. It makes **zero network calls** — it fetches nothing from the
backend. `WasmPlaybackView` is rendered as `<WasmPlaybackView />` with **no
props**, so it does not receive the selected scenario.

**Therefore: a user who selects a real nuScenes scenario and opens WASM
Playback sees a different, hardcoded scene while the rest of the UI shows their
scenario.** The panel gives no indication that it is not connected to the user's
data.

This directly violates a non-negotiable project boundary:
*"Do not silently reinterpret unavailable capabilities as successful behavior."*
A connected-looking panel showing a fixture is worse than an explicit
unavailable state.

**You must not ship this as-is.** Until a real backend source exists, WASM
Playback must either be visibly labelled as a disconnected demo/fixture, or be
removed from the add-view menu. **Ask me which** — see Question 4.

#### 1.7 Toolbar buttons and their real state

| Group | Button | State | Backend |
|---|---|---|---|
| History | Undo / Redo | wired, gated on `recipe.history.undoable` | `POST /recipe/undo`, `/redo` |
| Import | **Import scene** | **`disabled: true`** | `POST /source-scenes/{token}/import` — backend exists, **no UI** |
| Import | Export | wired | — |
| Edit | Select actors | wired | — |
| Edit | Edit motion | gated on selection | `POST /scenarios/{id}/variants/preview` |
| Edit | **Behavior mode** | **`disabled: true`** | none |
| Check/Run | **Validate** | **`disabled: true`** | none |
| Check/Run | **Replay** | **`disabled: true`** | `/replays` exists, **no UI** |
| Inspect | Measure / Compare | wired | `GET /compare` |
| View | Add view | wired, capacity badge | — |

**13 exported helpers in `api.ts` are called by neither the UI nor tests:**
`fetchWorkspaceDocument`, `createBatch`, `fetchBatchResults`,
`fetchBatchTrajectory`, `exportBatchResult`, `sendLiveCommand`, `createReplay`,
`fetchReplay`, `updateSettings`, `fetchSourceScenes`, `importSourceScene`,
`fetchCP1Review`.

Do **not** wire these up — that is a separate owner decision (see Q2). But do
tell me which ones your refactor should keep, drop, or move behind a feature flag.

#### 1.8 Backend wiring per view

| View | Backend |
|---|---|
| `top-down` | `GET /workspace/scenarios/{id}/top-down?source=lidar\|radar` — **new, zero backend tests** |
| `sensor-evidence` | `GET /workspace/scenarios/{id}/sensor-evidence?nsweeps=N` |
| `lidar` | `GET /workspace/scenarios/{id}/lidar` + `GET /workspace/lidar/{token}` |
| `third-person` / `in-car` | `GET /frames/{mode}?time_s=`, `GET /image-frames/{mode}`, and live `POST /esmini/live/scenario-pairs` → `GET /esmini/live/sessions/{id}` |
| `wasm-playback` | **none** |

Shared, view-independent: `/timeline`, `/gate-timeline`, `/lineage`,
`/evidence-layers`, `/compare`, `/recipe/*`.

---

### Step 2 — Non-negotiable boundaries. Do not cross these.

1. **Top-down stays the authoring/map/trajectory view.** Do not redefine it.
2. **Sensor Evidence is recorded nuScenes evidence only.** Never describe it as
   regenerated or post-edit sensor output.
3. **Never present recorded data as regenerated post-edit output.**
4. **Unavailable capabilities must stay explicitly unavailable.** A refactor must
   never turn an `unavailable` state into a silently working-looking one. This
   is the single highest-risk regression you can introduce.
5. **Preserve canonical schemas and provenance contracts.**
6. **Keep prediction metrics separate from replay fidelity metrics.**
7. **All provisional metrics stay provisional.** The footer `PROVISIONAL` badge
   is not decoration.
8. **CARLA same-XOSC remains post-MVP.**
9. **No new dependencies or new architecture without an approved decision.**
10. **Do not commit secrets, raw nuScenes data, or derived artifacts.**

---

### Step 3 — Questions you must ask me. Do not guess these.

Mark each clearly in your final report as `BLOCKED ON OWNER` or `DECIDED`.

**Q1 — In-car POV and LiDAR 3D.** They are unreachable from the UI but still
live in `ViewType` and the render tree. **Remove them entirely, or restore them
to the add-view menu?** Note LiDAR 3D has a fully implemented backend and
payload route; In-car POV has `POVFrame` support. Removing them discards working
backend capability.

**Q2 — The 13 dead API helpers.** Batch, Replay, Import, Settings, CP1 review
and live-command all have working backends and no UI. Should this task (a) leave
them dead, (b) wire up a subset, or (c) delete them? **Wiring them is a scope
increase and needs explicit approval.** I lean strongly toward (a) for this task.

**Q3 — MAX_VIEWS = 3.** Is three panels correct? It was four, was reduced to
three without an approval record I can find. Also: is `third-person` the correct
default main pane, or should the default return to `top-down`?

**Q4 — WASM Playback.** It runs a fixture and is not connected to the backend.
**Option A:** visibly label it "fixture / not connected to selected scenario" and
keep it. **Option B:** remove it from the add-view menu until a backend source
exists. **Option C:** you wire it to real scenario data — but that is a new
feature and needs its own approval. I recommend **B** for this task. Confirm.

**Q5 — Renderer ambiguity.** `third-person` silently shows native live state, or
transform preview, or an esmini image artifact. Should the pane **label which
renderer is active**, or should these become **separate view types**? This
changes the add-view menu and probably `MAX_VIEWS`. I lean toward labelling plus
distinct types.

**Q6 — Which unavailable reasons may the refactor change?** Some strings are
user-facing and may be asserted in `frontend/src/workspace.test.tsx`. Tell me
which ones are contract-frozen.

---

### Step 4 — Suggested approach (yours to change if you find better)

1. `git status` / `git diff` first. Establish what is uncommitted and not yours.
2. Run `impact` on `ViewPane`, `AddViewMenu`, `addView`, `resetLayout`,
   `MAIN_VIEW`, `MAX_VIEWS` **before** touching them. Report risk.
3. Propose a **registry-driven** design: one array of view descriptors
   (`{ type, label, icon, renderer, capabilities, availableWhen }`) driving the
   add-view menu, capacity logic, slot labels, and dispatch. This kills 1.1,
   1.2, 1.3 and 1.5 structurally instead of patching them.
4. Give each pane **only the props it uses**. Stop passing 22 props to
   everything.
5. Make the "Start native session" control a **capability** of the view
   descriptor, not a hand-maintained exclusion list.
6. Split `App.tsx`. 1020 lines in one file is part of the messiness. Propose the
   split; do not do a huge refactor without my go-ahead.
7. Keep every unavailable/fail-closed string and status chip behaviour identical.

**Do not attempt this in one enormous commit.** Small, reviewable steps.

---

### Step 5 — Definition of done

- [ ] `MAX_VIEWS`, add-view menu, slot labels and dispatch all derive from one
      registry; no hardcoded slot numbers.
- [ ] No view type is unreachable-but-present.
- [ ] `ViewPane` no longer passes props a pane does not use.
- [ ] The native-session control is descriptor-driven, not an exclusion chain.
- [ ] **Every unavailable state still renders unavailable**, with the same or a
      more specific reason. Verify none silently became a placeholder.
- [ ] WASM Playback is either labelled disconnected or removed — your Q4 outcome.
- [ ] `npm test -- --run` and `npm run build` pass.
- [ ] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` passes.
- [ ] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py` passes.
- [ ] `gitnexus detect_changes` run and reviewed before any commit.
- [ ] Docs updated: `docs/current/project-status.md`, `docs/current/active-work.md`,
      `docs/current/evidence-index.md`.
- [ ] Your report answers Q1–Q6 and lists anything else you need from me.

---

### Current verification baseline (re-measure, do not trust blindly)

Measured 2026-10-16 on the in-flight tree: Python `326 passed`, frontend
`48 passed`, build clean. The frontend count has moved 40 → 48 → 48; treat the
count as unreliable and report the measured value.

Note: **`GET /top-down` has no backend test.** The Python suite passes both with
and without it. Passing tests are not evidence for recorded-evidence behaviour —
only real private-data runs are.

---

### What I most want back from you

1. A **map of every view type → component → props → backend route → button →
   state machine (available / loading / unavailable + exact reason)**.
2. A list of **everything wired wrongly**, with file:line evidence.
3. Your answers to Q1–Q6, and **any question I did not think to ask**.
4. A proposed target structure, small enough to review, before you write it.
5. An explicit list of what you did **not** change and why.

**Ask before you build. It is cheaper than a rollback.**