# Dynamic Single-Track and CARLA Experiment Plan

Status: `APPROVED FOR EXECUTION / DIAGNOSTIC ONLY`

## Objective

Build and execute two isolated experiment arms for one authored vehicle
trajectory:

1. `dynamic-single-track-v1`: deterministic planar dynamic bicycle/single-track
   prototype with explicit parameters and diagnostics.
2. CARLA direct exact-pose feasibility run using the existing CP2-A contracts,
   not a same-XOSC claim unless the runtime actually consumes the same XOSC/XODR
   bytes.

The existing Tier 0 esmini replay and Tier 1 authoring preview remain unchanged
as scientific/runtime boundaries. Tier 2 outputs are diagnostic and must not
feed ADE/FDE claims, ranking, gates, or sensor-evidence claims.

## Execution Context

- Worktree: `/home/hahuy/github/project-N3-motion-editor`
- Branch: `feature/canvas-motion-branch`
- Input frame: `local_road_aligned` (`x` forward, `y` left, `z` up)
- Population: one vehicle actor per run
- Timestep: `0.01 s` for dynamic prototype; CARLA spike follows its declared
  synchronous setting and records the actual value
- CARLA world: explicit built-in world, no lossless nuScenes map claim
- Persistence: local experiment artifacts only; no production API integration

## Workstreams

### A. Dynamic single-track domain

Add a standalone module and tests. The module consumes an initial `State` plus
explicit steering/longitudinal profiles and emits a normalized trace plus
internal dynamic state and diagnostics. It must fail closed at low speed and
never silently clamp or project state.

Initial equations:

```text
alpha_f = delta - atan2(vy + lf*r, vx)
alpha_r = -atan2(vy - lr*r, vx)
Fyf = Cf * alpha_f
Fyr = Cr * alpha_r
vx_dot = ax + r*vy
vy_dot = (Fyf + Fyr)/m - r*vx
r_dot  = (lf*Fyf - lr*Fyr)/Iz
```

Use midpoint/RK2 integration with a fixed step and explicit versioned default
parameters marked synthetic, not nuScenes ground truth.

### B. Comparison metrics and artifact bundle

Use the frozen authored trajectory as reference. Resample candidates at
reference timestamps without extrapolation. Report per-state and per-run:

- position error, ADE, FDE, RMSE, median, p95 and max;
- wrapped yaw error;
- speed error;
- longitudinal/lateral error only when trusted lane tangent data exists;
- coverage class and overlap interval;
- feasibility violations;
- collision status and method provenance;
- solver/profile/timestep/parameter hashes.

The result must distinguish authored-vs-parent edit magnitude from
candidate-vs-authored execution error.

### C. CARLA runtime

Run the existing `scripts/archive/carla/m5b_carla-preflight.sh` and
`m5b_carla_spike.py` path first. Do not create a new CARLA adapter until:

- server accepts a client connection;
- client/server versions are recorded;
- a built-in world loads;
- synchronous mode and fixed timestep are observable;
- one ego + one vehicle can spawn;
- trace and cleanup artifacts are produced three times.

If the container crashes, record the exact signal/log and debug the container
launch independently. A Docker `running` status is not sufficient.

### D. QC

Run the full Python suite, focused prototype/CARLA contract tests, frontend
regression tests, `git diff --check`, and GitNexus change detection. Do not
commit or publish the dirty experimental branch automatically.

## Success Criteria

### Dynamic arm

- deterministic repeated trace;
- synthetic constant-speed/constant-curvature sanity case passes tolerances;
- low-speed guard and non-finite/invalid parameter failures are explicit;
- no parent mutation;
- metric bundle is reproducible and labels Tier 2 diagnostic status.

### CARLA arm

- three consecutive successful runs with stable sample count/timebase;
- explicit world/client/server/runtime manifest;
- direct transforms applied per synchronous tick;
- normalized trace written;
- actor cleanup and world-setting restoration evidenced;
- comparison metrics computed against the same authored reference.

### Blocked outcome

If CARLA cannot launch after bounded debugging, report `DEFERRED_RUNTIME_BLOCKED`
with logs and preserve the dynamic arm and comparison protocol. Do not claim a
CARLA comparison success from an unconnected container.

## Explicit Non-Goals

- no frontend integration;
- no Tier 2 API endpoint;
- no CARLA same-XOSC claim from direct exact-pose;
- no sensor regeneration;
- no lane snapping;
- no CARLA physics/controller conclusion from physics-disabled exact-pose;
- no final scientific thresholds.
