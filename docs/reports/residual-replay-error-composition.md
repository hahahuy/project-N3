# Residual replay error: composition, floors, and further reduction options

`scientific_status: PROVISIONAL`

Third report in the replay-fidelity series. Companion to
`docs/reports/replay-fidelity-root-cause-and-fix.md` (root cause and the first
fix) and `docs/reports/export-timing-850-scene-evidence.md` (self-consistency
framing, recorded by a parallel session).

All ADE/FDE figures are **role A** (recorded-vs-replayed), identity grid, unless
labelled otherwise. The advisory prediction metric is not used.

## 1. Two exporter conditions were needed, not one

The first fix alone (`StartTrigger` at `trajectory[0].time_s`) left a second
defect: the initial `SpeedAction` set each actor moving at its **first recorded
speed from simulation time zero**, so before its own track began, an actor
drifted along the template road at full recorded speed.

Measured evidence for that second mechanism: on the 100-scene index, the replay
error **at the first compared sample** implied 0–24.3 s of free running, which
matches the `start_t` range exactly. `corr(error@start, speed@t0) = +0.280`.

| actor group | share | median ADE |
|---|---|---|
| error at first sample <= 1 m | 72.8 % | 0.036 m |
| error at first sample > 1 m | 27.2 % | 1.901 m |

Both conditions are in `src/real2scenario/exporter.py`:

1. `StartTrigger` `SimulationTimeCondition/@value` = `actor.trajectory[0].time_s`
2. initial `AbsoluteTargetSpeed/@value` = `0`

## 2. Result on all 850 scenes (3215 actor tracks)

| statistic | pre-fix | after both conditions | reduction |
|---|---|---|---|
| ADE mean | 16.0399 | **0.1728** | **98.9 %** |
| ADE median | 0.2998 | **0.0586** | 80.5 % |
| ADE p95 | 95.0669 | **0.5365** | **99.4 %** |
| ADE max | 279.0878 | **0.8859** | **99.7 %** |
| FDE mean | 14.2757 | 0.1786 | 98.8 % |
| FDE median | 0.3375 | 0.0158 | 95.3 % |
| FDE p95 | 87.6680 | 0.6052 | 99.3 % |
| FDE max | 254.7957 | 1.0298 | 99.6 % |

Valid/invalid scene counts are identical (808/42), so nothing was traded away.

**Every track is now below 0.9 m.** 93.3 % are below 0.5 m and 49 % are below
0.05 m.

### The control populations are bit-identical

| population | n | pre-fix median/max | post-fix median/max |
|---|---|---|---|
| ego | 808 | 0.2618 / 0.8617 | 0.2618 / 0.8617 |
| actor tracks with `start_t == 0` | 1789 | 0.1807 / 0.8617 | 0.1807 / 0.8617 |

Neither condition can affect these populations, and they do not move. This is
what distinguishes a genuine fix from a global distortion of the metric.

## 3. What the remaining 0.06 m actually is

Residual composition, 3214 tracks:

| population | n | median | mean | p95 | max |
|---|---|---|---|---|---|
| all | 3214 | 0.0592 | 0.1728 | 0.5365 | 0.8859 |
| ego | 808 | **0.2618** | 0.2523 | 0.4823 | 0.8617 |
| non-ego actor | 2406 | **0.0358** | 0.1461 | 0.5510 | 0.8859 |

Ego is now the **largest** single error population, and its error is almost
entirely accumulated along-track drift:

| ego quantity | median | p95 |
|---|---|---|
| error at first sample | **0.0000** | 0.0000 |
| error at last sample | 0.2723 | 0.5189 |
| mean abs along-track | 0.2617 | 0.4819 |
| mean abs cross-track | **0.0037** | 0.0095 |
| distance travelled (m) | 104.98 | 192.78 |

Ego starts at exactly zero error (the teleport is exact) and accumulates about
0.26 m over 105 m, i.e. roughly **0.25 % of distance travelled**. It is a
numerical/tracking residual of the follow controller, not a timing or map error.

## 4. Floors: how much of the remainder is removable at all

Two floors were measured. Neither involves smoothing, filtering or altering the
reference.

**Floor 1, metric read-out.** Resample the recorded trajectory onto the replay
grid and read it back through `compute_replay_metrics()`:

| replay grid | read-out floor (median ADE) |
|---|---|
| 0.05 s | 0.000155 m |
| 0.01 s | 0.000144 m |

Immaterial. The metric is not the bottleneck.

**Floor 2, physical feasibility.** The exported OpenSCENARIO vehicle envelope is
`maxAcceleration 10`, `maxDeceleration 10`, `maxSpeed 70`, `maxSteering 0.5`.
Measuring the acceleration the *recorded* polylines actually demand:

| demand | median | p95 | max | limit |
|---|---|---|---|---|
| peak lateral (m/s²) | 0.24 | 2.42 | 6.65 | 10 |
| peak longitudinal (m/s²) | 1.11 | 3.43 | 7.31 | 10 |

**Tracks exceeding the envelope: 0 of 3206.** The vehicle envelope is not
binding, so the residual is *not* a physics floor. Steering is deliberately
excluded: relating yaw rate to the `maxSteering` attribute requires a wheelbase
and an actuation model that the exported OpenSCENARIO does not declare, so no
steering feasibility claim is made.

Conclusion: the remaining error is simulator tracking behaviour. It is real
error, and it is in principle reducible.

## 5. Further reduction options, measured

Every option below was implemented, run and measured on the same 100-scene
index. Nothing was tuned against a threshold.

| option | ADE mean | ADE median | ADE p95 | ADE max | verdict |
|---|---|---|---|---|---|
| both exporter conditions (reference) | 0.1829 | 0.0807 | 0.5431 | 0.7787 | — |
| + per-vertex `speed` attribute | 0.1829 | 0.0807 | 0.5431 | 0.7787 | **no effect**; esmini ignores it under `followingMode="position"` |
| + `followingMode="timing"` | 0.2091 | 0.1484 | 0.5933 | 1.4269 | **worse** |
| + `fixed_timestep` 0.05 -> 0.01 | **0.0434** | **0.0365** | **0.1067** | **0.1490** | **large improvement** |

### `followingMode="timing"` is a regression — currently on `main`

HEAD (`7b1f053`) sets `followingMode="timing"`. Re-run on the **full 850
scenes**, with both timing conditions otherwise identical:

| statistic | `position` | `timing` (HEAD) | worse by |
|---|---|---|---|
| ADE median | **0.0586** | 0.1322 | 2.26x |
| ADE mean | **0.1728** | 0.1977 | 1.14x |
| ADE p95 | **0.5365** | 0.5694 | 1.06x |
| ADE max | **0.8859** | 1.9154 | 2.16x |
| FDE max | **1.0298** | 1.8352 | 1.78x |

`timing` is worse on **every** statistic. Forcing the entity to be at each 2 Hz
vertex at each vertex time forces bang-bang control between chords that are
0.5 s apart, which is worse than the smoother position-following default.

The working tree currently restores `"position"`. **This is left uncommitted for
owner decision**, because reverting a commit is not a diagnostic agent's call.

### Timestep refinement: recommended, not applied

`fixed_timestep_s` 0.05 -> 0.01 (`src/real2scenario/simulation.py:58`).

| population | dt = 0.05 median/max | dt = 0.01 median/max |
|---|---|---|
| all | 0.0825 / 0.7787 | **0.0365 / 0.1490** |
| ego | 0.2796 / 0.6957 | **0.0559 / 0.1391** |
| actor | 0.0384 / 0.7787 | 0.0325 / 0.1490 |

It helps **ego 5x** (0.2796 -> 0.0559) and barely moves actors, which is exactly
the signature of a numerical integration residual. The read-out floor does not
move (0.000155 -> 0.000144 m), so the gain is real rather than a smaller yardstick.

Runtime cost measured on 10 scenes: 3.39 s -> 3.86 s, about **+14 %**, because
wall clock is dominated by devkit ingestion rather than by integration.

This is **not applied**, for two reasons: `fixed_timestep_s` is a recorded
provenance field, so changing it invalidates comparison with previous
artifacts; and the project documents a `0.05 s` fixed-timestep contract.

## 6. What would be cheating, and is deliberately not proposed

These would lower the reported number while reducing or misrepresenting
evidence. They are listed so they are not adopted later by accident:

- **Smoothing or resampling the recorded trajectory** before export. The
  ground-truth policy fixes the raw annotation as the reference; smoothing it
  changes the yardstick.
- **Fitting the exported trajectory to the replay** (or vice versa). That is
  circular; the metric must compare two independently produced artefacts.
- **Widening `maxAcceleration`/`maxDeceleration`** to make the vehicle less
  physical purely to lower error. Currently not binding at all (0/3206 tracks).
- **Moving an ADE/FDE threshold** to make the result look acceptable.
- **Excluding inconvenient tracks** with a rule fitted to the ADE distribution.
  `min_track_duration_s` is a legitimate policy knob, but its cut must be chosen
  on physical grounds, not chosen because it improves a number.

## 7. Role note on the identity grid

`docs/reports/export-timing-850-scene-evidence.md` states that these figures
measure exported-scenario self-consistency and "do not establish replay fidelity
against recorded driving". That caution is correct in general and is right for
every edited variant. For the **identity grid** it is stricter than necessary:
the generated trajectory is the canonical trajectory, and the canonical frame is
a rigid translation plus rotation of the raw annotation, so the frame change
cancels exactly in a Euclidean distance metric. Position ADE on the identity
grid is therefore position-equivalent to role A.

The distinction that does survive is the **speed** channel: canonical actor speed
is a finite difference of raw positions, while ego speed may come from CAN pose.
`speed_mae_mps` is therefore role B on the identity grid, and `heading_mae_rad`
and position ADE/FDE are role A.

## 8. Open items

1. Owner decision on the `followingMode` regression now on `main`.
2. Owner decision on `fixed_timestep_s` 0.05 -> 0.01.
3. Owner decision on a physically-motivated `min_track_duration_s`. After both
   conditions are applied, excluding tracks shorter than 2 s is worth much less
   than it was before, so there is no longer pressure to set it.
4. CP1 lane road-match remains `20/143 = 13.99 %`; map accuracy is still not
   established by any measurement here.
5. G3, G5 still never evaluate and G6 still reports `fail` for an unimplemented
   capability. Unaffected by these fixes.

## Verification

`check_docs_consistency.py` PASS; 331 Python tests pass, including two
regression tests that assert the trigger condition and the zero initial speed and
that both fail against pre-fix behaviour. Frontend 48 tests and production build
unchanged.

## 9. Knob sweep and the confirmed optimum

Every candidate was implemented, run and measured on the same 100-scene index
with both timing conditions in place. `followingMode` was cross-checked at the
finer timestep so the earlier conclusion could not be an artefact of the coarse
step.

| configuration | ADE mean | ADE median | ADE p95 | ADE max |
|---|---|---|---|---|
| `position`, dt 0.05 | 0.1829 | 0.0807 | 0.5431 | 0.7787 |
| **`position`, dt 0.01** | **0.0434** | **0.0365** | **0.1067** | **0.1490** |
| `position`, dt 0.005 | 0.0434 | 0.0365 | 0.1067 | 0.1490 |
| `position`, dt 0.01 + `--ignore_heading_for_traj_motion` | 0.0434 | 0.0365 | 0.1067 | 0.1490 |
| `timing`, dt 0.01 | 0.0659 | 0.0564 | 0.1637 | 1.4008 |
| `timing`, dt 0.01 + per-vertex speed | 0.0659 | 0.0564 | 0.1637 | 1.4008 |

Three results matter:

1. **dt 0.005 is bit-identical to dt 0.01.** The integration error has converged;
   a finer step buys nothing. 0.01 is the operating point, not a guess.
2. **`timing` remains worse at the finer timestep** (ADE max 1.4008 vs 0.1490,
   9.4x). The earlier verdict was not an artefact of the coarse step.
3. **Per-vertex `speed` and `--ignore_heading_for_traj_motion` are both inert.**
   Neither is a lever.

## 10. Confirmed optimum, full 850 scenes (3215 tracks)

| statistic | original main | `timing` (current main) | `position` | **`position` + dt 0.01** |
|---|---|---|---|---|
| ADE mean | 16.0399 | 0.1977 | 0.1728 | **0.0411** |
| ADE median | 0.2998 | 0.1322 | 0.0586 | **0.0348** |
| ADE p95 | 95.0669 | 0.5694 | 0.5365 | **0.1035** |
| ADE max | 279.0878 | 1.9154 | 0.8859 | **0.1726** |
| FDE mean | 14.2757 | 0.1879 | 0.1786 | **0.0356** |
| FDE median | 0.3375 | 0.0196 | 0.0158 | **0.0079** |
| FDE p95 | 87.6680 | 0.8913 | 0.6052 | **0.1170** |
| FDE max | 254.7957 | 1.8352 | 1.0298 | **0.2052** |

Cumulative reduction against the original main line: ADE mean **99.74 %**, ADE max
**99.94 %**, FDE max **99.92 %**. Valid/invalid scenes unchanged at 808/42.

## 11. Status: both changes approved and committed

Approved by the project owner and committed as `b52d423`:

- `followingMode` restored to `position`
- `fixed_timestep_s` 0.05 -> 0.01

The contract consequence is resolved rather than outstanding: the
`tests/test_simulation.py` assertion that pinned `--fixed_timestep` to `0.05`
now pins `0.01` and carries the measurement inline. A second regression test,
`test_exporter_keeps_position_following_mode`, was added because that
regression had already reached `main`. Both tests were verified to **fail**
against the pre-fix state and pass afterwards.

`fixed_timestep_s` is a recorded provenance field, so this commit supersedes
every earlier ADE/FDE figure. The table in section 10 is the baseline to
compare against.

## 12. Superseded figures

| figure set | status |
|---|---|
| ADE mean 16.0399 m, ADE max 279.0878 m (850 scenes) | superseded, pre-fix exporter and 0.05 s step |
| ADE mean 0.1977 m (850 scenes) | superseded, `timing` regression |
| ADE mean 0.1728 m (850 scenes) | superseded, correct mode but coarse step |
| **ADE mean 0.0411 m, ADE max 0.1726 m (850 scenes)** | **current, `b52d423`** |

The 100-scene figures in sections 2 and 9 remain valid as the experiment record
that justified each decision, but the reported baseline is the 850-scene one.

## 13. Handoff note for the WASM / esminiJS team

Three measured facts that constrain any WASM evaluator, sent separately and
repeated here so the report is self-contained:

1. **Per-vertex `Vertex/@speed` is inert.** Adding it changed nothing under
   either `position` or `timing`, to four decimal places over 348 tracks. Native
   esmini 3.9.0 does not read it. A WASM evaluator that honours it would
   diverge from native rather than match it.
2. **`followingMode="timing"` must not be replicated.** It is measurably worse
   on every statistic. WASM should implement `position`.
3. **Two export behaviours must be mirrored or WASM playback will visibly
   differ from frame one:** the actor holds position with
   `AbsoluteTargetSpeed = 0` until `trajectory[0].time_s`, and the
   `FollowTrajectoryAction` `StartTrigger` fires at `trajectory[0].time_s`, not
   at zero. Before these, 27.2 % of actor tracks were displaced before their
   recorded track even began.

Also unresolved and blocking any *scientific* correlation claim: the canonical
`State` model carries `source_timestamp_us` and `source_record_token`, but
`scenario.json` does not serialise either, and `time_s` is relative to
scenario start. The mapping from replay time to nuScenes source time therefore
cannot be reconstructed from the exported artifact today.
