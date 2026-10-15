# Multi-Dataset Platform Direction

Status: `FUTURE DIRECTION`  
Current Plan A scope remains nuScenes-first.

## Feasibility

Yes, the project can evolve into a platform for evaluating driving LiDAR and
trajectory datasets from multiple sources. The reusable product is not the
nuScenes table reader; it is the contract around:

```text
source adapter
  -> canonical scenario
  -> map/geometry adapter
  -> OpenSCENARIO artifact
  -> esmini/CARLA execution
  -> normalized trace
  -> ADE/FDE, coverage, gates and reports
```

## Required Adapter Contract

Each dataset adapter must provide:

- dataset/version identity;
- scene/window identity;
- actor/track identity and category mapping;
- raw source timestamp and record-token provenance;
- ego pose and actor trajectories;
- coordinate frame and versioned transforms;
- actor dimensions and source confidence;
- map/geometry linkage or an explicit `map_unavailable` status;
- sensor channel/calibration metadata when LiDAR/camera evaluation is enabled;
- license and artifact visibility metadata.

## What Stays Dataset-Agnostic

- canonical `Scenario`, `Actor` and `State` contracts;
- variant generation and deterministic provenance;
- replay trace normalization;
- ADE/FDE and coverage evaluation;
- G1-G7 gate/report interfaces;
- simulator backend contracts;
- UI layer/POV/actor-edit concepts.

## What Must Stay Adapter-Specific

- raw table/file layout;
- object taxonomy and track stitching;
- sensor calibration format;
- map projection and georeferencing;
- map confidence and missing-data policy;
- source license constraints;
- source-specific sensor preprocessing.

## LiDAR Dataset Modes

The future platform should support explicit capability modes:

- `trajectory_and_map`: best for replay/map evaluation;
- `trajectory_only`: replay without map-fidelity claims;
- `sensor_rich`: adds LiDAR/camera projection and sensor metrics;
- `map_only`: map alignment/build validation without actor replay.

Missing capabilities must be represented in manifests and reports. A dataset
without map data must not silently inherit nuScenes map assumptions.

## Migration Strategy

1. Finish the current nuScenes Plan A corridor and CP2 contracts.
2. Freeze the canonical scenario and trace schemas.
3. Extract nuScenes ingestion behind a formal dataset adapter interface.
4. Add one second dataset adapter using synthetic or legally distributable data.
5. Compare adapter output at the canonical-schema boundary before simulator or
   evaluator comparison.
6. Add dataset capability matrices and per-dataset license policies.

The platform direction does not authorize publishing any restricted dataset or
derived artifact and does not change the current Plan A acceptance criteria.
