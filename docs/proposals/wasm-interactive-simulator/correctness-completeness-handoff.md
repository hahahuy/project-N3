# WASM + Data Import: Correctness/Completeness Handoff

Status: `P0 COMPLETE / P2 PARTIAL / PHASE 1 DONE / PHASE 2 IN PROGRESS / UNCOMMITTED`
Written: 2026-10-16, after the Phase 1–2 correctness/completeness increment.

This document hands the Correctness+Completeness phase to the next agent. Read it
together with [`next-agent-handoff.md`](next-agent-handoff.md) (the WASM side-MVP
brief, owner decisions Q1–Q6, and the Q4 open question) and the three analysis
reports in `docs/reports/`:

- `nuscenes-data-exploration-future-integration.md`
- `nuscenes-to-xosc-realsim-coverage-and-metrics.md`
- `xosc-to-wasm-simulator-fidelity-and-data-use.md`

## 1. What this phase is

Phase 1 (correctness) and Phase 2 (scene completeness) add data that makes the
exported XOSC and the WASM playback surface more truthful **without moving the
measured native replay baseline**. The governing rule is:

> Inert metadata and review-only labels are free. Anything that changes
> simulator motion, timing, population, or triggers is a scientific-policy
> change and needs an owner decision.

The analysis that defined the phases lives in the user-provided priority list
(P1–P10), attached to the parent request of this handoff.

## 2. What is done (verify, don't redo)

### Phase 1 — implemented, tested

| Item | Where | Notes |
|---|---|---|
| Actor lifecycle | `src/real2scenario/models.py` (`observed_start_s/end`, `observation_count`, `lifecycle_status()`) | Derived from the recorded track only; descriptive, never motion |
| Trajectory time origin | Entity `Property` entries (`trajectory_time_origin_s`, `trajectory_last_vertex_s`) | Timing semantics unchanged (`position`, `relative`/`offset=0`) |
| Initial-state diagnostics | `recorded_initial_speed_mps`, `initial_speed_policy` properties | Zero `AbsoluteTargetSpeed` preserved — the measured baseline depends on it |
| Source actor properties | Entity `Property` entries | `source_actor_id/type`, frame, replay mode, transform + template provenance |
| Identity/count validation | `Scenario.__post_init__`, `InteractionEvent` | Unique IDs, ego membership, duration coverage, validated event membership |
| Snapshot clock fix | `frontend/src/wasm-playback/worker.ts` (`currentFrame` vs `steppedFrame`) | One `step` = exactly one `0.01` integration; reset is non-advancing |
| Worker-owned clock | Same file + `types.ts` (`play`/`pause`/`step`) | No UI interval or rAF integrator |
| Road-filename fix | Worker `roadFilename()` | Writes the OpenDRIVE under the XOSC-declared filename (fixed the `{excPtr}` real-scenario failure) |

### Phase 2 — partially done

| Item | Status |
|---|---|
| Recorded height + centre offsets drive the XOSC cuboid | Done (`Actor.height_m`, exporter uses real dims, no more `height=1.5` constant) |
| `vehicleCategory` mapping | Done conservatively: bicycle/bus/motorcycle/trailer/truck mapped, unknown stays `car`, source taxonomy preserved |
| Category-specific renderer colors | Done: vehicle vs unknown coloring; selection highlight unchanged |
| Smoke-view actor ledger | Done: `WasmPlaybackView` tracks `first_seen/last_seen/seen_count/status/speed` across frames in a `wasm-scene-ledger` list |
| `trackWasmActors` pure function + test | Done (`frontend/src/wasm-playback/WasmPlaybackView.test.tsx`) |
| Pedestrian/cyclist entity emission | **Not done** — exporter still emits `Vehicle` for all; ingestion selects `vehicle.*` only |
| XODR lane/marking enrichment | **Not done** — map-builder scope, not exporter scope |
| Traffic-light context (P7) | **Blocked**: no recorded signal-state mapping; inferring it is an invented fact |
| Environment (P8) | **Blocked**: `parse_xosc_subset` rejects `/OpenSCENARIO/Environment`; loosening it is a safety decision |
| Interaction events in XOSC (P10) | **Canonical model only** (`InteractionEvent`, derivation-required); no inert validator-approved XOSC representation exists |

## 3. Working tree state (as of this writing)

All work is **uncommitted**. Files touched by this phase:

```text
src/real2scenario/models.py, serialization.py, ingestion.py, exporter.py, __init__.py
tests/test_exporter.py, tests/test_models.py
frontend/src/wasm-playback/types.ts, worker.ts, WasmPlaybackView.tsx,
  ThreePlaybackCanvas.tsx, WasmPlaybackView.test.tsx
frontend/src/wasm-smoke/worker.ts
src/r2s_web/app.py (WASM_PAIR_EXPORTER_VERSION cache key)
docs/proposals/wasm-interactive-simulator/{README,next-agent-handoff}.md
frontend/wasm-esmini/{BUILD,README}.md
docs/reports/nuscenes-*.md, xosc-to-wasm-*.md (new analysis reports)
docs/proposals/wasm-interactive-simulator/correctness-completeness-handoff.md (this file)
```

Two files carry changes **not made by this phase's agent** — confirm authorship
before committing: `frontend/src/styles.css`, `frontend/src/workspace.test.tsx`.

Verification baseline: Python `346 passed` (336 pre-existing + 10 new),
frontend `51 passed`, `npm run build` clean, docs consistency PASS,
`git diff --check` clean. Both fail-closed XOSC validators (`parse_xosc_subset`,
`interpret_xosc_subset`) accept the enriched output.

## 4. The deployment gap you must know about

The `:5173` server observed during this session is **not serving this repo**:

- Vite runs as `node /app/frontend/node_modules/.bin/vite` (a different checkout
  in another mount namespace; `/app` is not visible from this environment).
- Three uvicorn processes exist with two different app modules
  (`src.api.main` vs `r2s_web.app`) and unknown working directories.
- A probe of the served Worker source contained none of the new code.

So none of the Phase 1–2 or clock/protocol fixes are visible at
`http://localhost:5173/wasm-smoke` until that environment is redeployed from
this checkout. Implement in this repo (source of truth), verify here, and treat
redeploy as a separate, explicit step. Do not "fix" the page by editing the
live environment.

## 5. Constraints that still bind (from `next-agent-handoff.md`)

1. WASM stays at `/wasm-smoke`, out of `VIEW_REGISTRY` (Q2). Do not re-add it.
2. Q4 cross-panel focus is **open** — keep `selectedId` local in
   `ThreePlaybackCanvas`; no stores, listeners, or cross-panel props.
3. `followingMode="position"`, per-actor start triggers at first track time,
   `AbsoluteTargetSpeed=0` — do not touch without an owner decision (Q5 parity).
4. Browser output is preview-only; nothing feeds ADE/FDE, gates, reports, or
   `replay.csv` (DEC-018). `InteractionEvent` stays canonical-model-only.
5. No new dependencies without approval (`three@^0.180.0` is the approved set).
6. Run GitNexus `impact` before editing symbols, `detect_changes` before
   committing (project `AGENTS.md` discipline). Pre-edit impact on `Actor`,
   `Scenario`, `build_openscenario_xml`, `extract_scenario`, `scenario_to_dict`
   returned HIGH/CRITICAL — proceed only with additive, default-preserving
   changes and per-item tests.
7. Raw nuScenes data and derived artifacts stay local/private.

## 6. Suggested next increments (small, in order)

1. **Ledger polish + screenshot evidence.** The `wasm-scene-ledger` is new and
   unstyled; add minimal CSS, screenshot fixture + real scenario, record in the
   handoff. No behavior change.
2. **Pedestrian/cyclist entity emission.** Needs: exporter policy for
   `Pedestrian`/`MiscObject` entities, `xosc_subset` acceptance of the new
   entity tags, ingestion selection widening with an explicit owner decision,
   and parity measurement (ADE recompute) before/after.
3. **XODR lane/marking enrichment.** Map-builder work; reference from XOSC only.
   Keep the template path as fallback and provenance-label whichever road is
   served.
4. **End-of-trajectory policy.** Currently hold-at-final-pose by engine default.
   Any stop/hide semantics change native ADE → owner decision + benchmark run.
5. **Traffic/environment/interaction-in-XOSC.** All correctly unavailable; do not
   approximate. Revisit only with a recorded source mapping (signals),
   a validator change (environment), or an approved inert representation
   (interaction events).

## 7. What to report back

1. Phase 1 re-verification (tests + both fail-closed validators).
2. Phase 2 ledger behavior on fixture vs a real scenario (active/ended counts).
3. Anything in §2 marked done that no longer holds.
4. An explicit statement that no browser-derived number reached a report,
   metric, gate, or `replay.csv`.
5. The deploy state of `:5173` — which checkout it serves and whether this
   repo's changes are live there.

**Build in the order above; never let a browser number reach a report.**

## 8. Addendum 2026-10-16 — ledger polish (increment 1, CSS-only)

- Added minimal `.wasm-scene-ledger` styling in
  `frontend/src/wasm-playback/playback.css` (list layout, `max-height: 120px`
  scroll, `data-status="ended"` dimming). No markup, protocol, or
  `trackWasmActors` semantics changed.
- Verified: Python `346 passed`, frontend `51 passed`, `npm run build` clean,
  docs consistency PASS, `git diff --check` clean. Both fail-closed validators
  (`parse_xosc_subset`, `interpret_xosc_subset`) accept the enriched export.
- `detect_changes --scope all`: 69 changed / 113 affected, risk CRITICAL —
  unchanged pre-existing footprint from Phase 1–2 touches on `Actor`,
  `Scenario`, `build_openscenario_xml` (HIGH/CRITICAL per AGENTS.md); this
  increment adds no symbol change.
- Screenshot evidence deferred: `:5173` still serves `/app` (different
  checkout, `node /app/frontend/node_modules/.bin/vite`), not this repo — same
  deployment gap as §4. Ledger fixture behavior (1 ego actor, always active) and
  lifecycle unit test (2→1 active + 1 ended, `seen_count` increment) hold; no
  live real-scenario screenshot taken so as not to edit the live environment.
- Pedestrian/cyclist emission NOT started (population change: needs exporter
  `Pedestrian`/`MiscObject` policy + `xosc_subset` tag acceptance + ingestion
  widening beyond `vehicle.` prefix + owner decision + ADE parity recompute).
  XODR/traffic/environment/interaction-in-XOSC remain correctly unavailable.
