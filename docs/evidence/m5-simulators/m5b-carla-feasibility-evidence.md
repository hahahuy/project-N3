# M5B CARLA Feasibility Evidence

## Decision record (2026-10-10)

**Recommendation: DEFER CARLA integration.** The manual spike is not runnable in the current environment: no CARLA installation, server executable, Python client package, CARLA Docker image, or CARLA world assets were found. This is an environment blocker, not evidence that CARLA is technically unsuitable. Do not implement a CARLA backend or UI on this result. Keep esmini as the execution baseline and revisit only if CARLA-level 3D review, sensors, or closed-loop work becomes a confirmed requirement.

The esmini baseline is present under $HOME/esmini (esmini and dat2csv); the API Compose stack is healthy and mounts it read-only. A direct host probe reports missing libGL.so.1 for esmini, while dat2csv --help responds. This does not change the CARLA blocker and does not claim a fresh esmini replay.

## Reproducibility boundary

Run `scripts/m5b-carla-preflight.sh` from the repository root and attach stdout
to a local run record. It does not install or launch CARLA. Use
`docs/evidence/m5-simulators/m5b-manual-run-record.md`. Keep local paths,
binaries, recordings, credentials, and licensed data out of git.

Required environment record: CARLA server/client release and Python compatibility; native/Docker launch method and image digest; host OS/GPU/driver/RAM; port; one built-in world ID; scene-0061 artifact/revision and coordinate frame; synchronous fixed_delta_seconds=0.05; exact command, logs, exit/timeout, and cleanup evidence.

## Selected manual one-vehicle open-loop spike

Use scene-0061 because existing esmini evidence makes comparison possible. Run only ego plus one vehicle actor in one built-in CARLA world. Apply recorded transforms directly at each synchronous tick. This validates neither dynamics, controllers, autonomy, sensors, nor map fidelity.

### World and actor mapping policy

The world is a declared test fixture, not a nuScenes map conversion. Record world ID and reconstruction mode: built-in-world, no road-topology claim. Canonical vehicle actors require an explicit, versioned CARLA vehicle blueprint; the first run supports ego and one selected target vehicle only. Record spawn transform, heading, coordinate conversion, and any dimension consequence. Reject pedestrians, cyclists, arbitrary behaviors, traffic-manager behavior, sensors, and unknown actor types rather than silently approximating them.

### Fixed timestep, trace, and cleanup

Use synchronous world settings with fixed_delta_seconds = 0.05 seconds. Per tick record tick index, simulation time, actor ID, location, rotation, and velocity when available. Emit a normalized SI-unit trace with sample counts. Capture startup/runtime/completion, versions, exit status, stdout/stderr, and timeout. Save initial world settings; restore them and destroy every spawned actor in finally, including failure paths. A run without cleanup evidence is incomplete.

## Required environment gates

- [ ] Compatible Python and CARLA client; client/server versions recorded
- [ ] Server launches reproducibly and accepts the recorded port
- [ ] Selected built-in world loads and reloads
- [ ] Synchronous mode and fixed 0.05 s timestep are observable
- [ ] Ego and one vehicle blueprint spawn at valid transforms
- [ ] Open-loop trace, completion, and normalized artifacts are produced
- [ ] Cleanup restores world settings and destroys actors after success/failure
- [ ] Three consecutive runs have comparable sample counts and no unexplained failure

Any failed gate is DEFER unless the failure is a permanent scope mismatch, which is REJECT. Passing gates alone is not PROCEED.

## Comparison matrix

| Dimension | esmini baseline | CARLA evidence required | Signal |
|---|---|---|---|
| Setup | Present; mounted baseline; host GL caveat | versions, launch, image/client, world | repeatability |
| World/map | local OpenDRIVE template approximation | one declared built-in world | no lossless map claim |
| Playback | headless OpenSCENARIO + dat2csv | synchronous transform trace | same scenario/timebase |
| Actors | vehicle-oriented baseline | ego + explicit vehicle blueprint | no silent substitution |
| Trace/metrics | SI normalization and replay metrics | equivalent tick trace and metrics | sample alignment |
| Cleanup | process-scoped artifacts | actor destruction + settings restore | mandatory, three runs |
| Review value | limited/local optional viewer | measurable reviewer value | must be material |
| Sensors/closed loop | not provided | only if required and evidenced | possible M6 value |
| Cost/risk | known dependency | install/GPU/maintenance burden | record, do not guess |

## Explicit decision criteria

**PROCEED to M6** only if every gate passes, three consecutive runs produce trace and cleanup evidence, CARLA provides material value beyond esmini (required 3D review, required synthetic sensors, or credible closed-loop path), and the team approves setup/maintenance cost.

**DEFER** when setup is blocked or value/cost remains unproven. Current decision: DEFER.

**REJECT** when a reproducible spike shows CARLA cannot support the selected scope, offers no material value over esmini, or required fidelity would require misleading map/actor approximation. Until a PROCEED decision, do not build a CARLA backend, selector, adapter, or shared abstraction.

## Expected local-only evidence

Preflight output; launch/version record; scenario/world/settings manifest; normalized trace; stdout/stderr; completion report; cleanup report; and optional short visual capture. This package is complete without implementing CARLA.
