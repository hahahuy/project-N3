# Data Analysis Handoff — Pedestrian/Cyclist Emission Widening

Status: `UNCOMMITTED / OWNER-APPROVED 2026-10-16 / ANALYSIS REQUESTED`
Written: 2026-10-16, immediately after the approved implementation increment.
Read with: [`correctness-completeness-handoff.md`](correctness-completeness-handoff.md)
(§2 Phase 2 table, §5 constraints, §7 report-back) and
[`next-agent-handoff.md`](next-agent-handoff.md) (Q1–Q6, DEC-018 boundary).

## 1. What changed and why you are receiving this

The owner approved pedestrian/cyclist emission plus ADE parity recompute
(2026-10-16). The implementation is done and **uncommitted** in the working
tree (8 files). This handoff asks the data analysis team to (a) verify the
new data update with measurements the implementation environment cannot
produce, and (b) take on the hard analyses blocking WASM, correctness/
completeness, and future missions.

| Change | File | Notes |
|---|---|---|
| Entity-tag routing | `src/real2scenario/exporter.py` | `human.*` → `Pedestrian`, `vehicle.*` → `Vehicle` (byte-identical move), else → `MiscObject` (`other`) |
| Selection widening | `src/r2s_web/source_scenes.py` | `vehicle.` + `human.` tokens merged; error message updated |
| Candidate counts | `src/r2s_web/schemas.py`, `frontend/src/api.ts`, `source_scenes.py` | New `pedestrian_candidate_count` (default `0`, additive) |
| Cache invalidation | `src/r2s_web/app.py` | `WASM_PAIR_EXPORTER_VERSION` `v2` → `v3` — old cached pairs regenerate |
| Overlay wording | `frontend/src/wasm-playback/ThreePlaybackCanvas.tsx` | "vehicle" → "actor" (selection can now be a pedestrian) |
| Tests | `tests/test_exporter.py`, `tests/test_web_api.py` | Pedestrian/MiscObject tags, validator acceptance, API field |

Verification the implementation team already holds: Python `348 passed`
(346 + 2 new), frontend `51 passed`, `npm run build` clean, docs consistency
PASS, `git diff --check` clean. Both fail-closed validators accept the new
tags with **zero validator changes** (they are entity-type agnostic — off
`ScenarioObject/@name`, Init teleports, ManeuverGroups). Impact analysis was
CRITICAL on `build_openscenario_xml` (9 upstream, 8 processes) and
`extract_scenario` (16 upstream); the increment proceeded under explicit owner
approval with additive, default-preserving edits only.

## 2. Ground facts (measured, local mini release — 10 scenes)

- Instance population: **476 vehicle + 227 human**; **9/10 scenes** contain ≥1 pedestrian.
- Full routing table from `data/v1.0-mini/v1.0-mini/category.json` (23 categories):

| Route | Categories |
|---|---|
| `Vehicle` (12) | `vehicle.bicycle`, `bus.bendy`, `bus.rigid`, `car`, `construction`, `emergency.ambulance`, `emergency.police`, `motorcycle`, `trailer`, `truck` (+ `vehicle.ego` synthetic, + conservative `car` default for unknowns) |
| `Pedestrian` (7) | `human.pedestrian.adult`, `child`, `construction_worker`, `personal_mobility`, `police_officer`, `stroller`, `wheelchair` |
| `MiscObject/other` (5) | `animal`, `movable_object.barrier`, `debris`, `pushable_pullable`, `trafficcone`, `static_object.bicycle_rack` — note: **selected by nobody today** (selection is `vehicle.*` + `human.*` only); reachable solely via explicit API token selection |

- Cyclists need no new handling: nuScenes annotates rider+bicycle as
  `vehicle.bicycle` (already `Vehicle`/`bicycle` since Phase 2).
- Per-scenario actor cap is unchanged (`max_actors=3`, exporter allows 1–3
  non-ego): pedestrians now **compete** with vehicles for the same slots via
  distance/TTC ranking.

## 3. Analyses requested on this update (in order)

**A1 — Vehicle-population ADE parity (confirm, don't re-derive).**
Claim: vehicle-only XOSC output is byte-identical to pre-widening output (the
`Vehicle` branch is a verbatim code move), so native esmini input — and hence
the measured baseline (ADE mean `0.0411 m` @ `dt 0.01`) — is unchanged.
Acceptance: export the same scenario with the pre- and post-change exporter,
`diff` the XML (expect empty), and state the ADE recompute is vacuous by
construction. If the diff is non-empty, stop and return the diff — that is a
defect, not a measurement.

**A2 — Pedestrian-inclusive native replay ADE/FDE.**
Acceptance: on an esmini-equipped machine, take pedestrian-inclusive scenarios
from the **wide index** (mini-10 is methodologically too small — see §7), run
native replay at `--fixed_timestep 0.01`, and report per-category ADE/FDE
(vehicle actors vs pedestrian actors separately — never a blended number).
Flag specifically: do pedestrians converge onto position-following as cleanly
as vehicles, or do they show the short-track convergence failure that Q6
describes for vehicles? **Version rule:** record the exact engine version with
every number. Native here is 3.9.0 while esminiJS is 3.10.0 (§7) — any
WASM↔native comparison must use version-matched runs, and a vehicle-only
re-run on the A2 engine is required to confirm the `0.0411 m` baseline still
holds on that engine (A1 proves identical *input*, not an identical
*engine*).

**A3 — Selection displacement.**
Pedestrians now compete for 3 slots. Acceptance: across the 10 mini scenes,
report (i) how often a pedestrian displaces a vehicle from the selected set
vs the old vehicle-only ranking, (ii) distance/TTC distributions of selected
pedestrians vs selected vehicles, and (iii) any scene where import now fails
(`<2 actors`) or succeeds where it previously failed. If displacement
systematically drops the highest-risk vehicle, propose a quota or weighting
— as a proposal with acceptance bar, not an implementation.

**A4 — esminiJS (WASM) handling of the new tags. → DONE BY WASM TEAM 2026-10-16.**
Parse verdict: **yes** — engine 3.10.0 (`v3.10.0-0-06065f9`) inits and
`step_frame(0)`s the pedestrian fixture with 3/3 objects, no crash
(`node frontend/wasm-esmini/smoke.mjs
frontend/src/wasm-smoke/fixture-pedestrian.xosc
frontend/src/wasm-smoke/smoke.xodr`; vehicle fixture still 1/1 with the
P0 counts 2 lane surfaces / 2 road marks). Engine strings: **`type` and
`kind` come back empty for every object, including the ego vehicle** — so no
`pedestrian` kind/color is possible from engine strings; identity must come
from `name`, and the renderer correctly buckets everything as `unknown`
(gray) until a name→taxonomy mapping exists (that mapping is the Q4
identity-key problem — not invented here). Browser-side visual confirmation
of the pedestrian fixture is still owed (deploy gap, §7 of the correctness
handoff). Side fix in the same increment: `smoke.mjs` previously hardcoded
`/road.xodr` (every run died with an opaque `{excPtr}`) — now derives the road
filename from the XOSC `LogicFile`, mirrors the browser `vectorItems`
helper for Emscripten vectors, and reports per-object tags.

**A5 — MiscObject policy.**
Acceptance: recommend (i) keep `other` for all, (ii) map specific categories
(e.g. `movable_object.barrier` → `barrier`), or (iii) reject non-vehicle
non-human at export (fail-closed). Include what esmini actually does with each
`MiscObjectCategory` value — an untested mapping is an invented fact.

**A6 — Mass/dimension defaults audit. → PROTOCOL DELIVERED 2026-10-16, ready to execute.**
`Pedestrian mass=75`, `MiscObject mass=0`, and the bbox fallback scales are
documented-as-inert defaults for position following. Run the protocol below on
native 3.10 (`export ESMINI_BIN="$HOME/esmini-3.10/bin/esmini"`
`ESMINI_DAT2CSV="$HOME/esmini-3.10/bin/dat2csv"`); it decides the claim by
construction, no statistics needed.

*Why this design is decisive:* same binary + same XOSC except the `mass`
attribute ⇒ if mass enters the computation anywhere, the trace must differ;
if all traces are byte-identical, mass provably steers nothing on this path.
One load-bearing subtlety: the test trajectory **must contain acceleration**
(a constant-speed straight line is insensitive even to a mass-aware
controller), hence the track criteria in step 1.

1. **Pick tracks.** One real pedestrian track: duration ≥ 10 s, speed range
   spanning ≥ 1 m/s (must include accel/decel or a curve), stable dimensions.
   One static misc object (cone/barrier). Export once via the repo exporter
   (`write_openscenario` stages the XODR alongside) to `/tmp/opencode/a6/`
   as `base.xosc`. Fallback with no dataset: author a synthetic pedestrian
   with an accelerate–cruise–decelerate speed profile (≥ 10 vertices);
   constant-speed lines are explicitly invalid for this test.
2. **Determinism gate (do not skip).** Replay `base.xosc` twice to two trace
   paths (`run_esmini` + `dat2csv` via `EsminiConfig`, `fixed_timestep_s=0.01`,
   headless). `diff` the two CSVs: empty ⇒ proceed; non-empty ⇒ STOP, the
   experiment is invalid — report run-to-run variance instead.
3. **Single-variable variants.** From `base.xosc`, change nothing but `mass`:
   `walk1` Pedestrian `75` → `750` (plausible, non-degenerate); `cone1`
   MiscObject `0` → `100`. E.g.:
   `root.find("./Entities/ScenarioObject[@name='walk1']/Pedestrian").set("mass", "750")`
   (same for the misc object), re-serialized with identical indent/decl.
   Vehicles carry no `mass` attribute — out of scope, note it.
4. **Replay each variant** (same engine, `dt 0.01`) and
   `compute_scenario_replay_metrics` per actor for the ADE/FDE table.
5. **Decide by this table:**

   | Observation | Verdict |
   |---|---|
   | Traces byte-identical across masses (gate passed) | Mass inert under position-following, native 3.10, tested class — assumption HOLDS |
   | Diff non-empty | Assumption FALSE — report max vertex displacement, which actor(s), longitudinal vs lateral; escalate, do not change defaults |
   | Engine crash on `mass=0` (misc) | Mass enters some code path (≥ validation) — not proven; retest misc `1` vs `100` and report |
   | Gate fails | Invalid run — report variance, no verdict |

   Scope limits (explicit, not footnotes): native 3.10 only;
   `FollowTrajectoryAction` + `position` only; WASM-engine repeat is a
   separate follow-up, not required here; no claim about other controllers,
   triggers, or collision dynamics. Total cost: 8 short replays
   (2 levels × 2 runs × 2 tags).

## 4. Harder analyses wanted (beyond this update)

These are the open hard problems. Take any; each needs the same rigor as
§3 (measured numbers, acceptance bar, no invented facts).

1. **Pedestrian Q6-analog.** Q6 settled that short-track exclusion stays off
   for vehicles (`dt 0.01` residual `0.0411 m`). Redo the convergence analysis
   for pedestrian tracks specifically: Keyframe-fragment rates, residual vs
   track length, and whether esmini's pedestrian controller differs from its
   vehicle position-following. Verdict wanted: does any exclusion ever apply
   to pedestrians, or is the population rule uniform?
2. **WASM↔native fidelity gap inventory.** Beyond `dt` (settled at `0.01`):
   enumerate every remaining known divergence between esminiJS-in-browser and
   native esmini 3.9.0 on identical XOSC (controller, triggers, end-of-track
   hold, entity-ID stability across `reset()`). Rank by effect on a future
   correlation claim. The end-of-trajectory hold-at-final-pose policy (§6.4 of
   the correctness handoff) is item one on this list.
3. **Completeness remainder.** XODR lane/marking enrichment (map-builder
   scope, reference-from-XOSC with provenance labeling), traffic-light context
   (P7 — needs a recorded signal-state mapping; absence of one IS the
   finding), environment (P8 — validator change is a safety decision), and an
   inert validator-approved representation for interaction events (P10).
   For each: what exists, what is blocked on what decision, and the cheapest
   truthful increment.
4. **Sensor-fusion feasibility (Q3).** Render recorded nuScenes sensor
   evidence next to WASM actors. Needs: timestamp alignment between the
   worker-owned `0.01` clock and `LIDAR_TOP` sweep times, `reset`+reintegrate
   seek (Q5 condition), and the engine↔canonical identity-key mapping (the Q4
   problem). Size the work and name the load-bearing unknowns.
5. **Cross-panel identity key (Q4 input).** Measure engine entity-ID stability
   across `reset()` in esminiJS: are IDs stable, re-derived, or garbage after
   reset? Your answer determines whether Q4's key mapping is "cache once" or
   "re-derive every reset".

## 5. Constraints that bind your analysis (non-negotiable)

1. Browser/WASM output is preview-only and must **never feed ADE/FDE,
   `replay.csv`, gates, or reports** (DEC-018). Your numbers come from native
   esmini or are labeled diagnostic.
2. If WASM and native disagree, **native is authoritative** — never present a
   browser frame as a native artifact.
3. **Unavailable = shown as unavailable.** No placeholder that reads as success.
4. Raw nuScenes data and derived artifacts stay **local/private**.
5. An answer of the form "sync the panels" / "pedestrians look fine" is
   insufficient — every verdict needs its acceptance bar and the numbers
   behind it. Send back anything vaguer for rework.

## 6. What to return

1. A2 numbers (per-category ADE/FDE table + machine/esmini version) or an
   explicit statement they are still unmeasured and where to run them.
2. A1 diff result (empty or the defect diff).
3. A3 displacement report + recommendation (proposal only).
4. A4 engine strings + parse verdict for `Pedestrian`/`MiscObject`.
5. A5 + A6 verdicts with mechanisms cited.
6. For any §4 item taken: measurements, ranking, and the cheapest truthful
   next increment with its own acceptance bar.
7. Anything in §2 you measured differently — ground facts are versioned, not sacred.

## 7. Addendum 2026-10-16 — data-team reply + toolchain inventory

**A1 ✅ VERIFIED by data team:** 40/40 XOSC files byte-identical pre/post
widening (`EMPTY_DIFF__ADE_RECOMPUTE_VACUOUS`), done via `git worktree`
without touching the working tree. Vehicle baseline `0.0411 m` stands **by
construction for identical engine** (see the version rule in A2).

**Agreed plan:** A3 first (cheap, pure Python, answers the displacement
safety question), then A2 on the wide 850-scene index with per-category
tables and reported n sizes — no verdicts from statistically small n.
A4 claimed by WASM team. A6 mass-swap experiment: data team designs to the
acceptance bar, runnable natively (see below); their along-track-residual
observation is noted but explicitly **not** accepted as A6 evidence
(cross-track cleanliness does not prove longitudinal mass-independence).

**Toolchain inventory (this environment):**
- Native esmini **3.9.0 DELETED by owner order 2026-10-16** (was
  `~/esmini/bin/esmini` + `dat2csv`, `v3.9.0-0-efbf7ee1`) — done so future
  agents cannot mistake it for the 3.10 line. **No native runtime remains
  here, and no `ESMINI_BIN`/`ESMINI_DAT2CSV` was ever exported.** The 3.9.0
  smoke numbers below stand as a recorded measurement, not a rerunnable setup.
- esmini **3.10.0 exists as source only** (sibling `github/esmini` checkout @
  `06065f9`, unbuilt, no `dat2csv`). Repo-wide hunt found no 3.10 binary or
  `libesmini*` anywhere (only `/opt/esmini` mount references in compose/docs,
  which does not exist in this environment).
- esminiJS **3.10.0 WASM build present** (`frontend/wasm-esmini/dist/esmini.js`).

**Tracked task — build native 3.10 binary → DONE 2026-10-16.**
Built from the sibling source @ `06065f9` with the slim flags
`USE_OSG/SUMO/OSI/GTEST/IMPLOT/PROJ=OFF, BUILD_ODRPLOT/REPLAYER/EXAMPLES=OFF`
(headless `esmini` + `dat2csv` need no OSG; configure 90 s, full build 81/81
targets on 12 cores). Toolchain: cmake 4.3, GCC 16, Ninja (all stock Fedora;
no sudo needed — externals auto-download, unused ones ignored).
Staged at `~/esmini-3.10/bin/` (`esmini`, `esmini-dyn`, `dat2csv`,
`libesminiLib.so`, `libesminiRMLib.so`; `ldd` clean), build version
`project-N3-3.10.0-local`. Acceptance: `--version` → `v3.10.0-0-06065f9`,
esmoke replay (ego+pedestrian+cone, `dt 0.01`) exit 0 with coverage
`complete` on all 3 actors (ego ADE `0.0200`/FDE `0.0400`, walk1
`0.0050`/`0.0100`, cone1 `0.0000` m — pipeline sanity, n=2, not a baseline).
**Version skew resolved:** native 3.10 now version-matches the esminiJS 3.10.0
engine — A2 runs on this binary; the vehicle-only same-engine re-run for the
`0.0411 m` baseline check still applies. Enable per the README convention
(shell config only, never committed):
`export ESMINI_BIN="$HOME/esmini-3.10/bin/esmini" ESMINI_DAT2CSV="$HOME/esmini-3.10/bin/dat2csv"`.

**Version-skew caveat (binding until resolved):** native runs here are 3.9.0;
the browser engine is 3.10.0. Never compare 3.9.0-native numbers against
3.10.0-WASM frames as if version-matched. Options, cheapest first: (i) keep
native 3.9.0 for A2 and label all WASM↔native deltas version-confounded;
(ii) build native 3.10 from source (needs OSG toolchain — size before
attempting); (iii) point to an existing 3.10 binary if one is available.

**Native smoke 2026-10-16 (3.9.0, synthetic ego+pedestrian+cone, 2 s, `dt 0.01`,
headless, `/tmp/opencode/esmoke`, not committed):** exit 0, `Pedestrian` and
`MiscObject(other, mass=0)` parsed and replayed, coverage `complete` for all
3 actors (ego ADE `0.0200`, walk1 `0.0050`, cone1 `0.0000` m — pipeline
sanity only, n=2 vertices is **not** a convergence result and does not
replace A2). Partial A5-native-acceptance: 3.9.0 does not reject the new
tags; full A5 semantics verdict still open.
   sacred.
