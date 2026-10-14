# CARLA Recorded-Trajectory Replay Research

Status: `RECOMMENDED IMPLEMENTATION`  
Updated: 2026-10-13

## Decision

Implement CARLA as a native, open-loop recorded-trajectory backend with two
explicit execution modes:

1. `exact_pose`: replay the canonical actor pose at each source timestamp using
   synchronous CARLA ticks and physics disabled for replay actors. This is the
   fidelity path and the only mode that may claim pose-replay accuracy.
2. `physics_controller`: keep physics enabled and drive actors with a controller
   or velocity/acceleration commands. This is the behavior/vehicle-dynamics path
   and must report its own error metrics. It must not be mixed with
   `exact_pose` metrics.

The project should not attempt to solve this with Traffic Manager, a route
destination, or a generic OpenSCENARIO behavior alone. Those mechanisms are
designed to choose safe/legal motion and will change the trajectory precisely in
the collision, sidewalk, wrong-way, abrupt-braking and near-collision cases that
this project needs to reproduce.

The practical pipeline is:

```text
nuScenes adapter
  -> canonical time-indexed Scenario
  -> explicit nuScenes/local -> CARLA alignment artifact
  -> actor blueprint and origin mapping
  -> CARLA exact_pose or physics_controller backend
  -> synchronized trace and optional sensor frames
  -> existing metrics, gates and reports
```

This resolves the central difficulty identified in
`2025-01-805902-02-202501_16_002.md`: the source trajectory is the authority in
the area of interest, while CARLA's road planner and collision avoidance are
not allowed to silently replace it.

## What Research Confirms

### Ai et al. extension paper

The supplied paper, *Reproduction of Real-World Scenarios in CARLA: An
Extension of CARLA Functionality* (Ai et al., 2025), takes the right conceptual
direction: inject timestamped waypoints and a velocity profile into the local
planner, disable collision and traffic-light restrictions when necessary, and
resume normal behavior outside the scripted region. Its reported nuScenes
experiment obtained an RMSE of 0.3831 m.

The important limitation is that this approach still routes the replay through
CARLA control/physics. A PID controller cannot guarantee that the vehicle is at
the requested pose at the requested timestamp, especially on curves or during
contacts. It is therefore useful for a physics/controller experiment, but not
the strongest baseline for proving exact recorded-pose reproduction. The paper
also requires a CARLA source modification and does not remove the independent
map-alignment problem.

### CARLA native API

The official CARLA Python API provides the primitives needed without changing
CARLA source:

- `Actor.set_transform()` applies a requested pose directly.
- `Actor.set_simulate_physics(False)` prevents physics from moving a replay
  actor away from the requested pose.
- `world.tick()` advances a synchronous simulation one step.
- `fixed_delta_seconds` gives simulation time a fixed increment.
- `client.apply_batch_sync()` allows per-tick commands to be sent as a batch.
- Sensor queues can be drained against the returned CARLA frame ID.

CARLA's synchrony documentation explicitly recommends synchronous mode plus a
fixed timestep when precise timing or sensor synchronization matters. It also
warns that variable timesteps accumulate floating-point and scheduling error.
For exact playback, this is more direct and more reproducible than using
Traffic Manager or a destination route.

References:

- [CARLA Python API](https://carla.readthedocs.io/en/latest/python_api/)
- [CARLA synchrony and timestep](https://carla.readthedocs.io/en/latest/adv_synchrony_timestep/)
- [CARLA repository](https://github.com/carla-simulator/carla)

### ScenarioRunner

ScenarioRunner is a traffic-scenario definition and execution engine. It
supports Python scenarios, OpenSCENARIO and scenario criteria. It does not
provide a native nuScenes recorded-track importer. It can be used later as an
orchestration or criteria layer, but a custom replay behavior would still be
needed and must remain the source of truth for recorded poses.

Do not make ScenarioRunner the canonical motion layer. Its route, behavior and
hazard abstractions are appropriate for generated or closed-loop scenarios, not
for forcing arbitrary unsafe recorded motion.

References:

- [ScenarioRunner documentation](https://scenario-runner.readthedocs.io/en/latest/)
- [ScenarioRunner repository](https://github.com/carla-simulator/scenario_runner)

### ScenarioNet

ScenarioNet is a valuable reference for dataset conversion and scenario
representation. It loads nuScenes, Waymo, nuPlan, Lyft and synthetic scenarios
for MetaDrive, not CARLA. Reuse its conceptual separation of dataset import,
scenario representation and simulator reconstruction, but do not introduce
MetaDrive as a second execution backend for the current Plan A.

Reference: [metadriverse/scenarionet](https://github.com/metadriverse/scenarionet)

### nuCarla and carla_nuscenes

These projects address the reverse direction: generating a nuScenes-compatible
dataset from CARLA. They are useful references for sensor metadata and output
layout, but they do not solve replaying real nuScenes tracks into CARLA:

- [nuCarla](https://github.com/michigan-traffic-lab/nuCarla)
- [carla_nuscenes](https://github.com/cf206cd/carla_nuscenes)

The CARLA Leaderboard is also not a replay solution. It evaluates an autonomous
agent driving a route to a destination, which is intentionally different from
replaying a recorded trajectory:

- [CARLA Leaderboard](https://github.com/carla-simulator/leaderboard)

## Why the Existing Spike Is Not Enough

The current `scripts/m5b_carla_spike.py` is a useful feasibility probe, but it
does not yet establish a production replay backend:

- It loads a built-in town and chooses a spawn-point anchor, not a measured
  map alignment.
- It uses direct transforms, but does not explicitly disable physics.
- It writes a minimal trace and does not synchronize sensor queues.
- It uses one fixed sample index per tick, so source timestamps are not handled
  when the source interval differs from the CARLA timestep.
- It does not batch transform commands.
- It only tests an ego actor plus one vehicle.
- It does not distinguish exact pose replay from physical behavior replay.

This agrees with `docs/evidence/m5-simulators/m5b-carla-feasibility-evidence.md`:
the environment result was a setup blocker, not evidence that CARLA cannot
support the feature. The implementation should remain deferred until a
reproducible CARLA server/client environment is available.

## Required Alignment Contract

The difficult part is not calling `set_transform`; it is deciding whether the
CARLA world represents the source scene well enough for the result to be useful.
Every CARLA run must carry an immutable alignment artifact containing:

- source dataset/version, scene and sample/annotation tokens;
- source coordinate frame and canonical coordinate frame;
- CARLA world/town and CARLA release/server version;
- SE(2) translation and yaw, with optional z/elevation correction;
- anchor correspondences used to fit the transform;
- position and heading residual for every anchor;
- actor origin convention (box center, rear axle, or blueprint origin);
- source dimensions and selected CARLA blueprint/dimension consequence;
- road/lane match result and unmatched/outlier samples;
- map reconstruction mode and its explicit fidelity claim.

The adapter must fail closed when the source is not in
`local_road_aligned` coordinates or when the alignment residual exceeds the
declared policy. A built-in CARLA town with a similar visual layout is not a
nuScenes map conversion and must be reported as `built-in-world` approximation.

## Exact Pose Backend

### Per-run setup

1. Connect to a version-compatible CARLA server and record client/server
   versions.
2. Load the declared world and configure synchronous mode before replay.
3. Use a fixed timestep `dt` selected from the canonical replay grid. For
   nuScenes 2 Hz keyframes, interpolate trajectories to a declared grid such as
   20 or 30 Hz; do not assume one source sample equals one CARLA tick.
4. Reload the world after applying settings when reproducibility requires it.
5. Spawn only actor categories with an explicit blueprint mapping.
6. Set `set_simulate_physics(False)` on each exact-replay actor. Do not register
   these actors with Traffic Manager.
7. Attach sensors only after actor spawning and record their configuration.

### Per-tick loop

For replay time `t_k`:

1. Interpolate each actor's canonical trajectory at `t_k` using a documented
   position/yaw interpolation policy. Use shortest-path yaw interpolation.
2. Convert each interpolated state into a CARLA `Transform`, including the
   actor-origin correction and alignment transform.
3. Submit all actor transform commands in one `apply_batch_sync` call.
4. Call exactly one `world.tick()`.
5. Read the world snapshot and drain each sensor queue until the matching frame
   is received. Preserve the source timestamp, requested transform, observed
   transform, CARLA frame ID and sensor frame ID together.
6. Record observed velocity/acceleration as measurements, not as commands. A
   teleported actor's physical derivatives are not equivalent to a real vehicle
   dynamics trace.

The implementation must never advance the world from more than one client.
Timeouts, missing sensor frames, failed batch responses and actor destruction
must be fatal run events and must appear in the manifest.

### Minimal pseudocode

```python
settings = world.get_settings()
settings.synchronous_mode = True
settings.fixed_delta_seconds = replay_dt
world.apply_settings(settings)

for actor in replay_actors:
    actor.set_simulate_physics(False)

for sample in replay_grid:
    commands = [
        carla.command.ApplyTransform(
            actor,
            to_carla_transform(sample.state(actor_id), alignment, origin),
        )
        for actor_id, actor in replay_actors.items()
    ]
    response = client.apply_batch_sync(commands, do_tick=False)
    assert all(not item.error for item in response)
    frame = world.tick()
    sensors = read_sensor_frames(frame)
    write_trace(sample, frame, replay_actors, sensors)
```

The exact command class/API spelling must be checked against the pinned CARLA
release. The contract matters more than copying this pseudocode literally.

## Physics/Controller Backend

This mode implements the supplied paper's idea without confusing it with exact
replay:

- keep physics enabled;
- supply timestamped reference waypoints and target speed/acceleration;
- use a low-level controller or CARLA vehicle control;
- disable collision/traffic-light avoidance only for explicitly declared
  safety-critical actors;
- retain high-frequency target profiles and record the applied control;
- measure pose, heading and speed error against the canonical trajectory.

This mode is valuable for root-cause and dynamics experiments, but its success
criterion is not exact pose equality. It should be run only after `exact_pose`
has established that alignment and source timing are correct.

## Trace and Metrics Contract

Extend the existing normalized CARLA trace so each actor sample includes:

- `source_timestamp_s` and `replay_timestamp_s`;
- `carla_frame_id` and `tick_index`;
- requested and observed position, yaw and velocity;
- `replay_mode` (`exact_pose` or `physics_controller`);
- actor blueprint and origin convention;
- alignment residual at the sample;
- sensor frame IDs and timestamps when sensors are enabled;
- command/batch error, dropped sample and timeout status.

Report at least:

- ADE/FDE per actor and aggregate;
- maximum position error and 95th percentile position error;
- heading and speed error;
- source-to-CARLA timestamp skew;
- road/lane match rate;
- dropped/unmatched sample count;
- sensor frame completeness and frame-to-source timestamp mapping;
- cleanup completeness and world-settings restoration.

Keep alignment error, exact-pose replay error and physics/controller error as
separate fields. A low replay error on a badly aligned built-in world is not
evidence of map fidelity.

## Implementation Order for This Repository

1. Keep the canonical `Scenario` and existing esmini path unchanged.
2. Add a versioned alignment model and validator beside the existing
   `CarlaAnchor` mapping. Preserve source scenario immutability.
3. Add a CARLA environment preflight that records server/client/world/version
   and fails without a compatible runtime.
4. Refactor the current spike into an `exact_pose` runner with fixed source-time
   interpolation, physics disabled, batched commands, frame-linked traces and
   guaranteed cleanup.
5. Run ego plus one vehicle on a synthetic fixture before using licensed
   nuScenes artifacts.
6. Add camera/LiDAR/radar queue capture only after transform traces pass.
7. Add `physics_controller` as a separate backend mode and compare it against
   exact-pose replay on the same alignment artifact.
8. Only then consider ScenarioRunner integration for criteria/orchestration or
   custom OpenSCENARIO execution.

## Acceptance Gates

CARLA replay remains `UNVERIFIED` until all of the following are demonstrated:

- compatible server/client versions and reproducible launch;
- synchronous fixed-step execution is observable in the manifest;
- alignment artifact is present and residuals pass its declared threshold;
- ego and one vehicle spawn with explicit blueprint/origin mapping;
- three consecutive exact-pose runs have equivalent sample counts and bounded
  observed-vs-requested transform error;
- sensor frames, if enabled, are linked to CARLA frame IDs and source times;
- failed runs destroy all spawned actors and restore world settings;
- exact-pose and physics/controller metrics are reported separately.

Until these gates pass, keep the existing decision in
`docs/evidence/m5-simulators/m5b-carla-feasibility-evidence.md` as `DEFER` and
continue using esmini for the deterministic MVP replay baseline.

## References

- Ai, Yan et al., *Reproduction of Real-World Scenarios in CARLA: An
  Extension of CARLA Functionality*, 2025. Local reference:
  `2025-01-805902-02-202501_16_002.md`.
- Dosovitskiy et al., *CARLA: An Open Urban Driving Simulator*, CoRL 2017:
  <https://proceedings.mlr.press/v78/dosovitskiy17a.html>.
- Wang et al., *AdvSim: Generating Safety-Critical Scenarios for Self-Driving
  Vehicles*, CVPR 2021.
- Rempe et al., *Generating Useful Accident-Prone Driving Scenarios via a
  Learned Traffic Prior*, CVPR 2022.
- ScenarioNet paper and code: <https://arxiv.org/abs/2306.12241> and
  <https://github.com/metadriverse/scenarionet>.
- CARLA API and synchronization documentation linked above.
