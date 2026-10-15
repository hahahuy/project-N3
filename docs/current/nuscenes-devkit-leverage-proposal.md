# nuScenes-devkit Backend Makeover — Phase 1

Status: `APPROVED / COMPLETED PHASE 1`
Default pipeline impact: `ADDITIVE` — devkit-backed measurements are preferred when available, with explicit fallback provenance.
Verified against `nuscenes-devkit==1.2.0` against a local `v1.0-trainval` release.

## Scope

Audit of what `nuscenes-devkit` and the local nuScenes release can supply
directly for four open problems: map expansion, frame prediction, map view and
POV/3D. Every number below was measured against the local release, not quoted
from documentation.

## Inventory That Changes The Starting Point

The local release is a complete `v1.0-trainval` install, not only `v1.0-mini`.
It contains assets the current pipeline does not read at all:

| Asset | Local extent | Used by pipeline today |
| --- | --- | --- |
| Map expansion vector data | 4 maps, all layers | Yes, but 2 of 15 layers |
| CAN bus expansion | 7832 files across scenes | **No** |
| LIDAR_TOP point clouds | 34149 keyframes + 297737 sweeps | **No** |
| LiDAR segmentation labels | 34149 | **No** |
| Panoptic labels | 34149 | **No** |
| Prediction challenge scenes | 833 scenes | **No** |

The pinned devkit version is already `1.2.0` in `requirements.lock.txt`, so
none of this needs a dependency change.

## Approved Makeover Boundary

The owner approved using more of the local nuScenes release and official devkit
to improve backend calculations. Phase 1 keeps the canonical scenario schema,
OpenSCENARIO exporter, simulator contracts and CP1 immutable baseline stable.
Dataset-specific access is isolated in `real2scenario.nuscenes_backend`.

Implemented in Phase 1:

- Optional CAN `pose` ingestion through `NuScenesCanBus`, matched by timestamp
  without extrapolation.
- CAN speed is preferred for the ego trajectory when a match is available;
  finite-difference speed remains the explicit fallback for missing CAN data or
  unmatched timestamps.
- Scenario provenance records CAN adapter version, status, sample count and
  configured misalignment limit without recording host dataset paths.
- Native polygon widths use sampled perpendicular cross-sections and a median
  estimator when Shapely geometry is available; area-over-centerline remains a
  compatibility fallback.

Not changed by this phase:

- Actor speed remains annotation/keyframe-derived; CAN is an ego-source signal.
- No lane direction, actor reference convention, matcher tolerance or CP1
  baseline is changed.
- CAN acceleration/yaw-rate fields are not yet added to the canonical `State`;
  they remain available through the source adapter for the Tier 1 simulator
  integration phase.
- Point clouds, map rendering and prediction evaluation remain separate API
  slices because they require payload contracts and private-artifact handling.

## 1. Map Expansion — OSM Is Solving A Problem That Is Already Solved

### The vector map is a surveyed HD map

`singapore-onenorth` carries 15 layers:

| Layer | Records | Layer | Records |
| --- | --- | --- | --- |
| `node` | 37740 | `lane` | 936 |
| `polygon` | 4886 | `lane_connector` | 1066 |
| `line` | 3845 | `road_segment` | 783 |
| `walkway` | 838 | `road_block` | 645 |
| `lane_divider` | 357 | `road_divider` | 152 |
| `stop_line` | 451 | `traffic_light` | 127 |
| `ped_crossing` | 120 | `carpark_area` | 39 |
| `drivable_area` | 1 | | |

`boston-seaport`, `singapore-queenstown` and `singapore-hollandvillage` are also
present, which directly serves the deferred "Full Singapore One-North coverage"
work item.

### The pipeline reads only `lane` and `lane_connector`

`src/real2scenario/mapbuilder/__init__.py` builds records from exactly those two
layers. Ten other layers are available and unused:

- `stop_line` (451) maps directly onto a native OpenSCENARIO stop trigger.
- `traffic_light` (127) supports traffic-light state actors.
- `ped_crossing` (120) and `walkway` (838) bound pedestrian generation zones.
- `road_segment` (783) and `road_block` (645) provide real road hierarchy,
  replacing the current one-lane-per-OpenDRIVE-road flattening.
- `drivable_area` (1) is a whole-map validity envelope for map assertions.
- `lane_divider` (357) and `road_divider` (152) give lane edge geometry and
  direction evidence.

### Why OSM alignment cannot succeed

The map expansion JSON contains **no georeferencing whatsoever** — no `lat`,
`lon`, `latitude`, `longitude`, `utm`, `epsg`, `wgs`, `crs` or `origin` key
exists in any record. The coordinate system is a local metric frame with an
arbitrary origin.

Consequences:

- A rigid SE(2) fit from OSM to the nuScenes map cannot be computed without
  manually digitized control points, exactly as the OSM proposal already
  states.
- The only geographic anchor is the satellite `basemap` raster per map, which
  is an image, not a transform.
- OSM is a public, crowd-sourced map with no lane-level topology, no arcline
  geometry and no surveyed widths. It cannot replace a 936-lane surveyed HD map.

Recommendation: OSM should be dropped as a map-expansion path. The existing
proposal already names the nuScenes vector map as canonical, so this confirms
the documented direction rather than changing it. If OSM is retained at all it
is a QA/attribution overlay only, and the "Full Singapore One-North coverage"
item should be retargeted to the other three local maps, which need no
alignment step at all.

### Lane width is under-measured today

`_lane_width` in `src/real2scenario/mapbuilder/__init__.py` derives width as
`area / centerline_length`. Measured across all 936 lanes:

| Method | p10 | p50 | p90 | in [2.5, 4.0] m | over 6 m |
| --- | --- | --- | --- | --- | --- |
| Current `area / centerline` | 3.40 | 4.54 | 9.04 | 36% | 249 |
| Median perpendicular width | 2.75 | **3.25** | 4.75 | **82%** | **8** |

The current formula overestimates because lane polygons flare at merges and
splits while the centerline length stays near-linear, so extra area is divided
by unchanged length. Sampling the polygon perpendicular to the centerline every
2 m and taking the median is robust to those flares and lands on the expected
3.0-3.6 m Singapore lane width.

This directly addresses the `CP1 polygon lane width` item, currently
`CORRIDOR-DIAGNOSTIC` with "occupancy/dimension limitations remain". Wider
lanes distort lane occupancy and actor-to-lane assignment, so the fix also
improves road-match diagnostics downstream.

Note: `lane_type` is `CAR` for all 936 lanes on this map, so it provides no
filtering signal here. It should be re-checked on the other three maps before
being used as a filter.

## 2. Frame Prediction — CAN Bus Is Present And Unused

This is the highest-value gap found.

### What is available

The CAN bus expansion covers 7832 files. The devkit exposes it through
`NuScenesCanBus.get_messages(scene_name, message_name)` in
`python-sdk/nuscenes/can_bus/can_bus_api.py`.

| Message | Rate (scene-0061) | Fields |
| --- | --- | --- |
| `pose` | 49.9 Hz | `pos`, `orientation`, `vel`, `accel`, `rotation_rate`, `utime` |
| `steeranglefeedback` | ~100 Hz | `value`, `utime` |
| `ms_imu` | ~100 Hz | `q`, `linear_accel`, `rotation_rate`, `utime` |
| `vehicle_monitor` | 2 Hz | `vehicle_speed`, `yaw_rate`, `steering`, `throttle`, `brake`, `gear_position`, `brake_switch`, `left_signal`, `right_signal`, `battery_level` |
| `route` | per scene | baseline navigation route, 964 points for scene-0061 |

### The frames are already compatible

CAN `pose` and `ego_pose` are in the same global map frame. Measured nearest-
timestamp gap for scene-0061: **0.556 m** XY. No transform is required, so CAN
data drops into the existing `SourceWindow` path unchanged.

### The current speed estimate is measurably wrong

Speeds are currently derived by finite difference over 2 Hz keyframes in
`src/real2scenario/ingestion.py`. Against CAN ground truth at matched
timestamps:

```text
project finite-diff speed (2 Hz): [3.14, 2.98, 2.79, 2.63, 2.51, 2.35, 2.25]
CAN ground-truth speed (50 Hz)  : [1.97, 1.97, 1.97, 1.97, 1.97, 1.97, 1.97]
max absolute error: 1.17 m/s
```

The finite-difference series drifts across a 0.5 s window while the true speed
is steady, which is the expected signature of differencing a decelerating
vehicle at too low a rate. This propagates into actor state speed, variant
generation and the ADE/FDE comparison.

### What this unlocks

1. Ego speed, longitudinal acceleration and yaw rate at 50 Hz instead of 2 Hz.
2. Steering angle, throttle, brake and gear — ground-truth driver inputs that
   the current pipeline has no access to at all.
3. A physically meaningful basis for the `kinematic-open-loop-v1` preview and
   for speed/distance/timing variants, which currently perturb a
   finite-difference quantity.
4. `route` gives the baseline navigation path, a useful independent signal for
   corridor selection and for prediction scoring.

### Caveats that must be recorded

- 24 scenes have no CAN data at all (`can_blacklist` in the devkit).
- About 93 scenes have a `route` that is misaligned with ego poses
  (`route_blacklist`). `pose` and the vehicle messages are unaffected.
- CAN is local/private under the nuScenes terms, same as all derived artifacts.
- The devkit exposes `route` through a hard-coded blacklist keyed to
  `max_misalignment == 5.0`; a different threshold triggers a full rescan.

## 3. Map View, POV And 3D — Data Available, Rendering Still Required

### Current state

`frontend/package.json` declares no 3D dependency. The whole UI is one
330-line `App.tsx` using inline SVG. The map drawing in `App.tsx` is a
placeholder path (`M0 50 H100`), not nuScenes map data.

The current UI previously disabled two views with the reason "no point-cloud access":

- 3rd-person POV, tracked as U5
- LiDAR 3D, tracked as U6

That reason is not accurate for this release and has been superseded by the
updated UI scope. LIDAR_TOP holds 34149 keyframe
clouds and 297737 sweeps, with 34149 LiDAR segmentation labels and 34149
panoptic labels alongside them. The data is on disk; the pipeline does not read
  it. U5/U6 are implementation gaps, not data-availability gaps.

### What the devkit supplies

- `NuScenesMap.render_map_patch`, `render_layers`, `render_map_mask` and
  `get_map_mask` render real lane and drivable-area geometry to a top-down
  raster, which is enough to replace the placeholder SVG map immediately.
- `NuScenesMap.get_next_roads(x, y)` returns lookahead `road_segment`,
  `road_block` and `lane` records. This is the road-ahead primitive the scene
  browser needs.
- `NuScenesMap.get_records_in_patch`, `get_records_in_radius` and
  `layers_on_point` support viewport and radius queries without loading the
  whole map per frame.
- `nuscenes.utils.geometry_utils.view_points` projects 3D points and boxes into
  an arbitrary camera. Combined with `calibrated_sensor` records it yields a
  correct third-person or sensor POV.
- `PointCloud`, `LidarPoints` and `RadarPointCloud` in
  `nuscenes.utils.data_classes` load and decimate recorded clouds.
- `export_pointclouds_as_obj` in the devkit scripts is a working OBJ exporter.

### What the devkit does not supply

There is no 3D renderer in the SDK — no Open3D, no WebGL, no mesh, no offscreen
rasterizer. The devkit solves data and transforms, not presentation. A real 3D
view therefore needs a frontend WebGL stack plus a backend endpoint that serves
decimated point clouds or box geometry; the devkit provides the correct numbers
for that endpoint but cannot provide the viewport.

The same boundary applies to the rest of the platform: the SDK contains no
OpenDRIVE writer, no OpenSCENARIO writer, no simulation engine and no
georeferencing. The project's existing hand-rolled map builder and exporter are
not redundant with anything in the SDK and should stay.

## 4. Prediction Benchmark

`maps/prediction/prediction_scenes.json` contains 833 scenes with multi-modal
annotated agent futures. The SDK ships `nuscenes/prediction` with CoverNet,
physics baselines and a rasterizer input representation, and
`nuscenes/eval/prediction` with minADE, minFDE and miss rate.

The project currently scores only against its own simulator replay. This is a
third-party ground truth for future-trajectory quality, and it is the natural
evaluation target for the frame-prediction work above.

## Recommendations

| # | Action | Unblocks | Confidence |
| --- | --- | --- | --- |
| 1 | Read ego speed/accel/yaw-rate from CAN `pose` at 50 Hz; keep finite difference as fallback for blacklisted scenes | Frame prediction, variant generation, ADE/FDE accuracy | Implemented in Phase 1 for ego speed; acceleration/yaw-rate adapter fields retained for Tier 1 integration |
| 2 | Replace `area / centerline` lane width with median perpendicular width sampling | CP1 polygon lane width, lane occupancy, road-match diagnostics | High, measured |
| 3 | Enable the U6 LiDAR POV using private decimated LIDAR_TOP payloads with devkit calibration provenance | LiDAR 3D view scoping | High, contract implemented; serving/UI open |
| 4 | Serve `render_map_patch` geometry to the frontend to replace the placeholder SVG map | Map view | High |
| 5 | Retarget "Full Singapore One-North coverage" to the other three local maps instead of OSM | Deferred map-source expansion | High |
| 6 | Adopt `stop_line`, `ped_crossing`, `traffic_light` and `road_segment` layers | OSC stop triggers, pedestrian zones, road hierarchy | Medium, needs schema review |
| 7 | Add `get_next_roads` as the road-ahead signal for scene browsing and lane matching | Map view, actor selection | Medium |
| 8 | Add `nuscenes/eval/prediction` as an external benchmark alongside replay ADE/FDE | CP3 benchmark protocol | Medium, needs owner approval |
| 9 | Record CAN coverage, route blacklist and local/private artifact status in the technical contracts | Evidence and license discipline | High |

## Guardrails

- Nothing here authorizes publishing CAN, point cloud or map derived artifacts.
- CAN is sensor data and inherits the nuScenes license terms.
- Recording `route` as a reference path must not be allowed to silently
  constrain or overwrite recorded ego trajectories.
- Speed derived from CAN is a measured input, not a ground-truth claim about
  actor intent.
- Map expansion changes must not alter the CP1 baseline or the immutable
  corridor evidence already recorded.
- Any change to lane width is a CP1 semantic change and needs the normal review
  and evidence path.

## Remaining Owner Decisions

1. Whether CAN-derived acceleration and yaw rate should be promoted into a
   future canonical source-state extension, rather than remaining adapter data.
2. Does the 20-variant grid remain meaningful with CAN-derived state, or does
   it need a re-declared physics budget?
3. Should the prediction benchmark become CP3 acceptance evidence, or stay
   advisory?
4. Is OSM retired from the active queue, or retained as a QA overlay only?
