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

## 9. Addendum 2026-10-16 — smoke reorg for tag widening (owner-requested)

`frontend/src/wasm-smoke/` reorganized so every remaining WASM check is
runnable (see `frontend/src/wasm-smoke/README.md` for the full procedure):

- `fixture.xodr` renamed to `smoke.xodr` so the file matches the XOSC-declared
  `LogicFile` name (2 refs updated, no behavior change).
- New `fixture-pedestrian.xosc`: ego `Vehicle` + `walk1` `Pedestrian` +
  `cone1` `MiscObject(other)`, init-only, sharing `smoke.xodr`.
- P0 probe (`worker.ts`) now runs **both** fixtures and reports per-object
  `name`/`type`/`kind`; page renders both results plus a fixture picker
  (vehicle / pedestrian / real scenario) for the playback preview.
  `WasmPlaybackView` gained an optional `fixture` prop (default `"vehicle"`).
- `frontend/wasm-esmini/smoke.mjs` fixed: road filename derived from the XOSC
  `LogicFile` (hardcoded `/road.xodr` failed every run with `{excPtr}`),
  Emscripten-vector helper mirrored from the browser workers, per-object tags
  reported, constructor `dt` aligned to `0.01` (Q5).
- Measured via the fixed harness (engine 3.10.0): pedestrian fixture yields
  3/3 objects; `type`/`kind` are empty for all objects — recorded in the data
  handoff (A4 done). Frontend `51 passed`, build clean, Python `348 passed`.
- Browser-side visual confirmation of the pedestrian fixture is still owed —
  deploy gap (§4) unchanged. Nothing here touches the live environment.

## 11. Addendum 2026-10-16 — attribute/road panel + fixture trajectory (owner-requested check)

So the owner can verify XOSC↔XODR correspondence on `/wasm-smoke` for any
scenario (fixture or real wasm-pair):

- `WasmPlaybackView` shows a "Scenario attributes" panel parsed from the
  already-fetched XOSC text (display-only, never a motion path): declared
  `LogicFile` vs served lane-surface/road-mark counts, plus per-entity tag,
  category, mass, bbox and Properties. Unknown tags/attrs render as `—`.
- `fixture-pedestrian.xosc` now carries `Properties` on all actors, per-actor
  `ManeuverGroup`s (exporter-style; one shared group would apply a private
  trajectory action to every actor), and a 3-vertex `FollowTrajectoryAction`
  for `walk1`. Verified in-engine (primed): walk1 tracks vertices, ego holds
  SpeedAction 5 m/s, cone static; P0 probe counts unchanged (it steps once).
- Fixture lesson recorded in `wasm-smoke/README.md`: Act `StartTrigger` with
  `rule="greaterThanEqual"` never fires in esminiJS (same frozen symptom as
  the missing prime) — fixtures use `greaterThan` like the exporter, which
  never emits `greaterThanEqual`, so production exports cannot hit this.
- Frontend `56 passed`, build clean. The correspondence check itself
  (looking at the panel on the live page) still needs the redeployed
  environment — procedure in `wasm-smoke/README.md`.

## 15. Addendum 2026-10-17 — 1x playhead-synced cloud + atomic artifact writes

LiDAR overlay v2 (owner asked 1x + continuous): new `GET
/api/workspace/scenarios/{id}/lidar-sweeps` lists the play-range sweeps
oldest-first (forward `sample.next` walk — the existing evidence endpoint
only covers pre-start history), 39 sweeps / 0.5 s stride / 19.15 s on
scene-0061. Browser prefetches a ≤24-sweep stride at full density in the
background and shows the latest sweep at or before the playhead (never the
future); the label always names sweep t and Δ. Verified live t=18.41 →
sweep t=18.05 (Δ0.36 s), 0 console errors.

excPtr true root fix: two overlapping wasm-pair POSTs (dev StrictMode
double-mount writes the same pair path twice) served 561 KB-of-3.9 MB and
0-byte reads — the XML gate only named it. All pair writes are now atomic
(tmp + rename): `exporter.atomic_write_bytes` (also covers xosc + staged
template copy for all 5 callers, bytes identical) + both app.py road writes.
Threaded test proves partial reads with direct writes (caught 0/104KB/
204KB) and none with rename. Python 365 passed (byte-identical holds),
frontend 59 passed, build clean.

## 14. Addendum 2026-10-17 — reset re-prime, overlays, follow-lock, artifact gate

Reset freeze (owner-reported): after any reset, ego held x=0.00 speed=0.00
forever while trajectory actors resumed. Root cause is the same missing-prime
class as construction — `reset()` restores teleports but Init-phase triggers
(ego SpeedAction) never refire. Fix: `resetEngineScenario` (reset + zero-step
re-prime) in the worker reset path; measured x=8.78 speed=8.75 at t=1.00 with
it. Unit-locked (`reset → step:0` call order).

excPtr root cause (owner-reported, reproduced on scene-0061): NOT malformed
generation — the browser received 561 KB of a 3.9 MB OpenDRIVE (cut
mid-attribute by the dev proxy; backend bytes verified well-formed).
esmini died parsing it → opaque `{excPtr}`. Fix: `assertWellFormedXml`
gate + one automatic refetch before engine handoff, human error otherwise.
No backend change.

Overlays (checkboxes, display-only, real scenarios only — fixtures have no
recorded source so boxes stay disabled): exact-cuboid wireframes instead of
skins (shared unit edges, recorded dims, selection raycast covers both);
recorded travel polylines + heading cones from workspace `paths` (~8
glyphs/path); one static LIDAR_TOP sweep (decimation 8, ~4.3k points) through
sensor→ego→global→local chain re-derived in TS (verified: ego_pose z=0
datum, ground returns ≈ surface, cloud aligns on screen). Missing pieces
resolve to null, never invented.

Follow-lock: selecting an actor (canvas click) anchors the orbit; per-frame
deltas move camera + target together through play/step, user offset
preserved; empty click / Reset View releases. Feet-on-road fix from §13
follow-up also in: group origin lifted by half recorded height + asphalt
lift (was: centered at h=0, wheels sunk).

Layout fix: `.three-playback-shell` min-height 280px — the absolute canvas
(buffer floor 280) overflowed a 239px shell and covered the new checkboxes
(plus, latently, the controls row). Verified live: all 3 overlays on,
follow through t=15.6s, 0 console errors. Frontend 62 passed, Python 363
passed, build clean.

## 13. Addendum 2026-10-16 — semantic ground underlay (owner-approved)

`GET /api/workspace/scenarios/{id}/ground-layers` serves nuScenes
map-expansion polygons (`drivable_area`, `walkway`, `ped_crossing`,
`carpark_area`) for the scenario actor bbox + 40 m, already moved into the
local frame with the exact trajectory math (verified: actor bbox inside
ground bbox; scene-0061: 37 polygons = 3 drivable + 24 walkway + 10 crossing,
755 verts, 33 KB, 0.2 s; actors x[0,68.6] y[0,35] inside drivable
x[-58.7,135.2] y[-58.7,114.9]). Hard lesson: devkit `get_map_geom`
returns patch-relative offsets, not map-global coords — vertices must be
rebased onto the patch center before `to_local_state`, else ground lands
~1.2 km away (seen: drivable x[1156,1350]). Guarded by a test asserting
actor-bbox-inside-drivable, proven to fail on the old math. The browser draws them as flat
ShapeGeometry fills under the lane ribbons (drivable darkest, crossings
lightest). Display-only, best-effort (missing ground never breaks playback),
unavailable-envelope on failure like sensor-evidence. OSM verdict: rejected
as road geometry (crowd-sourced meter data + SUMO guessing would downgrade
survey maps and add a heavy dep; SUMO cannot emit OSM anyway); OSM
buildings/landuse remains an optional labeled-context follow-up, not needed
for road completeness. Frontend `57 passed`, Python `363 passed`.

Renderer-only, zero sim/metrics impact. Actors are procedural low-poly skins
(car body+cabin+wheels, pedestrian torso+head, cone, plain box for unknown)
in unit space, scaled to the exact recorded cuboid per the unclamped rule —
footprints never lie; shapes are documented schematic, real numbers stay in
the attributes panel. Roads are merged asphalt ribbons from recorded lane
boundaries + edge lines + recorded road marks (marks were fetched but never
drawn until now). Completeness boundary: everything the data provides, nothing
invented — no lane markings where unrecorded, no shoulders/sidewalks/textures.
No new dependencies. Like every WASM UI increment on this track, shipped
without browser-visual confirmation (deploy gap §4); suite + build green.

## 12. Addendum 2026-10-16 — full-map cover replaces local corridor (decision)

Measured on the HDD dataset (`/mnt/backup/nuscenes`, all 4 expansion maps
present; devkit 1.2.0 pinned; builder already devkit-backed so there is
nothing to "replace with devkit" — see data handoff):

| Map | Lanes+connectors | Roads | Unsupported | Junctions | Build | esmini load+run |
|---|---|---|---|---|---|---|
| boston-seaport | 1215+1631 | 2846 | 0 | 1627 | 2.9 s | 0.6 s, exit 0 |
| singapore-hollandvillage | 601+719 | 1320 | 0 | 717 | 0.9 s | 0.3 s, exit 0 |
| singapore-onenorth | 936+1066 | 2002 | 0 | 1065 | 1.4 s | 0.4 s, exit 0 |
| singapore-queenstown | 910+1173 | 2083 | 0 | 1165 | 1.3 s | 0.4 s, exit 0 |

WASM parses the biggest map (2002 lane surfaces) in ~1 s via `smoke.mjs`
(browser frame-rate with ~4000 line objects still unmeasured — check on
redeploy before defaulting). Builder emits no road marks (cosmetic gap).

**Decision: default to per-map full cover, retire corridor usage for new
scenarios** (corridor code+tests stay — audit trail, no deletion). Why:
no crop boundary by construction (kills dangling refs, closure heuristics,
intersect policy as a class); build once per map (1–3 s, cache by
map+builder-version+params) instead of per scenario; full map is literally
"the scene's own map". What full map does NOT solve: the global→local frame
transform (still required — maps are global, trajectories local), provenance
wiring, ADE re-proof, and the owner decision for the environment change.
Proposed wiring: per scene resolve `location→map_name`, reference the cached
full XODR as `LogicFile`, record `map_reconstruction_mode` + builder version
in provenance. Re-proof bar: template-vs-fullmap ADE (expect ~nil),
primed-WASM fidelity re-run on a full map, render perf check.

**WIRED 2026-10-16 (owner-requested):** `/wasm-smoke` now serves the scene's
own full map. `transform_opendrive_to_local` (exact rigid motion, round-trip
tested) moves global-frame plan geometry into the scenario local frame —
without it actors would sit kilometres off the roads. `select_full_scene_map`
names the declared `LogicFile` + records provenance (exporter accepts with
zero special cases; `staged_path` override feeds staging). The wasm-pair route
tries full-map first and falls back to template on any failure (missing map
never breaks preview), with a per-path `map_warning` so the UI never
mislabels which road is served. Scene `location` is the map name (identity,
verified across trainval).

**Re-proof (native 3.10 + primed WASM, scene-0061 + scene-0047):** template
vs fullmap ADE **identical to 4 decimals on all 8 actor-tracks**
(0061: 0.0465/0.0468/0.0186/0.0335 both; 0047: 0.1005/0.0028/0/0 both);
primed-WASM on fullmap matches its template numbers exactly
(ego 0.0477, peds 0.0003/0.0010, truck 0.0008); both validators accept;
stderr clean. Map change is replay-inert on the measured set — as predicted
by the refuted map causation, now proven per scenario. Browser frame-rate
with ~2000 lane surfaces is the one unmeasured item (needs the redeployed
environment).

**Data provisioning DONE 2026-10-16 (owner-ordered):** `data/v1.0-subset80/`
(gitignored), 80 scenes = 35 quota scenes + stratified fill (30 boston / 27
onenorth / 15 queenstown / 7 hollandvillage): metadata subset 56 MB, 4 map
expansions + PNGs, LIDAR keyframes + sweep history (≤20 back), RADAR kf +
sweeps, can_bus subset — ~23 GB total, 0 missing files. Excluded by measurement
(no reader in `src/`): CAM payloads, lidarseg/panoptic. Verified: index builds
(80 scenes), devkit map loads, import works, `sensor-evidence` returns full
sweep history (5/4 and 20→11 on a mid-scene sample), pre-imported all 80
scenarios + prebuilt 4 full-map XODRs (`reports/maps/`, ~12 s). Mini payloads
(`samples/`, `sweeps/`, 5.1 GB) deleted, metadata kept — suite unaffected.
Dev convention: `NUSCENES_ROOT=data/v1.0-subset80 NUSCENES_VERSION=v1.0-subset80`
(shell only). Cache: distinct version name ⇒ fresh sqlite auto-builds,
signature-gated; no manual reinit needed. Name-collision note: mini and
trainval share scene names (`scene-0061` exists in both) — artifacts collide
by filename, provenance `dataset_version` disambiguates.

## 10. Addendum 2026-10-16 — WASM engine measurements (Node harness, `/tmp` only)

Version-matched run: native 3.10.0 vs esminiJS 3.10.0 (`-06065f9` both sides),
synthetic 6 s scenario (ego vehicle + accel-profile pedestrian + static cone,
13 vertices), `dt 0.01`, same repo-exported XOSC. No repo production code
changed; scripts live in `/tmp/opencode/wasmcorr/` (not committed).

**Finding 1 — unprimed engine never starts events (bisect V0–V5).** Init
Teleports/SpeedActions apply (fixture ego drives at 5 m/s), empty maneuvers
tolerated, storyboard StopTrigger fires (time froze at 6.01 past duration) —
but no Maneuver Event ever executes: not with `edge none`, not with `rising`,
not triggerless, not even a non-trajectory SpeedAction event. All actors hold
at teleports, speeds read 0. Practical meaning: trajectory playback — the
WASM premise — currently shows frozen actors for any real/wasm-pair scenario
(SpeedAction-only motion like the fixtures still animates).

**Finding 2 — root cause: missing zero-prime frame.** Native
`ScenarioPlayer::Init()` ends with `Frame(0.0)`; the esminiJS constructor
never issues one, and with a `dt: 0.01` config `step_frame(0)` resolves to
0.01 (never 0 — the earlier "zero-first" triage was a false negative).
Verified: construct with `dt: 0`, one `step_frame(0)` (sim time stays 0),
then step normally — ego speed reads recorded 4.0 at t=0.01, x=3.96 at t=1.

**Finding 3 — primed fidelity (first version-matched numbers, diagnostic only):**

| Actor | ADE native | ADE primed-WASM | Scale |
|---|---|---|---|
| ego | 0.0369 | 0.0400 | mm-level Δ |
| walk1 (ped, accel profile) | 0.0159 | 0.0107 | cm-level Δ |
| cone1 (static) | 0.0000 | 0.0000 | identical |

(WASM FDE n/a is a fencepost artifact — run ends 5.9999 < recorded 6.0 — not
a divergence. Never feed these to a report; DEC-018 holds.)

**Finding 4 — Q4/reset input.** `reset()` restarts the clock (0.01→0.50
verified), engine ids `[0,1,2]` + names stable across reset, reset[0]
positions == run[0]. For this build, cache-once identity mapping is viable;
re-derive-per-reset is not required — but this is one scenario, not a proof.

**Finding 5 — end-of-track data point (corrected 2026-10-16).** The earlier
"hold-at-final-pose" wording was imprecise. Measured on both engines with the
pedestrian fixture (story runs to t=10, walk1 trajectory ends t=2): past the
last vertex the actor **extrapolates with last velocity** (native and WASM
agree: walk1 x=7.98@2.5, 12.98@5.0). What froze in the 6 s scenario was the
*simulation itself* at the story StopTrigger (time halted at 6.01), not a
per-actor hold. So: stop-at-duration halts the sim (both engines); running
story + exhausted trajectory extrapolates (both engines). No stop/hide
semantics observed anywhere. §6.4's "hold by engine default" is superseded by
this paragraph; any policy change stays owner-gated.

**Fix IMPLEMENTED 2026-10-16 (owner-confirmed (1)):**
`frontend/src/wasm-playback/worker.ts` init now constructs with
`dt: ENGINE_PRIME_DT` (= 0) and calls `primeEngineScenario()` once before
serving `ready`; the `0.01` play/step protocol is untouched (`FIXED_DT`
moved to `types.ts` unchanged). Zero sim-time advance, no exporter/native
impact, browser-only. Locked by a unit test (single true-zero step;
prime = 0 / fixed = 0.01 constants) — frontend `53 passed`, build clean.
Post-fix behavior was pre-verified by the construction-identical Node run
above (primed ADE table). Browser-side visual + any Q2/correlation
discussion still gated on redeploy + review, not on further code.
