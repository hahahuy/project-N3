# Late-Future Multi-Dataset Platform Plan

Status: `APPROVED FUTURE DIRECTION`  
Current MVP impact: `NONE`

## Purpose

After the Plan A nuScenes/esmini/CARLA path is stable, Real2Scenario may evolve
into a platform for evaluating recorded driving, LiDAR and trajectory datasets
through one auditable canonical pipeline.

This plan does not expand the current CP0-CP6 acceptance scope.

## Target Architecture

```text
DatasetAdapter -> canonical Scenario/provenance/capabilities
  -> MapProvider -> OpenSCENARIO -> SimulatorBackend
  -> NormalizedReplayTrace -> metrics/gates/reports/UI
```

The core pipeline must not branch on dataset names. Dataset-specific logic stays
inside adapters.

## Priorities

### LF-1 — Freeze the Canonical Boundary

Define stable interfaces for dataset descriptors, scene descriptors,
capabilities, raw timestamps/tokens, coordinate frames, map references, sensor
descriptors and license/artifact metadata. The nuScenes adapter must preserve
its current provenance at the canonical boundary.

### LF-2 — Extract `NuScenesAdapter`

Move current nuScenes ingestion/scene discovery behind a formal adapter without
changing canonical artifact semantics. Existing scene-0061 extraction tests must
remain equivalent.

### LF-3 — Capability Matrix

Every dataset/backend publishes `available`, `unavailable`, `partial`,
`unverified` or `unsupported` capabilities for tracks, ego pose, lane map,
LiDAR, camera, radar, planning data, calibration and control data.

### LF-4 — Add One Second Dataset

Only after CP1/CP2/CP5 stabilization, add one external dataset. Default
candidate: **Waymo Open Motion** for trajectory/canonical adapter validation,
subject to package and license review. Choose **nuPlan** instead only if the
research direction becomes planning/ego behavior. Treat **ScenarioNet** as a
representation/conversion ecosystem unless a specific source dataset is
selected.

### LF-5 — Generalize Map Providers

Support `NuScenesVectorMapProvider`, `OSMReferenceProvider`,
`LiDARDerivedMapProvider` and `SurveyedVectorMapProvider`. NuScenes remains the
current canonical CP1 source; OSM remains auxiliary.

### LF-6 — Generalize Simulator Backends

Keep `capabilities()`, `validate_request()`, `run()`, `normalize_trace()` and
`cleanup()` independent from dataset adapters. Do not add a third simulator to
current Plan A scope.

### LF-7 — Separate Sensor and Trajectory Evaluation

Use modality-specific contracts for LiDAR, camera, radar and IMU/GNSS. Sensor
projection is not ADE/FDE trajectory fidelity.

### LF-8 — Trustworthiness Matrix

Report schema, geometry, replay, variant and cross-dataset trustworthiness
separately. Do not aggregate datasets until annotation/timebase/map semantics are
comparable.

### LF-9 — License Gates

Every adapter declares license, non-commercial, attribution, ShareAlike,
privacy and artifact visibility rules before public release.

### LF-10 — Benchmark/Paper Extension

After one second adapter is stable, add a capability-normalized benchmark and a
new research question only after owner approval.

## Activation Gate

Late-future work begins only after CP1 corridor, CP2 same-XOSC and CP5 package
are reviewable, an owner-approved second dataset exists, and its license policy
is documented.
