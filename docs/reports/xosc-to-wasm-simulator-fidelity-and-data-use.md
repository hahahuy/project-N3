# XOSC To WASM Simulator Fidelity And Useful Data

Status: `ANALYSIS / 2026-10-16`

## Executive Summary

The XOSC-to-WASM path is a lightweight interactive simulator preview. It is
useful when it receives enough data to make actor motion, timing, identity,
geometry and road context visually credible. It is not useful to load every
nuScenes field into WASM if the field does not affect the OpenSCENARIO engine or
the renderer.

The current path is:

```text
canonical Scenario
  -> XOSC + local-template XODR
  -> esminiJS in a Worker
  -> fixed-step WasmFrame
  -> Three.js actor/road preview
```

WASM output remains preview-only. It must not feed ADE/FDE, gates, reports or
`replay.csv`.

## Data Already Used By XOSC/WASM

### Scenario/entity data

The current XOSC uses:

- actor IDs and names;
- actor categories mapped to vehicle entities;
- actor dimensions;
- initial position and heading;
- trajectory vertex time;
- trajectory position and heading;
- actor-specific start time;
- scenario duration;
- initial target speed policy;
- local OpenDRIVE filename.

The Worker additionally uses:

- OpenSCENARIO XML;
- OpenDRIVE XML;
- fixed timestep `0.01`;
- object state IDs, names, position, heading and dimensions;
- road lane-boundary geometry;
- reset/play/step/pause lifecycle.

### Renderer data

The Three.js surface currently renders:

- lane-boundary lines;
- a grid and lighting;
- cuboid actor meshes;
- actor position and dimensions;
- actor heading;
- selected-object color;
- orbit camera and focus animation.

## Data That Would Improve Simulation Feel

### 1. Accurate lifecycle data

The most important addition is not more geometry. It is explicit actor lifecycle:

```text
observed_start_s
observed_end_s
active_at_time
track_quality
```

Without this, an actor can remain visually present after its recorded track ends
or appear before it was observed. Dynamic actor visibility should be driven by
source lifecycle and simulator state, not by a generic “all entities exist for
the full scenario” assumption.

### 2. Actor geometry and category

Dimensions are already used and should be retained. Better simulator feel would
also benefit from:

- category-specific mesh or color;
- pedestrian and cyclist entity support;
- static-object distinction;
- optional model/mesh metadata where licensed and available;
- per-actor bounding-box center convention.

These improve visual interpretation but do not improve native replay metrics.

### 3. More complete road context

The current XODR is a selected template approximation. Deeper visual feel would
benefit from:

- accurate lane centerlines and boundaries;
- lane markings and road signs;
- stop lines and pedestrian crossings;
- traffic-light locations and states;
- road furniture and static obstacles;
- map patch provenance and alignment confidence.

This is where a richer map-to-XODR path or a different renderer becomes more
important than adding fields to XOSC alone.

### 4. Actor interaction context

Useful derived data includes:

- lane ID and lane relation;
- gap to lead/follow actors;
- relative longitudinal and lateral distance;
- time-to-collision estimates;
- cut-in, merge, crossing and following labels;
- stop or yield context.

These are useful for camera defaults, selection, timeline annotations and
scenario review. They should not be represented as if they were directly
measured simulator outputs unless their provenance is explicit.

### 5. Recorded sensor overlays

Recorded camera, LiDAR and radar can make the preview much more useful when
shown beside or overlaid with WASM actors. They are not inputs to the WASM
engine itself and must be labeled as recorded evidence.

Good interactions include:

- scrub a shared timestamp;
- select a WASM actor and highlight its recorded annotation;
- show the corresponding camera frame;
- show recorded LiDAR/radar evidence at the same source time;
- indicate timing offset, historical sweep smearing and unavailable data.

This is evidence fusion, not sensor simulation.

### 6. Ego vehicle camera and sensor calibration

Calibration and ego pose are useful for recorded sensor projection and camera
frustums. They do not currently belong in the raw WASM actor frame unless the
engine is explicitly extended to model sensors. The current boundary should be:

```text
WASM actor frame: simulator state
recorded sensor frame: nuScenes evidence
calibration: bridge for projection and alignment
```

### 7. CAN and motion telemetry

CAN speed, acceleration, yaw rate and brake pressure can add timeline context:

- compare recorded ego speed with WASM/native replay speed;
- show braking onset;
- explain why a trajectory changes speed;
- identify stationary/accelerating phases.

This is useful for review, but it should not silently control the WASM vehicle
unless a deliberate closed-loop or telemetry-replay feature is approved.

## Data That Does Not Improve Current WASM Directly

These data are valuable elsewhere but do not need to be copied into XOSC/WASM
for the current preview:

- raw camera pixels;
- raw LiDAR point clouds;
- raw radar points;
- panoptic masks;
- CAN brake messages;
- source record tokens beyond provenance and correlation;
- annotation visibility counts;
- dataset log metadata.

They should remain in separate recorded-evidence contracts and be joined by
timestamp, actor identity and source provenance.

## Fidelity Levels

| Level | What is represented | Current status |
|---|---|---|
| L0 frame preview | XOSC entity boxes, road lines, camera orbit | Implemented |
| L1 trajectory replay | Time-indexed actor position and heading | Implemented, validate lifecycle and timing |
| L2 scene context | Better XODR, lanes, markings, traffic context | Partial/approximate |
| L3 evidence fusion | Recorded camera/LiDAR/radar alongside replay | LiDAR partial, camera/radar future |
| L4 sensor simulation | Engine-generated sensor outputs | Not implemented and not claimed |
| L5 closed-loop behavior | Policy/physics/controller response | Not implemented in current WASM path |

## Metrics For WASM Fidelity

The browser preview should use diagnostic metrics only, separate from Tier 0
reports:

```text
frame_time_error_s
actor identity continuity
actor active-window correctness
position delta between consecutive frames
heading delta between consecutive frames
WASM-vs-source position error at sampled timestamps
WASM-vs-native replay error at sampled timestamps
camera/LiDAR timestamp alignment error
road/lane occupancy validity
```

For the Worker specifically, acceptance should verify:

- one `step` produces exactly one `0.01 s` integration;
- reset returns a non-advanced initial frame;
- object states change when the source trajectory changes;
- late-start actors do not appear as moving before their start time;
- actors stop or disappear according to an explicit lifecycle policy;
- Play and Step produce the same sequence when sampled at the same steps;
- Pause stops frame production;
- native remains authoritative when WASM and native disagree.

## Recommended Implementation Sequence

1. Validate actor motion at `t=0`, `0.5`, `1`, `5` and end time for every selected
   actor.
2. Add explicit lifecycle state to the frame/render contract.
3. Add per-actor category and quality badges.
4. Improve local XODR/map context before adding decorative assets.
5. Add recorded camera evidence and timestamp correlation.
6. Add radar and richer CAN only for a defined review need.
7. Consider CARLA or another sensor-capable backend if actual synthetic sensor
   generation or closed-loop behavior is required.

## Final Boundary

More nuScenes data can make the interactive preview feel more grounded, but the
player should not become a hidden sensor simulator or a second metric engine.
The useful architecture is:

```text
XOSC/WASM: interactive actor and road preview
nuScenes: recorded sensor/evidence source
native esmini: authoritative replay and metrics
CARLA/future backend: sensor/physics/closed-loop experiments
```
