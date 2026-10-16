# nuScenes To XOSC Real2Sim Coverage And Correctness Metrics

Status: `ANALYSIS / 2026-10-16`

## Executive Summary

The current nuScenes-to-XOSC path is a trajectory replay conversion, not a
complete world reconstruction. It covers the selected ego and actor tracks,
their timing, position, heading and dimensions, and a template OpenDRIVE road
context. It does not carry the full sensor stream, original map geometry,
traffic-light state, actor appearance metadata or closed-loop behavior.

The central correctness question is therefore:

> Did the conversion preserve the selected recorded trajectories, identities,
> timing, coordinate convention and actor population without inventing motion?

It is not:

> Did the simulator recreate the original nuScenes world or sensor pixels?

## Current Coverage

### Input coverage

The ingestion path reads the selected scene/window and builds:

- chronological keyframe timestamps;
- ego positions and headings from `ego_pose`;
- selected vehicle annotations from `sample_annotation`;
- stable instance identity through `instance_token`;
- category and dimensions;
- finite-difference speed, optionally replaced by matched CAN speed;
- source timestamps and source annotation/pose tokens;
- a declared coordinate frame and transform provenance.

Actor selection is explicit and currently vehicle-oriented. The web scene import
may select a bounded interaction set, rather than exporting every object in the
scene.

### XOSC coverage

The exporter writes:

- one `ScenarioObject` per canonical actor;
- vehicle dimensions and basic performance limits;
- an initial teleport position;
- initial target speed `0`;
- one `FollowTrajectoryAction` per actor;
- time-indexed `Polyline` vertices containing position and heading;
- `TrajectoryFollowingMode followingMode="position"`;
- a start trigger at each actor's first trajectory time;
- a scenario stop trigger based on scenario duration;
- a selected local OpenDRIVE template reference.

### Not covered in XOSC

- Raw camera, LiDAR or radar observations.
- Sensor calibration and sensor noise.
- Original traffic-light state and signal timing.
- Full map topology and exact source-world geometry when a template is used.
- Actor attributes, visibility and point-support quality.
- Pedestrians/cyclists unless the exporter policy is expanded.
- Explicit dynamic spawn/despawn semantics beyond action timing.
- Closed-loop policy behavior or physical interaction.
- Original object meshes, textures, lighting or weather.

## How Missing Data Affects Real2Sim

| Missing or reduced input | Effect |
|---|---|
| Actor lifecycle metadata | Actors may be treated as present outside their observed interval. |
| Unselected actors | Interaction and crowd context can be incomplete. |
| Visibility and point counts | Weak or occluded tracks can be treated as equally reliable. |
| Attributes | Parked, stopped and moving objects are harder to interpret. |
| Exact map geometry | Road/lane relationships can be approximate even when actor motion is correct. |
| Traffic context | Braking or stopping cannot be causally attributed to a recorded signal. |
| Sensor calibration/data | Sensor-level correctness cannot be evaluated. |
| High-frequency samples | Timing and interpolation error can be hidden between keyframes. |
| Actor model/physics | Dimensions may be correct while physical response remains unverified. |
| Closed-loop behavior | Replay proves reference tracking, not autonomous behavior. |

## Correctness Metrics

### 1. Population and identity preservation

Report per scenario:

```text
source_actor_count
exported_actor_count
matched_actor_count
missing_actor_ids
unexpected_actor_ids
duplicate_actor_ids
```

Acceptance target for a selected export: `100%` identity preservation. If the
export intentionally selects a subset, report the selection policy and the
excluded population explicitly.

### 2. Timestamp preservation

For every actor, compare source trajectory timestamps with exported vertex times:

```text
max_abs_time_error_s
mean_abs_time_error_s
timestamp_monotonicity_failures
start_time_error_s
end_time_error_s
```

Expected result for deterministic serialization is zero or a documented decimal
formatting tolerance.

### 3. Coordinate and transform correctness

Validate source-to-canonical conversion before simulator comparison:

```text
position_round_trip_error_m
yaw_round_trip_error_rad
origin_anchor_error_m
heading_anchor_error_rad
coordinate_frame_label_match
```

Use known anchor states and round-trip transforms. A low simulator ADE cannot
compensate for an incorrect coordinate convention.

### 4. Initial-state correctness

For each actor:

```text
initial_position_error_m
initial_heading_error_rad
initial_dimension_error_m
initial_speed_error_mps
```

The current exporter intentionally initializes speed to zero, so any nonzero
source initial speed should be reported as a policy difference rather than
silently treated as a conversion success.

### 5. Replay trajectory error

Compare native esmini replay states to source states at matched actor/time pairs:

```text
position_error_m: mean, median, p95, max
along_track_error_m
cross_track_error_m
heading_error_rad
speed_error_mps
FDE at actor end time
coverage_ratio
```

Use both aggregate and per-actor distributions. The current project already
uses ADE/FDE, but along/cross-track decomposition is more diagnostic for map
alignment and trajectory-following errors.

### 6. Timing and lifecycle correctness

Measure:

```text
first_motion_time_error_s
actor_spawn_time_error_s
actor_despawn_time_error_s
active_actor_count_error_over_time
late-start actor position error
```

This catches the historical failure mode where every actor action started at
time zero and late-starting trajectories were consumed too early.

### 7. Motion-shape correctness

Compare the source and replay derivatives:

```text
speed RMSE
acceleration RMSE
yaw-rate RMSE
jerk distribution difference
stop duration difference
```

These metrics must be labeled as replay fidelity, not as evidence that the
original vehicle used the same controller or physics model.

### 8. Map and lane validity

For each replay state, report:

```text
drivable-area occupancy rate
lane match rate
wrong-direction rate
lane continuity failures
road-boundary violations
```

Separate source-map oracle results from template-OpenDRIVE results. A template
can produce a valid XOSC while still being an inaccurate reconstruction of the
original map.

## Recommended Real2Sim Acceptance Card

Every conversion benchmark should include:

```text
dataset/version/scene/window
actor selection policy and counts
source and exported timestamps
coordinate transform version
map/template identity
native esmini version and timestep
identity preservation
initial-state errors
ADE/FDE and along/cross-track errors
timing/lifecycle errors
lane/drivable validity
unavailable capabilities
```

The acceptance card should be generated from private artifacts and preserve
source tokens without publishing raw data.

## Interpretation

The current path is strong for deterministic open-loop trajectory replay. It is
not sufficient to claim sensor replication, exact world reconstruction or
closed-loop driving behavior. The most valuable correctness additions are
actor lifecycle metrics, source-to-local transform round trips, per-actor
timing checks, along/cross-track error, and map-validity reporting.

## Phase 1-2 Implementation Status

Implemented as additive, default-preserving changes:

| Priority | Status | Evidence |
|---|---|---|
| 1 Actor lifecycle | Implemented as inert metadata | `Actor.observed_start_s`, `observed_end_s`, `observation_count`, `lifecycle_status()`; exported as entity `Property` entries |
| 2 Actor category/type | Implemented conservatively | `_vehicle_category()` maps bicycle/bus/motorcycle/trailer/truck; unknown subtypes stay `car` and the source taxonomy is always preserved |
| 3 Initial motion | Recorded, behaviour unchanged | `recorded_initial_speed_mps` and `initial_speed_policy` properties; the zero initial `AbsoluteTargetSpeed` that the measured baseline depends on is untouched |
| 4 Trajectory timing | Implemented as metadata | `trajectory_time_origin_s`, `trajectory_last_vertex_s`; the `position` mode and `relative`/`offset=0` timing are unchanged |
| 5 Provenance properties | Implemented | `source_actor_id`, `source_actor_type`, `coordinate_frame`, `replay_mode`, `coordinate_transform_version`, `opendrive_template_id` |
| 6 Road/lane context | Partially delivered | Real recorded dimensions and centre offsets now drive the OpenDRIVE-facing cuboid instead of hardcoded constants; lane/marking enrichment remains in the map builder, not the exporter |
| 7 Traffic signals | **Blocked, deliberately not implemented** | The source has no recorded signal-state mapping, and inferring one from braking is exactly the invented-fact failure this project forbids |
| 8 Environment | **Blocked by the fail-closed subset** | `parse_xosc_subset` rejects `/OpenSCENARIO/Environment`; loosening it is a safety decision, not a data decision |
| 10 Interaction events | Canonical model only | `InteractionEvent` with required `derivation` and validated actor membership; not emitted into XOSC because no inert, validator-approved representation exists |

Deliberately unchanged: trajectory vertices, `followingMode="position"`,
per-actor `StartTrigger` timing, zero initial speed, Act/Story structure, and
the scenario stop triggers. These define the measured replay baseline, so no
metric-affecting element was touched. Priorities 7 and 8 remain unavailable
rather than approximated.
