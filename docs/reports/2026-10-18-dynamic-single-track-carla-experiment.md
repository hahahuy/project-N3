# Dynamic Single-Track and CARLA Experiment Report

Status: `DYNAMIC-SUCCESS / CARLA-EXACT-POSE-SMOKE-SUCCESS`

## Dynamic arm

Implemented `dynamic-single-track-v1` in:

```text
src/real2scenario/dynamic_single_track.py
```

The prototype is a separate Tier 2 diagnostic module. It does not modify
`State`, `ReplayTrace`, Tier 1 `kinematic-open-loop-v1`, XOSC export, replay
metrics, gates, or frontend behavior.

Properties:

- planar dynamic bicycle/single-track state `(x, y, yaw, vx, vy, yaw_rate)`;
- linear front/rear tire cornering forces;
- fixed-step midpoint/RK2 integration;
- explicit parameter version and synthetic default profile;
- low-speed fail-closed guard;
- explicit steering, acceleration, lateral-acceleration and non-finite diagnostics;
- normalized `State`/`ReplayTrace` output with Tier 2 provenance;
- no silent clamps or trajectory projection.

The constant-speed straight-line smoke case produced a final position of
`16.00000000000001 m` for an 8 m/s, 2-second input. The residual is numerical
roundoff at approximately `1e-14 m`. The prototype is deterministic across
repeated runs.

## Experiment metrics

Implemented `trajectory-experiment-metrics-v1` in:

```text
src/real2scenario/experiment_metrics.py
```

It aligns candidate states to the frozen reference time grid without
extrapolation and reports:

- coverage status;
- overlap interval and sample count;
- ADE/FDE;
- position RMSE, p95 and maximum;
- wrapped heading MAE and maximum;
- speed MAE and maximum.

This metric family is explicitly separate from official Tier 0 replay metrics.

## CARLA attempts and recovery

Container:

```text
carla
image: carlasim/carla:0.9.16
```

Initial observed behavior:

1. Container can report `running` and port `2000` can appear open.
2. CARLA Unreal process crashes during startup with `Signal 11` / `SIGSEGV`.
3. The same crash occurs after `docker restart carla`.
4. The same crash occurs with a bounded `-nullrhi` launch, so the failure is
   not limited to Vulkan/offscreen rendering.
5. Container logs show:

```text
CarlaUE4-Linux-Shipping ...
Signal 11 caught.
CommonUnixCrashHandler: Signal=11
CarlaUE4.sh: ... Segmentation fault
```

6. Host Python has no CARLA client package.
7. The container contains CARLA wheels for CPython 3.10, 3.11 and 3.12, but
   the project experiment environment cannot install the CPython 3.11 wheel
   into its CPython 3.12 environment.
8. No CARLA RPC handshake/version/world probe succeeded.

The initial failure was diagnosed as a CARLA/UE startup/runtime issue rather
than a scenario failure. After restarting the service and installing the
matching CPython 3.12 CARLA 0.9.16 wheel from the image, the RPC probe passed:

```text
client_version: 0.9.16
server_version: 0.9.16
world: Carla/Maps/Town10HD_Opt
```

The exact-pose smoke then passed with synchronous `0.05 s` ticks, one vehicle,
trace output and cleanup. Three consecutive stability runs also passed with
`10/10/10` ticks and the same server/world identity.

The CARLA run is still a **direct-transform feasibility arm**. Physics was
disabled and every pose was explicitly applied before each tick. It is not a
CARLA dynamics result and is not a same-XOSC claim.

## Comparison result

Reference: synthetic authored straight trajectory, 41 states, `0.05 s`, 4 m/s,
2 seconds.

| Arm | Coverage | ADE (m) | FDE (m) | Position RMSE (m) | Heading MAE (rad) | Speed MAE (m/s) |
|---|---:|---:|---:|---:|---:|---:|
| dynamic-single-track-v1 | complete | `2.63e-15` | `5.33e-15` | `3.23e-15` | `0` | `0` |
| CARLA direct exact-pose | complete | `2.43e-6` | `4.58e-6` | `2.88e-6` | `5.20e-10` | `0` |

The near-zero dynamic error is expected for the constant-speed straight-line
sanity case. The micrometre-level CARLA error is also expected: the actor pose
is directly teleported to the reference transform with physics disabled. It
does **not** measure vehicle dynamics, controller fidelity, map fidelity or
sensor fidelity.

Local-only artifacts were written outside the repository under:

```text
/tmp/project-n3-carla-run/
/tmp/project-n3-carla-comparison/comparison.json
/tmp/project-n3-carla-stability/stability.json
```

## Current decision

```text
dynamic-single-track-v1: SUCCESS for isolated synthetic prototype
experiment-metrics-v1: SUCCESS for isolated synthetic comparison metrics
CARLA RPC/runtime: SUCCESS for direct exact-pose smoke
CARLA stability: SUCCESS, three consecutive runs
CARLA dynamics/controller: NOT TESTED
same-XOSC evidence: NOT CLAIMED
sensor generation: NOT TESTED
```

## Current decision

```text
dynamic-single-track-v1: SUCCESS for isolated synthetic prototype
experiment-metrics-v1: SUCCESS for isolated synthetic comparison metrics
CARLA runtime: SUCCESS for direct exact-pose and physics-enabled smoke
CARLA curved controller: NOT ACCEPTED
same-XOSC evidence: NOT CLAIMED
```

## Recommended next step

Preserve the matched client setup and turn the ad-hoc direct-transform smoke
into a local-only reproducible runner. Keep it explicitly separate from
same-XOSC and from physics-enabled CARLA experiments. A future dynamics arm
must first define controller/physics inputs; direct exact-pose cannot answer
that question.

Do not add a production CARLA adapter or frontend selector until the runtime
passes the existing M5B gates: one world, ego plus one vehicle, synchronous
fixed timestep, normalized trace, cleanup, and three consecutive successful
runs.

## Physics-Enabled Edit-Object Comparison

An isolated runner was added at:

```text
scripts/experiments/run_physics_comparison.py
```

It runs the edited vehicle target through both `dynamic-single-track-v1` and a
CARLA physics-enabled `vehicle.tesla.model3`, using synchronous `0.05 s`
ticks, one-time initial velocity setup, a low-level throttle/brake speed PID,
a collision sensor, and the same normalized experiment metrics.

### Straight baseline

For a 6-second, 6 m/s straight path in `Town10HD_Opt` at spawn index 20:

```text
coverage: complete
collision_count: 0
CARLA position ADE: 0.522 m
CARLA position FDE: 0.420 m
CARLA position RMSE: 0.523 m
CARLA heading MAE: 0.000668 rad
CARLA speed MAE: 0.0541 m/s
```

This is a measurable physics-enabled straight-line result. It is not a
general vehicle-model accuracy claim because the initial velocity is set once
to establish the authored initial condition.

### Curved case

The same setup with constant steering input `0.06 rad` did not pass:

```text
CARLA position ADE: approximately 4.73 m
CARLA position FDE: approximately 17.92 m
speed MAE: approximately 3.00 m/s
collision events: 55
```

A follow-up heading/lateral-error feedback attempt avoided collisions but was
unstable and diverged further. This is not an approved curved-path controller
result. It indicates that direct steering mapping is insufficient for this
CARLA world/blueprint and that reference-point, road placement, steering
sign/scale, and controller calibration still need work.

The current evidence supports:

- deterministic dynamic single-track execution;
- working CARLA physics runtime and collision sensor;
- reasonably close straight-line speed tracking;
- no claim of high-fidelity curved tracking yet;
- strict separation between exact-pose and physics-enabled CARLA results.

The next engineering step is calibrated CARLA controller work: verify the
actor reference point and bounding-box offset, steering sign and scale, valid
road-aligned spawn, and a proper path-tracking controller against the dynamic
trace. Do not promote this experiment into the production Edit motion path
until curved tracking and collision behavior pass explicit thresholds.

## Follow-up Calibration Findings

The CARLA steering probe established:

- positive normalized steering produces positive yaw/lateral motion;
- negative normalized steering produces negative yaw/lateral motion;
- the `vehicle.tesla.model3` bounding-box local offset is approximately
  `(0.029, 0.000, 0.736) m` in the tested runtime;
- the actor transform and bounding-box center must not be treated as the same
  reference point without an explicit convention.

The curved analytic target used in the first runner was not map-native. It was
an abstract local curve placed at a CARLA spawn anchor. CARLA's built-in world
has its own road/lane geometry, so the curved result mixes controller error,
reference-point error and map/path mismatch. A pure-pursuit feedback attempt
did not produce a valid result and increased divergence.

The next valid benchmark must first sample a CARLA waypoint chain from the
selected lane, transform that chain into the experiment frame, and use that
map-native chain as the desired edited path. Only then should steering scale,
controller gains and physics tracking be compared.
