# WASM/sim data-analysis returns — consolidated index

`scientific_status: PROVISIONAL`

Single entry point for every data-analysis return against the WASM/simulator
handoff chain. Written 2026-10-16 so the results can be re-read later without
re-deriving them. Each section states the verdict, the evidence location, and the
scope limit, so nothing here can be quoted outside its scope.

Engine: native esmini **`v3.10.0-0-06065f9`** and esminiJS **3.10.0 WASM**
(version-matched; the earlier 3.9.0-native vs 3.10.0-WASM skew is resolved).
Dataset: nuScenes `v1.0-trainval`, 850 scenes, token-ascending index.
Integration step: `--fixed_timestep 0.01`.

## Return index

| item | question | verdict | report |
|---|---|---|---|
| **A1** | does the widening change vehicle XOSC output? | **NO — 40/40 byte-identical** | inline below |
| **A2a** | does the `0.0411 m` baseline survive on 3.10? | **YES — central statistics agree to within ~1 %** | `a2-pedestrian-replay-fidelity.md` |
| **A2b** | per-category pedestrian vs vehicle ADE/FDE | pedestrians **2.6x tighter median, 4.5x tighter max** | same |
| **A2c** | do pedestrians show short-track convergence failure? | **NO** | same |
| **A3** | does a pedestrian displace a vehicle? | **32.35 % of scenes, 0 ranking anomalies** | `a3-selection-displacement.md` |
| **A4** | does esminiJS parse the new tags, and what strings? | **PASS**; wrong field names in the existing probe | `a4-a5-wasm-entity-tags.md` |
| **A5** | MiscObject policy + what esmini does with each category | 17 valid values; `other` invalid; **2 exporter defects** | same |
| **A6** | is `mass` inert under position following? | **YES — assumption HOLDS**, decided by construction | `a6-mass-inertness.md` |

---

## A1 — vehicle XOSC byte-identical across the widening

Exported the same 40 canonical scenarios with the pre-widening exporter (HEAD via
a detached worktree) and the post-widening working tree, then diffed the XML:

```
scenarios 40   identical_files 40   differing_files []   missing_after []
verdict: EMPTY_DIFF__ADE_RECOMPUTE_VACUOUS
```

The ADE recompute is vacuous **for the input**. A1 alone could not prove the
*engine* agreed; A2a closed that.

## A2 — pedestrian replay fidelity, per category

| class | tracks | ADE median | ADE mean | ADE p95 | ADE max | FDE median | coverage |
|---|---|---|---|---|---|---|---|
| ego | 850 | 0.0525 | 0.0518 | 0.0967 | 0.1723 | 0.0539 | 850/850 |
| **pedestrian** | **432** | **0.0124** | **0.0133** | **0.0359** | **0.0468** | **0.0037** | 432/432 |
| **vehicle** | **2113** | **0.0318** | **0.0398** | **0.1096** | **0.2112** | **0.0045** | 2113/2113 |

**Never blended.** 0 failures in 850 scenes.

Engine portability (A2a): esmini 3.9.0 baseline mean 0.0411 m → 3.10.0 mean
0.0413 m (+0.5 %); median +1.1 %; p95 +0.6 %, on a strictly **larger**
population (A2a is vehicle-only: `3383` vs the baseline `3215`, because this
harness does not apply the kinematic feasibility gate and therefore also
replays the 42 scenes the production benchmark rejects. A2b above is
pedestrian-inclusive at `3395`. Do not compare an A2a figure to an A2b figure.)

Convergence (A2c): no class exceeds 0.5 m ADE. Pedestrian short tracks (< 2 s)
are the *best* group at max 0.0146 m — short tracks are not a pedestrian problem.

## A3 — selection displacement

| quantity | value |
|---|---|
| scenes with >= 1 selected pedestrian | 275 (32.35 %) |
| scenes where a vehicle is displaced | 271 (31.88 %) |
| vehicles displaced / pedestrians added | 420 / 432 |
| displaced vehicles that were **rank 1** | **271 (64.52 %)** |
| **ranking anomalies** (vehicle had better TTC, still lost) | **0** |
| scenes where the selected set shrank | **0** |
| import regressions | **0** (850/850 succeed before and after) |

Pedestrians that win a slot are ~2x closer (4.61 m vs 9.86 m) and ~2x more
imminent (1.35 s vs 2.65 s median TTC). **The ranking is not defective**; the
trade-off is a policy question about whether TTC is the right severity proxy
across object classes.

Proposal delivered (not implemented): reserving one vehicle slot would change
35 scenes (4.12 %), lift vehicle coverage 815 → 850, and cost 35 pedestrian slots
(−8.1 %). Acceptance bar recorded in the A3 report.

## A4 — esminiJS entity tags

Parse verdict **PASS**: 3 entities in, 3 out, stepping cleanly at `dt = 0.01`.

| entity | `object_type` | `object_category` |
|---|---|---|
| Vehicle | `1` | `0` (class enum) |
| Pedestrian | `2` | `0` = PEDESTRIAN |
| MiscObject | `3` | `5` = BARRIER |

**The state object has no `type` and no `kind` field.** The existing `smoke.mjs`
and the renderer read those, which is why everything is bucketed `unknown`. Fix
the field read, then a pedestrian kind/colour is a truthful increment, not scope
creep.

Cross-engine parity: native 3.10 and esminiJS 3.10 agree exactly on both the
error path and the value path.

## A5 — MiscObject policy

- 17 valid `miscObjectCategory` values; **`other` is not one of them**.
- Unrecognised values hit `LOG_ERROR("MiscObject category {} not supported yet")`
  and fall back to enum `NONE = 0`. Non-fatal, exit 0.
- **Defect 1:** the exporter writes `MiscObjectCategory`, esmini reads
  `miscObjectCategory`. The value is **never read**, whatever it says.
- **Defect 2:** `Pedestrian` is emitted with no `pedestrianCategory` at all.
- Category is **motion-inert** under position following: 7 categories replayed,
  all byte-identical.
- Recommended: fix both attribute names, map 6 reachable categories (1 exact,
  4 approximate → `obstacle`, 1 fail-closed for `animal`). This buys log hygiene
  and forward compatibility and changes **no replay number**.

## A6 — mass inertness

**`MASS_INERT_UNDER_POSITION_FOLLOWING__ASSUMPTION_HOLDS`.**

Executed the delivered protocol on native 3.10: real pedestrian track (15.50 s,
32 vertices, 1.30 m/s speed range, so acceleration is genuinely present), real
ego, static cone. Determinism gate passed (two runs byte-identical). Three
single-variable variants — pedestrian 75→750, misc 0→100, misc 0→1 — all produced
**byte-identical traces**. `MiscObject mass=0` does not crash the engine.

A defect in my own first attempt (the `cone1` variant varied the pedestrian's
mass and left the cone's at `0`, so the cone was never tested) was caught by a
`diff` self-check and is recorded in the report, because it is exactly the
failure mode the protocol exists to catch.

---

## Cross-cutting facts worth not re-deriving

1. **Read-out floor.** Resampling a recorded trajectory onto the 0.01 s grid and
   back through `compute_replay_metrics()` costs **0.000144 m** median. The
   metric is not the bottleneck at any residual measured here.
2. **Residual character.** After the export-timing fix, error is **100 %
   along-track** and starts at exactly `0.0000 m`. Per population, quoting
   `residual-replay-error-composition.md` §7:

   | population | mean abs ADE | mean abs cross-track | along-track / distance |
   |---|---|---|---|
   | **ego** (`808` tracks) | 0.2618 m | median 0.0037 m, p95 0.0095 m | **~0.25 %** (0.2617 m over 104.98 m) |
   | **non-ego** (`2406` tracks) | 0.0358 m | — | far smaller |

   Ego is the largest single error population and its residual is almost purely
   accumulated along-track drift. **There is no single blended percentage** —
   ego and non-ego differ by ~7x, so quoting one number for "the residual"
   would misrepresent both.
3. **Timestep converged.** `dt = 0.005` is bit-identical to `dt = 0.01`;
   `dt = 0.05 → 0.01` was worth 4.2x on ADE mean.
4. **The 850-scene role A baseline** (`b52d423`): ADE mean 0.0411 m, median
   0.0348 m, p95 0.1035 m, max 0.1726 m, FDE max 0.2052 m over 3215 tracks,
   808/850 valid. Confirmed portable to 3.10.0.
5. **The dominant replay error was a time-origin defect**, not the map template.
   Map-template causation was **refuted by measurement**: the worst actors sit
   0.52–0.59 m from native nuScenes lane centrelines, while ADE≈0 actors sit
   4.2–4.3 m away and are stationary.

## Standing constraints on any of the above

- Browser/WASM output is **preview-only** and must never feed ADE/FDE,
  `replay.csv`, gates or reports (DEC-018).
- If WASM and native disagree, **native is authoritative**.
- Unavailable must be shown as unavailable, never as a placeholder that reads as
  success.
- Raw nuScenes data and derived artifacts stay local/private. Everything under
  `docs/reports/` is gitignored by repository policy.
- Every number above is `PROVISIONAL` and carries its scope limit. None of it
  establishes map accuracy, safety/TTC evidence, or a scientific fidelity claim.

## Still open

| item | status |
|---|---|
| A4 follow-ups: `reset()` entity-ID stability, end-of-track hold policy, seek | not measured; native-only evidence does not substitute |
| A5 implementation of the corrected attribute names | proposed, not implemented |
| A3 vehicle-slot quota | proposed with acceptance bar, owner decision |
| §4.2 WASM↔native divergence inventory beyond `dt` | partial (tags only) |
| §4.3 completeness remainder, §4.4 sensor fusion | not started |
| `min_track_duration_s` policy | still open; **no pressure to set it** — no class exceeds 0.5 m ADE now |
| bounding-box dimension inertness | **not** established; A6 covered `mass` only |