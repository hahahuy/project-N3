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

**A2 — Pedestrian-inclusive native replay ADE/FDE (the measurement this environment cannot make).**
No `ESMINI_BIN` exists here, so no native run was possible. Acceptance: on an
esmini-equipped machine, take ≥1 pedestrian-inclusive scenario (e.g. mini
`scene-0061`: 29 vehicles / 60 pedestrians), run native replay at
`--fixed_timestep 0.01`, and report per-category ADE/FDE (vehicle actors vs
pedestrian actors separately — never a blended number). Flag specifically:
do pedestrians converge onto position-following as cleanly as vehicles, or do
they show the short-track convergence failure that Q6 describes for vehicles?

**A3 — Selection displacement.**
Pedestrians now compete for 3 slots. Acceptance: across the 10 mini scenes,
report (i) how often a pedestrian displaces a vehicle from the selected set
vs the old vehicle-only ranking, (ii) distance/TTC distributions of selected
pedestrians vs selected vehicles, and (iii) any scene where import now fails
(`<2 actors`) or succeeds where it previously failed. If displacement
systematically drops the highest-risk vehicle, propose a quota or weighting
— as a proposal with acceptance bar, not an implementation.

**A4 — esminiJS (WASM) handling of the new tags.**
Acceptance: confirm the esminiJS build parses `Pedestrian` and `MiscObject`
entities (init + `step_frame` + object states, same P0 bar as vehicles), and
report the exact `type`/`kind` strings the engine returns for them — the
renderer currently buckets non-`vehicle` objects as `unknown` (gray) and the
ledger reports `actor_kind: vehicle | unknown`, so your strings decide whether
a `pedestrian` kind/color is a truthful small increment or scope creep.

**A5 — MiscObject policy.**
Acceptance: recommend (i) keep `other` for all, (ii) map specific categories
(e.g. `movable_object.barrier` → `barrier`), or (iii) reject non-vehicle
non-human at export (fail-closed). Include what esmini actually does with each
`MiscObjectCategory` value — an untested mapping is an invented fact.

**A6 — Mass/dimension defaults audit.**
`Pedestrian mass=75`, `MiscObject mass=0`, and the bbox fallback scales are
documented-as-inert defaults for position following. Acceptance: confirm from
esmini semantics (or a run) that mass truly never steers a
`FollowTrajectoryAction` under `followingMode="position"`, or mark the
assumption false with the mechanism.

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
7. Anything in §2 you measured differently — ground facts are versioned, not
   sacred.
