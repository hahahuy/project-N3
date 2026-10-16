# Replay and variant metric diagnostic analysis

`scientific_status: PROVISIONAL`

> **Superseded in part.** This report characterises the metric distribution on a
> **100-scene** index and deliberately stops before proposing fixes. The
> dominant cause has since been isolated and a fix measured on the **full 850
> scenes**; see `docs/reports/replay-fidelity-root-cause-and-fix.md`. Read that
> report first — it revises the "map template is the dominant cause" working
> hypothesis recorded in F-01/F-02 below.

This is a **diagnostic analysis pass over already-generated metrics**. It adds no
feature, changes no pipeline behaviour to improve a number, and proposes no
threshold. Every number below is labelled with the metric role it belongs to,
its denominator, and what it does not prove.

## Provenance

| Item | Value |
|---|---|
| Dataset | nuScenes `v1.0-trainval`, 850 scenes, private dataset root (local mount) |
| `scene.json` SHA-256 | `bdc3211bfbfda652d5e9dab73c45c7132925ca84f869bf45e8e14edeafb1d20b` |
| `log.json` SHA-256 | `774c8256554a5569f64660e5f450394ce7e3a82168edfab530edab81f9ae7edc` |
| Git revision | `e9ad9b80e9f1835d4c2311d53854783faab1f100` |
| esmini | `v3.9.0-0-efbf7ee1` |
| Metric core | `compute_replay_metrics()`, `src/real2scenario/metrics.py:59` |
| Aggregate contract | `benchmark-aggregate-v1`, `src/real2scenario/benchmark.py:69` |
| Scene index policy | `scene.json` sorted by `token` ascending, slice `[0:100]`, no per-location cherry-picking |
| Scene index locations | `boston-seaport`, `singapore-hollandvillage`, `singapore-onenorth`, `singapore-queenstown` |
| Artifacts | local/private at `~/r2s-diagnostic/` (local, private), `~/r2s-evidence/` (local, private) |

## Baseline reproducibility

The stated 100-scene pilot was **reproduced**, not re-derived:

| Quantity | Stated baseline | This run | Agrees |
|---|---|---|---|
| scenes / valid / invalid / sim-failed | 100 / 88 / 12 / 0 | 100 / 88 / 12 / 0 | yes |
| actor tracks | 348 | 348 | yes |
| ADE p95 | 77.973 | 77.973 | yes |
| ADE max | 157.803 | 157.803 | yes |
| ADE median | 0.323 | 0.316 | within 0.007 |
| ADE mean | 13.394 | 13.167 | within 0.23 |
| FDE max | 141.038 | 141.038 | yes |
| B/C grid tracks | 4248 | 4248 | yes |
| B/C grid ADE max | 162.764 | 162.764 | yes |

The residual differences in the means are consistent with this run including the
15 no-CAN scenes that the CAN defect (F-04) previously forced out of any index.

Note on provenance: the only pre-existing benchmark run artifact found on this
machine is a **5-scene, single-location** run
(`~/r2s-evidence/cp3-benchmark/`, revision `4137164…`). The 100-scene
figures in the mission brief are not backed by a stored artifact; they are
reproducible, and this report regenerates them.

## Role separation

| Role | Grid | Tracks | ADE mean | ADE median | ADE max |
|---|---|---|---|---|---|
| **A** recorded-vs-replayed | identity | 348 | 13.167 | 0.316 | 157.803 |
| **B** generated-vs-replayed, parent only | identity | 348 | 13.167 | 0.316 | 157.803 |
| **B/C** mixed edited grid, 12 variants | standard | 4248 | 14.236 | 0.358 | 162.764 |

**Role A and role B parent-only are the same computation.** With the identity grid
the generated trajectory *is* the canonical recorded trajectory, so the two
definitions collapse to one number. Measured difference: **0.000 m**, and the
per-scene paired difference over all 88 valid scenes is 0.000 m at max, median
and p95. This is a determinism result as much as a role result: two independent
runs of the same configuration agree exactly.

**Reporting the 12-variant grid as role A is a live error.** It inflates the
pooled mean by **+1.069 m** and the actor-only median from **0.381 m to
2.086 m** (5.5x), because the gap and speed edits push actor tracks away from
recorded truth. Ego is unaffected (median 0.280 → 0.263 m) because the gap edit
does not touch ego.

## Analysis A — distribution, and a correction to the stated hypothesis

Role A, 348 valid actor tracks:

| Statistic | ADE (m) | FDE (m) |
|---|---|---|
| mean | 13.167 | 11.456 |
| median | 0.316 | 0.323 |
| p90 | 55.754 | 45.509 |
| p95 | 77.973 | 77.643 |
| p99 | 121.905 | 109.994 |
| max | 157.803 | 141.038 |
| std | 28.023 | 25.233 |

**The distribution is not cleanly bimodal.** It is trimodal in log space:

| Regime | Range (m) | Tracks | Share |
|---|---|---|---|
| low mode | < 1 | 244 | 70.1 % |
| **saddle** | 1 – 10 | 21 | 6.0 % |
| high mode | >= 10 | 83 | 23.9 % |

The saddle is **populated**, not empty. There is no gap in the data: the largest
log-space gap below the tail is only 1.42x (between 1.18 m and 1.67 m). So a
"strongly bimodal, empty-gap" reading is not supported. The practical
consequence is that any threshold placed inside 1–10 m would classify 6 % of
tracks ambiguously rather than separating two populations cleanly.

## Analysis B — outlier attribution: the error is longitudinal, not lateral

Error decomposed in each recorded actor's own heading frame, 9707 aligned
samples:

| Population | mean abs along-track | mean abs cross-track | along / total | cross-dominant samples |
|---|---|---|---|---|
| all samples | 6.757 m | 1.613 m | **0.906** | 17.9 % |
| good cluster (<1 m) | 0.187 m | 0.016 m | 0.957 | 19.7 % |
| **bad cluster (>=10 m)** | **46.358 m** | 11.382 m | **0.904** | 11.8 % |
| ego only | 0.259 m | **0.004 m** | 0.997 | 5.3 % |
| actors only | 10.482 m | 2.535 m | 0.905 | 25.2 % |

**This refutes the "lateral map error" form of the leading hypothesis.** 90.4 %
of the error in the failing cluster is along-track. And ego cross-track error is
0.004 m — if `straight-two-lane-v1.xodr` were producing lateral map error it
would show up in ego, which drives that template directly. It does not, because
the XOSC export carries absolute positions rather than lane-relative ones.

The map template is still implicated, but through a different mechanism: actors
whose true path is not on the template road get driven onto the template
corridor, producing a large **longitudinal** displacement in roughly the same
heading direction. The map reference is `straight-two-lane-v1.xodr` for all 88
valid scenes (and absent for the 12 rejected, which never reach G1).

The decisive structural split is ego versus actor:

| Population | Tracks | ADE mean | ADE median | ADE max |
|---|---|---|---|---|
| ego | 88 | 0.259 | 0.275 | **0.696** |
| non-ego actor | 260 | 17.535 | 0.372 | 157.803 |

Ego never exceeds 0.696 m in 88 scenes. Every catastrophic value is a non-ego
actor. Separation is not complete (153 actor tracks fall below ego's max), but
the tail belongs entirely to actors.

## Analysis C — coverage and short tracks

**Coverage loss is real in code but empty in this data.** `compute_replay_metrics()`
emits `coverage_status`, but `benchmark_aggregate_to_dict()` never carries it, so
the aggregate cannot report it. Measured directly from the per-actor reports:
**all 348 tracks are `complete`**. `insufficient_coverage` = 0, missing FDE = 0.
Dropping incomplete tracks changes the mean by exactly 0.000 m. The reporting
defect is genuine; its measured impact on this dataset is nil.

There is also no `no_overlap` coverage status in the implementation — a
non-overlapping trajectory raises `ValueError` instead. Any report referring to
a `no_overlap` count would be referring to a status that cannot occur.

Short tracks (`sample_count` proxies duration at the ~0.5 s nuScenes cadence):

| Filter | Tracks kept | ADE mean | Change |
|---|---|---|---|
| none (`min_track_duration_s = 0`) | 348 | 13.167 | — |
| >= 5 samples (~2.5 s) | 345 | 13.143 | -0.024 |
| >= 10 samples (~5 s) | 326 | 11.760 | -1.407 |

Only 3 tracks are shorter than ~2.5 s, and they are not disproportionate (mean
15.9 m, but n=3). Short tracks contribute modestly; the 1.4 m drop at the
10-sample cut is a composition effect, not an artifact of short tracks being
pathological.

## Analysis D — interpolation floor

This is the measurement the brief identified as most valuable. Protocol:
resample each recorded canonical trajectory onto the 0.05 s replay grid and
read it back through the pipeline's own `compute_replay_metrics()`.

| Case | ADE mean | ADE median | ADE max |
|---|---|---|---|
| aligned round trip (keyframes land on grid nodes) | **0.000232 m** | 0.000156 m | 0.00227 m |
| de-commensurate (grid shifted 1/4 step, forcing interpolation at every keyframe) | **0.063 m** | 0.057 m | 0.252 m |

**Conclusion: the 0.316 m median is not resampling error.** Even the pessimistic
floor (every recorded keyframe forced through linear interpolation) is 0.063 m,
5x below the observed median. The aligned floor is 0.0002 m, three orders of
magnitude below. Essentially 100 % of the low-cluster error is genuine
simulator/label error.

The aligned floor is near zero because nuScenes keyframes are ~0.5 s and the
replay grid is 0.05 s, so keyframes coincide with grid nodes; and because the
exporter writes `.17g` and dat2csv writes 12 decimals, so there is no numeric
quantization to measure.

## Analysis E — failure causes

All 12 rejected scenes are `kinematic` feasibility rejections. **Zero simulator
failures. Zero other cause categories.** 22 individual violations across 11
distinct scene IDs.

| Code | Count |
|---|---|
| `acceleration_exceeded` (limit 5.0) | 12 |
| `jerk_exceeded` (limit 20.0) | 8 |
| `deceleration_exceeded` (limit 8.0) | 2 |

Classified by `observed / limit`, with the 1.25x band fixed before inspecting
the split:

| Band | Violations | Reading |
|---|---|---|
| marginal (<= 1.25x) | 13 | attributable to 2 Hz annotation noise |
| moderate (1.25–2x) | 8 | borderline |
| gross (> 2x) | **1** | genuine kinematic anomaly |

Exactly **one** gross violation exists: `scene-0704`, acceleration 10.366 m/s²
against a 5.0 limit (2.07x). The 11 rejected scenes are therefore
**source-data/limit interaction, not pipeline failure** — 10 of 11 are rejected
without a single gross violation.

Two reporting weaknesses: a scene may carry up to 4 violation reasons but the
run card surfaces them as a counted list only, and `reason_count` in G4 counts
reasons, not scenes.

## Analysis F — role A vs role B

See "Role separation" above. Role A and role B parent-only are bit-identical
(0.000 m difference, all 88 scenes). The edited grid must not be reported as
role A.

## Analysis G — role C, measured for the first time

Parent-to-variant deltas measured **directly on trajectories**, never through
ADE. ADE is fidelity against recorded truth, not perturbation size.

| Edit axis | Measured position delta | Measured speed delta | Measured timing delta | Measured gap delta |
|---|---|---|---|---|
| `timing_offset_s` | **0.000 m** | 0.000 m/s | exactly the requested offset (max 1.000 s) | 0.000 m |
| `initial_gap_delta_m` (-2.0) | median **2.000 m**, mean 1.494 m, max 2.000 | 0.000 m/s | 0.000 s | median 2.000 m |
| `speed_multiplier` (0.9) | mean 2.503 m, max 14.649 m | mean 0.501 m/s, max 2.009 m/s | 0.000 s | 0.000 m |

Findings:

- **Timing offset is a pure time shift.** It moves the trajectory start and
  changes nothing inside it: zero position delta, zero speed delta. It does not
  re-time or resample the motion.
- **Gap offset shifts actor positions by the requested amount**, and never
  touches ego (`ego_gap_delta_m` = 0.0 on every variant).
- **The gap edit is not applied uniformly.** Requested -2.0 m, measured median
  2.000 m but mean 1.494 m — a substantial minority of tracks receive a smaller
  shift. This is a real, previously unmeasured inconsistency in the edit path.
- **Speed edits compound into position.** A 10 % speed multiplier produces up to
  14.6 m of positional divergence by the end of a trajectory, which is why the
  edited grid cannot stand in for role A.

This explains the earlier note that `initial_gap_delta_m` "does not change ADE":
the gap edit moves the variant ~1.5–2.0 m away from recorded truth, which is
visible in the edited grid, but ADE is measured against *recorded* truth and was
being read as a perturbation measure, which it is not.

## Analysis H — actor-selection sensitivity

| `max_actors` | Actor tracks | Valid / invalid scenes | ADE mean | ADE median | ADE max |
|---|---|---|---|---|---|
| 1 | 188 | 94 / 6 | 12.192 | 0.336 | 157.803 |
| 2 | 281 | 94 / 6 | 13.976 | 0.343 | 157.803 |
| 3 (default) | 348 | 88 / **12** | 13.167 | 0.320 | 157.803 |

Two findings:

- **The "12/100 rejected" figure is an artifact of the actor-selection policy.**
  At `max_actors` 1 or 2 only 6 scenes are rejected; admitting the third actor
  doubles the rejections. Rejection rate is a function of how many actors are
  retained, not a property of the scenes.
- **The worst outlier is present even at `max_actors=1`** (max 157.803 m
  identical across all three settings). The failure mode is not caused by
  admitting extra actors.

`max_actors` is hard-capped at 3 by contract
(`ValueError: Selection max_actors must be between 1 and 3.`,
`src/real2scenario/selection.py:35`), so wider actor-selection sensitivity is not
reachable without an approved policy change.

**Not measured:** template-vs-scene-local-corridor comparison. `road_match.py`
cannot produce the comparison because G3 never evaluates (F-10), and no
scene-local corridor was available for these scenes. Map error and replay error
therefore remain only partially separated; the ego/actor and along/cross
decomposition above constrains the hypothesis but does not isolate the map term.

## Findings

| ID | Finding | Severity | Class | Evidence |
|---|---|---|---|---|
| F-01 | Actor replay fidelity is catastrophic for 23.9 % of tracks (ADE >= 10 m); ego never exceeds 0.696 m | **HIGH** | pipeline defect | Analysis A/B, role A, n=348 |
| F-02 | Failing-cluster error is 90.4 % along-track, not lateral; ego cross-track error 0.004 m | **HIGH** | measurement diagnostic | Analysis B, 9707 samples |
| F-03 | Median ADE 0.316 m is genuine error, not resampling: floor is 0.0002 m aligned / 0.063 m worst case | MEDIUM (favourable) | measurement artifact ruled out | Analysis D |
| F-04 | CAN pose absence raises a bare devkit `Exception` outside the caught tuple, killing the process | **HIGH** | pipeline defect | Reproduced crash on `scene-0161`; 15/850 scenes affected |
| F-05 | `benchmark.py:92` pools all actor metrics micro-style; the aggregate carries no scene-macro statistic despite the execution plan requiring it | **HIGH** | pipeline defect | `benchmark.py:92`, `analysis.json` |
| F-06 | `coverage_status` is computed but dropped by `benchmark_aggregate_to_dict()` | MEDIUM | pipeline defect | `benchmark.py:135-143`; measured impact nil here (348/348 complete) |
| F-07 | No `no_overlap` coverage status exists; non-overlap raises `ValueError` instead | LOW | pipeline defect | `metrics.py:73` |
| F-08 | G6 reports `fail` for 100/100 because `no_collision` is never computed (`collision_status_unverified`) — an unimplemented capability presented as a measured failure | **HIGH** | pipeline defect | G6 observed block, 100/100 |
| F-09 | G3 `skipped` 100/100 (`road_match_unavailable`) and G5 `skipped` 100/100 (`event_definition_not_declared`): 2 of 7 gates never evaluate | **HIGH** | pipeline defect | Gate funnel, both runs |
| F-10 | Funnel is partially decorative: only G1, G2, G4, G7 ever evaluate | **HIGH** | pipeline defect | `evaluated_counts` |
| F-11 | Feasibility limits reject 12/100 scenes; only 1 of 22 violations is gross | MEDIUM | source-data behaviour | Analysis E |
| F-12 | Rejection count is policy-dependent: 6/100 at `max_actors` 1–2, 12/100 at 3 | MEDIUM | measurement artifact | Analysis H |
| F-13 | `initial_gap_delta_m` is not applied uniformly: requested 2.0 m, measured median 2.000 m but mean 1.494 m | MEDIUM | pipeline defect | Analysis G |
| F-14 | Reported 12-variant grid is role B/C; presenting it as role A inflates actor median 5.5x | **HIGH** | measurement artifact | Analysis F |
| F-15 | `min_track_duration_s = 0`; short tracks are few (3 < 2.5 s) and not disproportionate | LOW | measurement artifact | Analysis C |
| F-16 | `max_actors` hard-capped at 3 blocks wider actor-selection analysis | LOW | contract limit | `selection.py:35` |
| F-17 | The pre-existing on-disk benchmark artifact is 5 scenes / 1 location, not the 100-scene pilot | LOW | evidence hygiene | `~/r2s-evidence/cp3-benchmark/` |
| F-18 | dat2csv emits space-padded CSV headers and values (`" name"`, `" ego"`); parsing is whitespace-sensitive | LOW | pipeline fragility | Observed while reading replay traces |

## Contract-conformance fix

F-04 was fixed as a contract-conformance defect, not a feature. CAN pose is an
optional capability with a documented finite-difference fallback and a
provenance field `fallback_finite_difference`; the implementation violated its
own contract by letting a devkit `Exception` escape.

- `src/real2scenario/nuscenes_backend.py`: added an explicit handler so an
  unavailable CAN source degrades to an empty capability result, mirroring the
  existing broad catch in the same method.
- `tests/test_nuscenes_backend.py`: focused test asserting a bare devkit
  `Exception` yields `can_pose() == ()` and `can_vehicle_monitor() == ()`.

Impact analysis before the edit: `NuScenesSourceAdapter._messages` is
**CRITICAL** risk, 11 impacted symbols across 10 execution flows. The change is
strictly additive and only affects the previously-crashing path.

Effect on the analysis: the full 850-scene pool became usable, removing the
selection bias of excluding the 15 no-CAN scenes.

## Numbers that may NOT be used as a scientific claim

1. **Any ADE/FDE mean.** 13.167 m is a pooled micro mean over 348 tracks
   dominated by a 23.9 % failing regime whose members reach 157.803 m. It
   describes a mixture, not a fidelity level. No scene-macro statistic exists in
   the aggregate to correct this.
2. **The 0.316 m median as a fidelity claim**, until the failure regime is
   characterised and either fixed or excluded by a stated, pre-registered rule.
   It is real error (F-03), but it is a median over a bimodal mixture.
3. **Any number from the 12-variant grid presented as role A** (F-14).
4. **Any statement about map accuracy.** G3 never evaluates, and the
   template-vs-corridor comparison was not possible (Analysis H), so the map term
   is constrained but not isolated.
5. **Any statement about safety, TTC, clearance or rare events.** G6 fails for
   100/100 for an implementation reason, and G3/G5 never evaluate. No gate in
   this system currently provides safety evidence.
6. **The 12/100 rejection rate as a scene property** (F-12).
7. **Any threshold on ADE or FDE.** This analysis deliberately proposes none.
8. **Anything from the advisory `minADE`/`minFDE` prediction metric** — separate
   role, not mixed anywhere in this report.
9. **CP1 corridor road-match `20/143 = 13.99 %`** — preserved unchanged; it is a
   different measurement on different data and is not comparable to anything here.

## Evidence required before any ADE/FDE threshold could be proposed

1. **Scene-macro as the primary statistic**, implemented in
   `benchmark-aggregate-v1` with the micro value retained and explicitly
   labelled as secondary. Until this exists, no threshold has a well-defined
   denominator.
2. **A stated policy for the failing regime.** Either a map/resolution fix, or
   a pre-registered exclusion rule (e.g. actor-off-template) defined on
   properties available *before* the replay, so the exclusion cannot be fitted
   to the ADE distribution it is meant to explain.
3. **Template-vs-scene-local-corridor evidence**, which requires G3 to actually
   evaluate. This is the only way to separate map error from replay error.
4. **G6 implemented, or G6 reporting `skipped` with
   `collision_status_unverified`** rather than `fail`. An unimplemented gate must
   not present as a measured negative.
5. **`coverage_status` carried into the aggregate**, so FDE reliability is
   auditable per run rather than reconstructed from per-actor files.
6. **A larger, scene-stratified sample** across all four locations, with the
   index policy and `scene.json` hash recorded per run, as done here.
7. **An independent label-noise floor.** The interpolation floor is measured
   (0.0002–0.063 m), but nuScenes annotation noise at 2 Hz is a separate and
   unmeasured quantity that bounds achievable ADE from below.
8. **F-13 resolved**, so that `initial_gap_delta_m` is a trustworthy edit axis
   before any variant space is used for evaluation.

## Verification

```
check_docs_consistency.py      -> PASS
pytest                         -> 327 passed
frontend npm test --run        -> 48 passed
frontend npm run build         -> built
```

Passing tests is not acceptance. The numbers above remain `PROVISIONAL`.

## Scope boundaries honoured

CP1 `20/143 = 13.99 %` preserved; matcher policies untouched; prediction metrics
kept separate; every metric and gate marked `PROVISIONAL`; CARLA same-XOSC out of
scope; no new dependencies or architecture; no unavailable capability reported
as success; no tuning toward any target number; all raw data and derived
artifacts kept outside the repository.