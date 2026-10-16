# UI Motion Editor Design

Status: `APPROVED MVP DIRECTION / PARTIALLY IMPLEMENTED`
The U0 parameterized preview subset is implemented. Full authoring, timeline,
POV and sensor surfaces remain later MVP work and must use real backend contracts.

## Purpose

The UI should let a technical user inspect recorded scenarios and create a new
motion variant for a selected actor without modifying the canonical recorded
scenario. Every edit creates a child artifact with parent/config/seed/hash
provenance and must pass the declared validation gates.

## Layer Model

The review workspace should keep these layers independently visible:

- OSM reference/alignment layer.
- nuScenes vector-map layer.
- generated OpenDRIVE layer.
- recorded/raw trajectory layer.
- generated variant layer.
- esmini replay layer.
- CARLA replay layer.
- sensor evidence layer: camera, LiDAR or radar.
- road-match and validation diagnostics.

OSM is an auxiliary reference layer. It is not the canonical CP1 map source.
Sensor projection is visual QA evidence, not a replacement for annotation
trajectory ground truth.

## POV Model

The UI should distinguish three camera sources:

### Analyst POV

- 2D pan/zoom.
- 3D orbit when a 3D world is available.
- fit scene.
- follow ego.
- follow selected actor.
- look-at target.

### Simulator POV

- esmini viewer or recorded overlay.
- CARLA spectator/chase/ego camera when runtime evidence exists.

### Sensor POV

- `CAM_FRONT`, other camera channels, `LIDAR_TOP` and radar channels.
- timestamp-synchronized raw sensor view.
- optional map projection/frustum overlay.

Simulator POV must not be presented as a recorded sensor POV. A CARLA camera
without matching calibration is synthetic visualization only.

## Object Motion Editor

The editor should support three modes:

### Parameterized edit — first implementation target

- speed multiplier;
- heading offset;
- initial gap delta;
- timing offset.

The editable universe includes vehicles, pedestrians, cyclists, all trajectory-
bearing actors and movable static objects such as cones/barriers. MVP also
supports instantaneous velocity and segment propagation edits. These are
trajectory/kinematic edits, not behavior replay.

The approved MVP direction is an internal fixed-timestep kinematic simulator.
The currently implemented U0 preview is the earlier deterministic trajectory
transformation and validation slice; it supports edited position, heading,
velocity and timing states but is not yet the complete frame-producing preview
engine. Neither path claims physics, autonomy or behavior fidelity. CARLA
POV/execution is post-MVP.

MVP direction/propagation controls include:

- heading offset;
- direction vector;
- instantaneous velocity at a selected timestamp;
- segment velocity/trajectory propagation;
- explicit propagation mode;
- recorded LiDAR point-cloud evidence with source provenance.

### Waypoint edit — later

- drag a waypoint/control point;
- edit heading and speed;
- explicit `snap to lane` action;
- smooth transition option;
- kinematic and road-match feedback.

### Behavior edit — post-MVP and separate

When behavior execution is unavailable, the UI must show `unsupported` and must
not silently fall back to waypoint replay.

## Artifact Semantics

An edit creates a child variant. It never mutates the parent or raw recorded
trajectory.

```json
{
  "artifact_type": "variant",
  "parent_scenario_id": "...",
  "variant_config": {
    "edit_mode": "parameterized",
    "actor_edits": [
      {
        "actor_id": "...",
        "speed_multiplier": 1.2,
        "heading_offset_rad": 0.15,
        "timing_offset_s": 0.25
      }
    ],
    "seed": 7
  },
  "provenance": {
    "parent_hash": "...",
    "config_hash": "...",
    "generator_version": "...",
    "replay_mode": "waypoint"
  }
}
```

## Validation Flow

```text
edit schema
  -> timestamps
  -> G4 physics
  -> G3 road-match
  -> G5 collision
  -> simulator support
  -> temporary G6/G7 diagnostics
  -> optional replay
```

The UI must show all gate states and reasons. A single `valid=false` boolean is
not sufficient for review.

## Sensor/Map Synchronization

Timeline synchronization must use timestamps, not sample indexes. A displayed
time should identify:

- source timestamp and sample token;
- sensor frame timestamp;
- simulator tick/time;
- interpolation/coverage status.

If no sensor frame is within the configured tolerance, show
`sensor_frame_unavailable` rather than silently selecting a distant frame.

### Current Implementation Boundary

The implemented U0 preview returns edited, time-indexed trajectory states and
draws recorded/generated trajectory paths. It does not generate new camera,
LiDAR or radar frames after an object edit, and the current timeline does not
yet select a rendered frame at the chosen timestamp. Sensor reprojection,
simulator-rendered frames and frame artifact persistence require a later
implementation with explicit timestamp, calibration and provenance contracts.

## Non-Goals for the First Showcase

- no live sensor regeneration;
- no full 3D streaming requirement;
- no behavior replay claim;
- no OSM replacement of the nuScenes canonical map;
- no CARLA same-XOSC claim without runtime evidence;
- no direct editing of raw recorded data.
