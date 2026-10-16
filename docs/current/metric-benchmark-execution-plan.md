# Metric and Benchmark Execution Plan

Status: `APPROVED NEAR-FUTURE WORK PLAN`  
Scope: CP3 metric refinement and full-dataset benchmark preparation

## Purpose

Use the complete local `nuScenes v1.0-trainval` dataset to improve metric
provenance, benchmark statistical quality and failure analysis without changing
the approved ground-truth policy or turning provisional thresholds into final
scientific claims.

Default local dataset configuration:

```text
NUSCENES_ROOT=/mnt/backup/nuscenes
NUSCENES_VERSION=v1.0-trainval
```

Raw and nuScenes-derived artifacts remain local/private.

## Non-Negotiable Measurement Policy

- Raw nuScenes annotation and ego-pose keyframes remain the ground truth.
- Do not compare against smoothed trajectories as a replacement ground truth.
- Do not change ADE/FDE thresholds in this work plan.
- Do not mix template replay, corridor replay and full benchmark results into one
  undifferentiated score.
- Do not treat an intentionally edited variant as expected to match the original
  recorded trajectory.
- Tier 0 esmini replay remains the fidelity measurement path; Tier 1 preview
  output is not its own evaluation oracle.
- Every result retains dataset, scene, map/template, simulator, run, seed,
  actor-selection and configuration provenance.

## Metric Roles

### Recorded-vs-replayed fidelity

Primary baseline metric:

```text
raw nuScenes trajectory -> OpenSCENARIO/esmini replay
```

Report per actor and per scene:

- ADE;
- FDE;
- position RMSE;
- heading MAE;
- speed MAE;
- coverage status and ratio;
- overlap duration;
- aligned sample count;
- track duration.

### Generated-vs-replayed self-consistency

Secondary engineering metric:

```text
generated/canonical trajectory -> OpenSCENARIO/esmini replay
```

Label this separately as export/replay self-consistency. It measures XOSC and
esmini execution fidelity, not similarity to recorded nuScenes behavior.

### Edited-variant effect

Edited variants must report their intentional change separately:

- position delta from parent;
- speed delta;
- timing delta;
- initial-gap delta;
- generated-vs-replayed self-consistency;
- feasibility and gate status.

Do not use high recorded-vs-replayed error for an intentionally edited variant
as evidence that the edit or replay pipeline failed.

## Aggregation

Produce both levels:

- per-actor metrics for diagnosis;
- per-scene macro aggregates so every scene contributes equally;
- pooled actor-track micro aggregates as a secondary view.

The primary dataset summary should be scene-macro, not only pooled states or
actor tracks. Report mean, median, p95 and max for ADE/FDE, plus the number of
scenes and actor tracks contributing to each statistic.

FDE reporting must include availability counts:

```text
FDE available: N / M actor tracks
FDE unavailable: K tracks, reason=insufficient_coverage or no_overlap
```

Missing FDE remains `null`/`n/a`, never zero.

## Coverage and Alignment

Extend metric output with:

- recorded start/end timestamps;
- replay start/end timestamps;
- overlap duration;
- coverage ratio;
- aligned sample count;
- expected sample count;
- coverage class: `complete`, `partial`, `insufficient` or `no_overlap`.

Replay states may be linearly interpolated at recorded timestamps only within
the overlap interval. No extrapolation is allowed.

## Baselines and Uncertainty

Add an interpolation/quantization floor by resampling a trajectory to the
replay time grid and back to the recorded keyframes. Report this as a numerical
baseline, not as a scientific threshold.

Add scene-level bootstrap confidence intervals for descriptive ADE/FDE summaries.
Bootstrap units must be scenes, not individual highly correlated states.

Suggested output:

```text
ADE macro mean: 0.42 m
95% scene bootstrap CI: [0.36, 0.49] m
```

## Diagnostic Stratification

Where provenance supports it, stratify results by:

- scene and location;
- actor type;
- ego vs non-ego;
- track duration;
- speed range;
- straight vs turning motion;
- lane-changing or interaction class;
- template vs scene-local corridor;
- complete vs partial coverage;
- baseline vs edited variant.

For corridor-backed runs, add diagnostic lane-frame metrics without replacing
global metrics:

- longitudinal error;
- lateral error;
- heading error.

Lane-frame metrics remain diagnostic until CP1 semantic alignment is accepted.

## Benchmark Classes

Keep these benchmark classes separate:

### Class A: Template replay

Tests ingestion, XOSC export, esmini replay and metric plumbing. It does not
make a CP1 map-fidelity claim.

### Class B: Scene-local corridor replay

Tests nuScenes map reconstruction, road-match, topology and lane-frame
diagnostics. Results remain CP1 provisional evidence.

### Class C: Full approved benchmark

Uses an owner-approved scene index, frozen protocol and full-dataset provenance.
It supplies CP3 evidence only after the approval boundary is satisfied.

## Failure Accounting

Count failures by cause rather than only valid/invalid totals:

- schema invalid;
- kinematic invalid;
- road-match failure;
- collision failure;
- missing event definition;
- simulator failure;
- insufficient coverage;
- no overlap;
- unsupported dimensions;
- unsupported actor type.

Keep variant funnel results separate from replay metric distributions.

## Execution Order

1. Extend metric schemas with role, provenance, coverage and availability fields.
2. Add explicit recorded-vs-replayed and generated-vs-replayed computation.
3. Add scene-macro and actor-track micro aggregation.
4. Add FDE availability accounting and overlap classes.
5. Add interpolation-floor measurement.
6. Add scene-level bootstrap summaries.
7. Add lane-frame diagnostics where corridor geometry is available.
8. Freeze a full-dataset benchmark manifest and owner-approved scene split.
9. Run Class A, Class B and Class C separately and update the evidence index.

## Acceptance Boundary

This plan is complete when the metrics are role-separated, coverage and missing
data are explicit, scene-level aggregation and uncertainty are reproducible, the
benchmark manifest is frozen, and no provisional threshold or CP1 policy was
silently changed.

No result from this plan alone establishes CP1 acceptance, final ADE/FDE policy,
G6/G7 scientific thresholds, CP2 same-XOSC or CARLA runtime equivalence.
