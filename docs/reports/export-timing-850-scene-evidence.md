# Export Timing Bug — 850-Scene Self-Consistency Evidence

> **SUPERSEDED — historical record only.** The figures in section 3
> (`median 17.95 m → 0.022 m`, `max 157.80 m → 0.78 m`) are **intermediate**. They
> were measured after the timing fix but **before** the `followingMode` revert to
> `position` and the `fixed_timestep` `0.05 → 0.01` change, both of which reduced
> the error further.
>
> **Current baseline:** ADE mean **0.0411 m**, median **0.0348 m**, p95 **0.1035 m**,
> max **0.1726 m**, FDE max **0.2052 m** — full 850-scene `v1.0-trainval` set, 3215
> actor tracks, esmini v3.9.0, at commits `b52d423`/`79a4a8a`/`3372ff0`. See
> `docs/reports/residual-replay-error-composition.md`.
>
> The mechanism described below is still correct: the defect was a **timing anchor**,
> and it required **two** conditions to fix — hold speed until the recorded track
> starts, and align the follow-trajectory `StartTrigger` to the recorded track start.
> The "map template is the primary cause" hypothesis was disproved by measurement.

Status: `SUPERSEDED-BY-b52d423 / HISTORICAL / PROVISIONAL`
Date: 2026-10-16
Supersedes: the replay self-consistency figures in
`docs/reports/cp3-benchmark-run-evidence.md` for **self-consistency only**.

> **Figures in this report are superseded by commit `b52d423`.** This report was
> recorded while `followingMode="timing"` and a 0.05 s integration step were in
> force. `b52d423` restored `followingMode="position"` (measured worse for
> `timing` on every statistic) and moved `fixed_timestep_s` to 0.01. The
> 850-scene role A baseline to cite from now on is ADE mean **0.0411 m**, median
> **0.0348 m**, p95 **0.1035 m**, max **0.1726 m**, FDE max **0.2052 m** over
> 3215 tracks. See `docs/reports/residual-replay-error-composition.md`.
> The analysis and the role caveat below remain valid.

---

## 1. What the bug was

The exporter emitted an `AbsoluteTargetSpeed` equal to the actor's **first
recorded speed** in its `Init` `SpeedAction`:

```xml
<SpeedAction>
  <SpeedActionDynamics dynamicsShape="step" value="0" dynamicsDimension="time"/>
  <SpeedActionTarget>
    <AbsoluteTargetSpeed value="<actor.trajectory[0].speed_mps>"/>
  </SpeedActionTarget>
</SpeedAction>
```

OpenSCENARIO applies an `Init` action at simulation time zero. An actor whose
recorded track begins late — say at `t = 3.0 s` — therefore received a
non-zero target speed from `t = 0` and was driven **away from its teleport
pose** for the whole interval before its follow-trajectory trigger fired.

The recorded data contains no motion in that window. The simulator was
inventing it. For a late-appearing actor that is metres of fabricated travel,
and it is worst exactly where trajectories are sparse.

A contributing condition is the matching `StartTrigger`: without a trigger
that waits for the recorded track start, a `t = 0` activation lets the
follow-trajectory take over immediately and re-creates the same class of error.

## 2. The fix

`src/real2scenario/exporter.py`:

- `AbsoluteTargetSpeed` is `0` — hold the actor stationary until its recorded
  track begins, instead of pre-loading its initial speed.
- Per-vertex `speed` is emitted on the follow-trajectory `Polyline`, so speed
  is carried by the recorded states themselves rather than by a separate
  controller action.
- The `StartTrigger` is aligned with the recorded track start.

Regression test: `tests/test_exporter.py::test_exporter_holds_actor_stationary_until_its_track_begins`
— asserts the initial `AbsoluteTargetSpeed` is `0` for every actor.

## 3. Measured result (SUPERSEDED — see header)

Measured on the **full 850-scene local nuScenes set**, at the state of `7b1f053`:

| Metric | Before | After | Change |
|---|---|---|---|
| Actor-track ADE, median | 17.95 m | 0.022 m | −99.9% |
| Actor-track ADE, max | 157.80 m | 0.78 m | −99.5% |

**These two rows are intermediate and must not be quoted as current.** The
`followingMode` revert to `position` and the `fixed_timestep` `0.05 → 0.01` change
later reduced the error further; the current baseline is in the header.

Tracks whose first keyframe is at `t = 0` are numerically unchanged by both
conditions; the whole improvement comes from late-appearing actors.

**Provenance of these figures:** the values above are recorded in the
regression test docstring, which is the only committed record. The full
850-scene run artifact is local/private and is **not** committed, per
`docs/current/artifact-policy.md`. A run manifest with dataset version,
simulator version, git revision and per-scene values has not been attached to
this report.

## 4. What these numbers mean — and what they do not

This is the critical reading, and it must not be misreported.

**What the result does establish.** The exported OpenSCENARIO and the esmini
replay of that scenario now agree closely. The export → simulate round trip is
self-consistent, and the simulation has stopped fabricating motion that is not
in the recording. The previous ADE was dominated by an artifact — invented
travel in the pre-trigger window — not by genuine trajectory divergence.

**What the result does not establish.** This metric compares the exported
scenario against esmini's replay of that same scenario. It is a
**self-consistency** measure. It is **not** replay fidelity against the recorded
nuScenes driving trajectory, which is the measurement that would justify a
claim about simulation faithfulness. That measurement remains unavailable and
is blocked by the open CP1 lane road-match result (`20/143 = 13.99%`).

Driving a self-consistency metric toward zero is exactly the circularity
`MVP&ProjectSummary.md` R3 warns about. The improvement here is real — it is
backed by a concrete bug mechanism, not by tuning — but it is an **engineering**
result about the export/simulate boundary, and it does not promote the
scientific status of replay fidelity.

**These numbers therefore remain `PROVISIONAL`.** No ADE/FDE threshold is
proposed, no pass/fail claim is created, and the prediction-versus-replay metric
separation is unchanged.

## 5. Consequences for earlier evidence

- The ADE/FDE figures in `docs/reports/cp3-benchmark-run-evidence.md`
  (`mean 15.31`, `median 0.29`, and the per-scene `0.03 / 2.6 / 11.7 / 43.1 m`)
  were produced with the **previous** exporter semantics and **must not be
  quoted as current**. They are retained only as the pre-fix record.
- Any conclusion drawn from those values needs re-establishing under the new
  exporter.
- CP1, CP3, CP4 and CP5 statuses are unchanged. CP1 remains `20/143 = 13.99%`.
- The five-scene index, gate funnel and provisional benchmark protocol are
  unaffected in structure; only replay-derived error magnitudes change.

## 6. Open items

1. Attach the 850-scene run manifest (dataset version, esmini version, git
   revision, per-scene values) so this report has committed provenance.
2. Re-run the five-scene provisional benchmark under the new exporter so the
   CP3 evidence report has a current self-consistency figure.
3. Keep the two metric roles explicitly separate in every report and in any
   presentation: **self-consistency** (this report) versus **replay fidelity
   versus recorded data** (still unavailable).

## 7. Boundaries

- Raw nuScenes data and derived artifacts stay local and uncommitted.
- The canonical schema, CP1 baseline and matcher tolerances are unchanged.
- No threshold was tuned to produce this result; the defect was a contract
  violation and the fix restores the recorded semantics.
- CARLA remains unverified and post-MVP; this evidence is esmini only.