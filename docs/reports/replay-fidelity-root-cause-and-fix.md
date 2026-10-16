# Replay fidelity: root cause, full-850 validation, and fix

`scientific_status: PROVISIONAL`

Companion to `docs/reports/replay-variant-metric-diagnostics.md`. That report
characterised the metric distribution on a 100-scene index and did **not**
identify the cause. This report covers the **full 850-scene set**, isolates the
dominant cause, and records a measured fix.

All numbers below are **role A** (recorded-vs-replayed fidelity, identity grid)
unless explicitly labelled otherwise. The advisory nuScenes prediction metric
(`minADE`/`minFDE`) is not used anywhere in this report.

## Provenance

| Item | Value |
|---|---|
| Dataset | nuScenes `v1.0-trainval`, **all 850 scenes** |
| Locations | `boston-seaport` 467, `singapore-onenorth` 183, `singapore-queenstown` 115, `singapore-hollandvillage` 85 |
| `scene.json` SHA-256 | `bdc3211bfbfda652d5e9dab73c45c7132925ca84f869bf45e8e14edeafb1d20b` |
| Index policy | `scene.json` sorted by `token` ascending, slice `[0:850]`, no location cherry-picking |
| esmini | `v3.9.0-0-efbf7ee1` |
| Git revision | `e9ad9b80e9f1835d4c2311d53854783faab1f100` (working tree, uncommitted) |
| Valid scenes | 808 / 850 (42 rejected by kinematic feasibility; identical before and after the fix) |
| Actor tracks | **3215** (808 ego + 2407 non-ego) |

## Headline

The dominant error source is **not** the map template. It is a **time-origin
defect in XOSC event triggering**: every actor's `FollowTrajectoryAction` started
at simulation time 0, including actors whose recorded track begins later. esmini
therefore consumed the whole recorded trajectory in the first seconds and then
coasted, leaving the actor roughly `track_start_time x speed` metres ahead of
truth at every compared timestamp.

One-line fix, validated on all 850 scenes:

| statistic (role A, 3215 tracks) | before | after | reduction |
|---|---|---|---|
| ADE mean | 16.040 m | **1.138 m** | **92.9 %** |
| ADE median | 0.300 m | 0.122 m | 59.5 % |
| ADE p95 | 95.067 m | **5.882 m** | **93.8 %** |
| ADE max | 279.088 m | 95.665 m | 65.7 % |
| FDE mean | 14.276 m | **0.179 m** | **98.7 %** |
| FDE median | 0.338 m | 0.016 m | 95.3 % |
| FDE p95 | 87.668 m | 0.605 m | 99.3 % |
| FDE max | 254.796 m | **1.030 m** | 99.6 % |

Valid/invalid split is unchanged (808/42), so no validity was traded for the
improvement. No threshold, tolerance or feasibility limit was modified.

## The fix

`src/real2scenario/exporter.py`, `_append_maneuver_group`:

```python
-    _append_simulation_time_condition(start_trigger, "greaterThan", 0.0, edge="none")
+    _append_simulation_time_condition(
+        start_trigger, "greaterThan", actor.trajectory[0].time_s, edge="none"
+    )
```

The actor is already teleported to `trajectory[0]`, so it holds position until
its recorded track actually begins, then follows the polyline on the recorded
timeline. `time_reference` `offset` is deliberately left at `"0"`: with
`domainAbsoluteRelative="relative"` the offset *shifts vertex times*, which was
measured and made things worse (see "Rejected hypotheses").

## Evidence that this is the cause

### 1. Error tracks the track start time almost monotonically

Baseline, role A, 348 tracks from the 100-scene index:

| track start time | n | ADE median | ADE mean | share > 10 m |
|---|---|---|---|---|
| t = 0 s | 206 | **0.173 m** | 0.207 m | **0.0 %** |
| (0, 2) s | 32 | 2.878 m | 4.828 m | 18.8 % |
| [2, 5) s | 28 | 18.238 m | 21.675 m | 67.9 % |
| [5, 10) s | 46 | 36.785 m | 35.346 m | 69.6 % |
| >= 10 s | 36 | 69.313 m | 59.778 m | 72.2 % |

Pearson r(start_t, ADE) = **0.734**. Tracks beginning at t = 0 have *zero*
tracks above 10 m.

### 2. Direct trace inspection

Worst baseline track (ADE 157.8 m, `start_t` = 11.5 s). Recorded and replayed
positions at each recorded timestamp:

```
   t     rec_x    rec_y    rep_x    rep_y      err  recsp  repsp
11.50    219.14    29.14    34.48   -19.18   190.88  16.06  17.97
13.50    191.99    14.14     0.00   -19.18   194.86  14.71  17.38
16.00    155.29    -1.13     0.00   -19.18   156.34  16.49   0.00
19.50     96.52   -19.18     0.00   -19.18    96.52  17.97   0.00
```

The XOSC itself is correct: teleport `(219.14, 29.14)`, speed 16.06 m/s, and a
17-vertex polyline from `(219.1, 29.1)` to `(96.5, -19.2)` with vertex times
`11.50 .. 19.50`. But the replay started at simulation t = 0, so the entire
8-second trajectory was consumed by t = 8, and by the first compared sample
(t = 11.5) the actor had run ~185 m past where it should have been. The
replayed speed then collapses to exactly `0.00` once the polyline is exhausted.

### 3. The fix leaves the unaffected population bit-identical

This is the strongest control. Tracks that already start at t = 0 are unaffected
by the change and their metrics do not move at all:

| population | n | before median | after median | before max | after max |
|---|---|---|---|---|---|
| start_t == 0 s | 1789 | 0.1807 m | 0.1807 m | 0.862 m | 0.862 m |
| ego (always starts at 0) | 808 | 0.2618 m | 0.2618 m | 0.862 m | 0.862 m |

A change that improves the failing population while leaving a 55.7 % control
population numerically unchanged is behaving like a genuine bug fix rather than
a global distortion.

## What the fix did NOT fix, and why

Residual error is concentrated in **very late, very short tracks**:

| track start time | n | median after | share > 10 m after |
|---|---|---|---|
| t = 0 s | 1789 | 0.181 m | 0.0 % |
| (0, 2) s | 221 | 0.029 m | 0.0 % |
| [2, 5) s | 291 | 0.044 m | 0.3 % |
| [5, 10) s | 410 | 0.058 m | 2.7 % |
| >= 10 s | 504 | 0.201 m | **17.3 %** |

Every one of the 8 worst residual tracks has `duration` between 0.40 s and
1.60 s with only 2–4 keyframes, starting between t = 17.6 s and t = 19.1 s — i.e.
at the very end of a ~19.5 s scenario. The entity is teleported into position
but esmini has under two seconds to settle heading and steering onto the path, so
it is still far from the recorded position at the first and often only compared
sample. This is a **convergence-time** limitation, not a timing bug.

The project already has the parameter for this:
`compute_scenario_replay_metrics(..., min_track_duration_s=...)`, currently
defaulting to `0`. Its effect, measured on the post-fix 3215 tracks:

| filter | n kept | median | mean | p95 | max | > 10 m |
|---|---|---|---|---|---|---|
| none (`= 0`) | 3215 | 0.1216 | 1.1378 | 5.8821 | 95.67 | 3.08 % |
| exclude < 1 s | 3203 | 0.1216 | 1.0546 | 5.6225 | 57.10 | 2.93 % |
| exclude < 2 s | 3168 | 0.1195 | 0.9200 | 4.8019 | 41.81 | 2.53 % |
| exclude < 3 s | 3094 | 0.1158 | 0.7628 | 4.2847 | 32.37 | 1.91 % |
| exclude < 5 s | 2868 | 0.1046 | 0.5539 | 3.1444 | 22.65 | **0.66 %** |

Only 1.5 % of tracks (47/3215) are shorter than 2 s. For reference, the same
exclusion applied to the **baseline** barely moves it (mean 16.040 -> 15.021),
confirming short tracks were never the cause and are only trimming the tail now.

This is offered as a **policy proposal, not an applied change**. Choosing the
cut is an owner decision and must not be fitted to the ADE distribution.

## Rejected hypotheses (measured, not assumed)

| hypothesis | experiment | result |
|---|---|---|
| Missing per-vertex speed causes the drift | add `speed` to every `Polyline/Vertex` | **no change at all** (13.1667 -> 13.1667). esmini ignores vertex `speed` under `followingMode="position"`. |
| XOSC timing mode is needed | `followingMode="timing"` + vertex speed | small gain only: mean 13.1667 -> 12.9772, p95 77.97 -> 72.99. Not the cause. |
| Shift the polyline timeline | `Timing offset = trajectory[0].time_s` | **worse**: mean 13.1667 -> 13.7183. With a `relative` domain the offset shifts vertex times rather than delaying the follow. |
| Straight two-lane map template is the dominant cause | distance from each trajectory to native nuScenes lane centerlines | **refuted**. The worst actors sit 0.52–0.59 m from a native lane centerline (i.e. genuinely on-road), while tracks with ADE ~ 0 sit 4.2–4.3 m away and are stationary. |

The map template is therefore **not** the dominant term for ADE. It remains a
real limitation for the G3 road-match gate, which never evaluates, and for any
future claim about map accuracy. It should not be cited as the cause of these
ADE values.

Note the speed hypothesis failing is itself informative: the error was never a
speed-profile problem, it was a *when-to-start* problem.

## Secondary metrics, full 850, post-fix

These are already computed by `compute_replay_metrics()` and are cheap to report:

| metric | population | n | median | mean | max |
|---|---|---|---|---|---|
| heading MAE (rad) | ego | 808 | 0.0068 | 0.0112 | 0.0538 |
| heading MAE (rad) | actor | 2407 | 0.0029 | 0.0075 | 0.0895 |
| speed MAE (m/s) | ego | 808 | 0.1185 | 0.1158 | 0.3118 |
| speed MAE (m/s) | actor | 2407 | 0.1309 | 0.2059 | 8.5231 |

`coverage_status` is `complete` for **3215/3215** tracks. The aggregate still
drops this field, so it remains unauditable from `benchmark-aggregate-v1` alone.

## By location (role A, post-fix)

| location | tracks | median before | median after | > 10 m before | > 10 m after |
|---|---|---|---|---|---|
| boston-seaport | 1767 | 0.281 | 0.112 | 24.6 % | 3.1 % |
| singapore-hollandvillage | 333 | 0.580 | 0.291 | 36.3 % | 5.1 % |
| singapore-onenorth | 683 | 0.244 | 0.073 | 19.2 % | 2.6 % |
| singapore-queenstown | 432 | 0.328 | 0.205 | 26.6 % | 2.3 % |

The fix helps every location by a similar factor. `singapore-hollandvillage`
remains the hardest location on both median and tail.

## Role B/C on the full set (post-fix)

| role | grid | variants | valid | tracks | ADE mean | ADE median | ADE p95 | ADE max |
|---|---|---|---|---|---|---|---|---|
| A | identity | 850 | 808 | 3215 | 1.138 | 0.122 | 5.882 | 95.67 |
| B/C | 12-variant standard | 10200 | 9762 | 38844 | 1.181 | 0.134 | 5.781 | 95.67 |

With the timing defect fixed, role A and the role B/C grid sit close (mean
1.138 vs 1.181), whereas on the 100-scene baseline the edited grid was +1.069 m
above role A. The earlier separation was mostly the timing defect interacting
with the edits, not the edits themselves. Roles A and B remain **distinct
measures** and must still be reported separately.

The gate funnel is unchanged in structure after the fix: G3 evaluated 0, G5
evaluated 0, G6 evaluated 10200 with 0 passes. The fix does not affect gating.

## Status and required approval

The one-line exporter change is **currently applied to the working tree and
uncommitted**. It is a correctness fix with a mechanism, a controlled
experiment, a bit-identical control population and a 92.9 % mean reduction on
850 scenes. It has not been tuned, and no threshold was moved.

It still requires:

1. ~~A focused regression test~~ — **done**:
   `tests/test_exporter.py::test_exporter_delays_trajectory_start_to_the_recorded_track_start`
   builds a scenario whose non-ego track starts at t = 4 s and asserts the emitted
   `StartTrigger` `SimulationTimeCondition/@value` is `4` for that actor and `0`
   for ego, and that `TimeReference/Timing/@offset` stays `"0"`. Verified to
   **fail** against the pre-fix code and pass after.
2. Owner review, since it changes emitted XOSC for every scenario and therefore
   invalidates previous benchmark artifacts for comparison purposes.

## Boundaries honoured

CP1 `20/143 = 13.99 %` untouched; no matcher, threshold, tolerance or
feasibility limit modified; prediction metrics kept separate; every metric
labelled role A/B/C with its denominator; all artifacts local and private;
no new dependency and no new architecture; CARLA same-XOSC still out of scope.