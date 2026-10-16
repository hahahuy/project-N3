# nuScenes Data Exploration And Future Integration

Status: `ANALYSIS / 2026-10-16`

## Scope

This report inventories the nuScenes data that is relevant to Real2Scenario,
the current implementation boundary, and future integration opportunities. It
does not authorize new data ingestion or change the canonical scenario contract.
Raw nuScenes data and derived artifacts remain local/private.

## Current Data Path

The current metadata index and ingestion path use:

```text
scene -> sample timeline -> sample_data/LIDAR_TOP -> ego_pose
                                |
                                -> sample_annotation -> instance -> category
```

The canonical result preserves:

- actor identity, category and dimensions;
- time, position, yaw and speed;
- source timestamp and source record token per state;
- ego pose-derived trajectory;
- selected scene/window and coordinate-transform provenance;
- optional CAN-derived ego speed, with finite-difference fallback.

The web evidence path additionally supports recorded `LIDAR_TOP`, calibration,
ego-pose transforms, multisweep history, native map patches and optional CAN
alignment. The WASM surface consumes only the exported XOSC/XODR pair and must
remain simulator preview, not recorded sensor evidence.

## Data Inventory

| Data | Current use | Future value | Priority |
|---|---|---|---|
| `scene`, `sample` | Scene discovery and ordered keyframes | Dataset browsing, reproducible windows, timeline bounds | High |
| `sample_annotation` | Actor position, heading, dimensions | Lifecycle, visibility, annotation quality, sensor support | High |
| `instance` | Stable actor identity and category link | First/last annotation, track completeness and identity audits | High |
| `ego_pose` | Ego trajectory and coordinate anchor | Ego replay validation, source-to-sensor alignment | High |
| `sample_data` | `LIDAR_TOP` anchors and sensor evidence | Unified sensor timeline, camera/radar synchronization | High |
| `calibrated_sensor` | LiDAR transform and sensor provenance | Camera projection, frustum overlays, all sensor transforms | High |
| `sensor` | Channel selection | Camera/radar modality discovery and capability reporting | High |
| `category` | Actor type | Vehicle/pedestrian/cyclist policy and simulator mapping | High |
| `attribute` | Not currently preserved | Moving/parked/stopped and rider-state context | Medium |
| `visibility` | Not currently preserved | Occlusion and observation-confidence labels | Medium |
| `num_lidar_pts`, `num_radar_pts` | Not currently preserved | Track quality and evidence strength | Medium |
| Camera `sample_data` and image files | Adapter exposes future explorer only | Recorded camera evidence and 3D box projection | High |
| Radar `sample_data` and point files | Rendering flag exists, active path is LiDAR | Velocity-oriented recorded evidence | Medium |
| Map expansion layers | Native map patch and road matching | Traffic context, stop lines, crossings, lane semantics | High |
| `log` | Partial location lookup in map adapter | Location, recording context and reproducibility metadata | Medium |
| CAN bus | Optional pose, speed, acceleration, yaw rate and brake | Steering, wheel speed, control/event alignment | Medium |
| Panoptic/segmentation data | Not part of core ingestion | Semantic QA and perception-oriented review | Low/medium |

## Highest-Value Additions

### Actor lifecycle and quality

The current `Actor.trajectory` implicitly records the first and last observed
annotation, but the contract does not expose lifecycle explicitly. Additive
metadata should distinguish:

- observed start and end time;
- annotation count and missing keyframes;
- whether the track is clipped by the selected window;
- visibility summary;
- LiDAR/radar support summary;
- sparse or fragmented track status.

This is directly useful to the WASM player: an actor can be shown as absent
before its observed start and after its observed end rather than being treated
as present for the whole scenario.

### Recorded camera evidence

Camera evidence is the strongest future integration for reviewer confidence. A
versioned contract should carry channel, timestamp, sample-data token, image
artifact reference, calibration, ego pose, projected annotation boxes and
synchronization status. The UI should show recorded camera imagery beside the
WASM actor preview, never label the preview as recorded imagery, and never use
camera pixels as native replay metrics without an explicit evaluation contract.

### Attributes and visibility

`attribute` and `visibility` data can improve actor selection and explain why a
track was included or excluded. They should remain timestamped or sample-scoped;
an actor can change from moving to stopped and its visibility can change over
time.

### Map and traffic context

The map expansion can expose lanes, drivable area, crossings, stop lines and
traffic lights. These layers can improve interaction classification and map
review, but they do not by themselves prove that a recorded traffic-light
state or behavior was reproduced in esmini/WASM.

## Boundaries

- nuScenes records are recorded evidence and source truth.
- Native esmini remains the sanctioned source for ADE/FDE, gates and reports.
- WASM output is interactive preview only.
- Recorded LiDAR, camera and radar must not be described as engine-generated.
- Sensor timestamps must not be merged into one implicit timeline without an
  explicit synchronization policy.
- Dataset-specific fields belong at the adapter/evidence boundary unless the
  canonical contract is deliberately extended.

## Recommended Sequence

1. Add lifecycle and track-quality metadata to the source/evidence contract.
2. Add recorded camera evidence and projection validation.
3. Make actor-class selection explicit for vehicles, pedestrians and bicycles.
4. Preserve attributes and visibility histories.
5. Extend radar and CAN only where a concrete review or metric needs them.
6. Add traffic-context behavior only with a versioned behavior contract.
7. Treat panoptic data as semantic QA, not as trajectory identity.
