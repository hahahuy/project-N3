# nuScenes And Simulation Guide

## 1. Purpose

This guide gives every team member a shared mental model before implementing ingestion or simulation. It answers four questions:

1. What is nuScenes and which files matter for this project?
2. How can we inspect images, LiDAR, maps, boxes, tracks, and panoptic labels?
3. What does it mean to replicate a nuScenes interaction in esmini or CARLA?
4. Which aspects can be reproduced faithfully, and which must be declared approximations?

Read this document before R2S-100 and R2S-101.

## 2. What nuScenes Is

nuScenes is a recorded autonomous-driving dataset. A recording session is divided into scenes, and each scene contains time-linked sensor measurements, ego poses, object annotations, and map/log metadata. The mini version is a small development subset; the full release contains more scenes.

For this project, nuScenes is the source of a real interaction. It is not itself a simulator. The project extracts the observed motion and scene context, represents them in a canonical format, then recreates an equivalent test in a simulator.

The dataset is organized around these relationships:

```text
scene
  -> ordered samples (keyframes)
     -> sample_data for each camera/LiDAR/radar sensor
     -> sample_annotation for tracked 3D object boxes
     -> ego_pose for the ego vehicle pose
     -> calibrated_sensor for sensor-to-ego calibration
  -> log and map context
```

In normal nuScenes use, a `sample` is a keyframe. `sample_data` connects that keyframe to one sensor datum and may also form a higher-frequency linked sequence. `sample_annotation` supplies the labeled 3D boxes for instances at the relevant keyframe. An `instance` groups one physical object across annotations over time.

## 3. Files And What They Mean

| Record/file | What it contains | Why Real2Scenario needs it |
| --- | --- | --- |
| `scene.json` | Scene names and first/last samples | Select a recorded drive segment. |
| `sample.json` | Keyframe timeline and channel references | Move through an interaction window. |
| `sample_data.json` | Sensor file references and linked sensor frames | Locate camera/LiDAR/radar observations. |
| `sample_annotation.json` | Labeled object 3D boxes, category, instance links | Reconstruct actor tracks and dimensions. |
| `instance.json` | Object identity across time | Keep one actor ID across keyframes. |
| `ego_pose.json` | Ego vehicle pose in global coordinates | Reconstruct ego trajectory. |
| `calibrated_sensor.json` | Sensor pose relative to ego | Project boxes into camera/LiDAR and understand sensor frame. |
| `sensor.json` | Sensor identity/type/channel | Choose the required camera/LiDAR channel. |
| `category.json` | Object taxonomy | Map source labels to simulation actor types. |
| `attribute.json` | Attributes such as moving/parked | Optional behavior context. |
| map expansion data | Lane, road, and drivable-area information | Road-aligned extraction and map validity checks. |
| camera images / LiDAR files | Raw observed sensor data | Visual inspection and perception-oriented extension. |
| panoptic masks / `panoptic.json` | Per-pixel or per-point semantic/instance segmentation labels | Verify scene semantics; not enough for trajectories alone. |

The currently committed `data/nuScenes-panoptic-v1.0-mini` subset includes panoptic-related content and category metadata. It does **not** include the core scene/sample/annotation/ego-pose tables or the raw sensor files listed above. Therefore it cannot currently provide actor trajectories, ego trajectories, camera rendering, or complete scene browsing on its own.

## 4. Coordinate Frames

Coordinate mistakes are a major source of invalid replay. Keep the frame name with every trajectory.

| Frame | Meaning | Typical use |
| --- | --- | --- |
| Global/map | Fixed world frame used by recorded poses | Compare ego and actor locations across a scene. |
| Ego vehicle | Frame attached to the recording vehicle | Express an actor relative to ego. |
| Sensor | Frame attached to a camera/LiDAR/radar | Project 3D annotations to a sensor view. |
| Local road-aligned | Project-specific frame centered/oriented at a selected source window | Export stable local trajectories to a template map. |
| Simulator | Frame used by esmini/OpenDRIVE or CARLA | Execute the reconstructed scenario. |

The general transform chain is:

```text
annotation box in global frame
  -> inverse ego_pose
  -> ego frame
  -> inverse calibrated_sensor
  -> sensor frame
```

For replay, the pipeline first selects a local origin and heading, then converts global recorded positions into the local road-aligned frame. This transform is an intentional project artifact with a documented version, not an implicit coordinate swap.

## 5. How To Inspect nuScenes

### 5.1 Official Python Devkit

The official `nuscenes-devkit` is the first tool the team should use. It provides table access, a `NuScenes` object, visualization helpers, and map utilities. Use a Jupyter notebook for onboarding so the team can see each representation while reading the corresponding records.

After obtaining a licensed nuScenes mini dataset and installing the devkit in the project environment:

```bash
pip install nuscenes-devkit matplotlib
export NUSCENES_ROOT="$HOME/datasets/nuscenes"
export NUSCENES_VERSION="v1.0-mini"
```

Minimal notebook example:

```python
import os

from nuscenes.nuscenes import NuScenes

nusc = NuScenes(
    version=os.environ["NUSCENES_VERSION"],
    dataroot=os.environ["NUSCENES_ROOT"],
    verbose=True,
)

nusc.list_scenes()
scene = nusc.scene[0]
first_sample_token = scene["first_sample_token"]
nusc.render_sample(first_sample_token)
```

`render_sample` is the most useful first view: it overlays annotations on available sensor views. It requires the matching raw sensor files, not just JSON metadata.

Useful exploration calls include:

```python
sample = nusc.get("sample", first_sample_token)
nusc.render_sample_data(sample["data"]["CAM_FRONT"])
nusc.render_ego_centric_map(first_sample_token)
```

Depending on the installed devkit release and available data, also use its annotation/point-cloud rendering helpers to inspect individual labeled boxes and LiDAR. Treat helper APIs as exploration tools; production ingestion must read and validate the underlying metadata explicitly.

### 5.2 What Can Be Viewed With Each Download

| Local material | What the team can inspect | What remains unavailable |
| --- | --- | --- |
| Metadata JSON only | Scene graph, timestamps, object metadata, poses | Image pixels, point clouds, panoptic mask renderings. |
| Metadata + camera images | Camera frames with 3D box overlays | LiDAR points and LiDAR panoptic visualization. |
| Metadata + LiDAR | Point clouds, 3D boxes, selected map overlays | Camera image appearance if images are absent. |
| Metadata + panoptic masks | Semantic/instance labels aligned with their original sensor data | Actor tracks unless annotations/instances are also present. |
| Complete mini release | All supported devkit rendering and extraction paths | Exact original world reconstruction in another simulator. |

The immediate M1 task is not to download every modality. It is to acquire the metadata needed for ego/object tracks and at least one modality for visual review. Camera images are the easiest option for a human-facing onboarding demo; LiDAR is helpful for validating 3D geometry.

### 5.3 Data Inventory Checklist

Before coding an extractor, fill this table for the selected dataset location:

| Item | Present? | Path/version | Reviewer notes |
| --- | --- | --- | --- |
| Core metadata tables |  |  |  |
| Map expansion data |  |  |  |
| Front-camera frames |  |  |  |
| Top/primary LiDAR frames |  |  |  |
| Sample annotations and instances |  |  |  |
| Ego poses and calibration |  |  |  |
| Panoptic labels |  |  |  |
| NuScenes devkit version |  |  |  |
| License/attribution reviewed |  |  |  |

## 6. From nuScenes To A Canonical Scenario

The extractor must create a simulator-independent description. It should not emit XML while it is reading nuScenes tables.

```text
1. Select scene and time window.
2. Read ego_pose records to form the ego trajectory.
3. Follow annotation/instance records to form candidate actor tracks.
4. Estimate speed/heading only with a documented interpolation/differentiation rule.
5. Select 1-3 relevant actors using distance, TTC, lane relation, or manual review.
6. Convert source global coordinates to a named local road-aligned frame.
7. Save canonical Scenario JSON with source tokens and transformation metadata.
```

The output needs at minimum, for each state: time, position, yaw, speed, actor ID, actor type, and dimensions when known. Preserve original source tokens so a reviewer can navigate from any generated scenario back to the nuScenes sample/annotation records.

## 7. What “Replicate” Means

There are three distinct fidelity levels. The project must state which one it achieved.

| Level | What is replicated | MVP status |
| --- | --- | --- |
| Trajectory replay | Ego/actor motion, timing, relative interaction, and basic road context | Required. |
| Scene reconstruction | Road geometry, lanes, actor shapes, traffic furniture, buildings, lighting | Approximate only in MVP. |
| Sensor replication | Camera/LiDAR/radar observations comparable to recorded data | Post-MVP, requires CARLA/assets/calibration work. |

A successful OpenSCENARIO replay means the trajectory interaction was recreated under documented assumptions. It does not mean the simulator world is visually identical to the original nuScenes scene, nor that camera pixels or LiDAR returns match the recorded sensor data.

## 8. Replicating With esmini

esmini is used to validate trajectory-level OpenSCENARIO replay.

```text
nuScenes tracks
  -> local road-aligned coordinates
  -> choose supported OpenDRIVE template
  -> create entities, initial state, trajectories, triggers in .xosc
  -> esmini replay
  -> normalized replay trace
  -> compare with source trajectory
```

### What esmini can prove for this project

- The generated OpenSCENARIO file is structurally runnable by the selected backend.
- Entities spawn with expected names and initial states.
- Fixed/reference trajectories and timing replay as configured.
- A batch can be executed headlessly to calculate completion rate, position error, TTC, and distance.
- Generated variants can be filtered by executable scenario behavior.

### What esmini cannot faithfully recreate in this MVP

- Original nuScenes camera imagery, LiDAR returns, weather, buildings, and surrounding city assets.
- Exact road topology if the recorded segment does not match a supported `.xodr` template.
- Closed-loop reactions of a driving policy unless an external controller is added.

Use esmini first when the review goal is “does the `.xosc` replay the recorded interaction with acceptable kinematic error?”

## 9. Replicating With CARLA

CARLA becomes useful when the goal expands beyond trajectory replay.

```text
nuScenes tracks and map context
  -> local coordinate transform
  -> compatible CARLA town or custom imported map
  -> choose vehicle/pedestrian blueprints
  -> spawn actors and apply trajectory/controller behavior
  -> optionally attach camera/LiDAR/radar sensors
  -> run synchronous replay and record trace/sensor data
  -> compare trajectory and, later, perception outputs
```

### What CARLA adds

- A 3D world with vehicles, pedestrians, roads, weather, and lighting.
- Synthetic camera, LiDAR, radar, IMU, GNSS, and collision sensor outputs.
- A place to test perception/planning/control systems in closed loop.
- A presentation-friendly visualization after the core scenario pipeline is proven.

### CARLA replication decisions that must be explicit

| Decision | Required project policy |
| --- | --- |
| Map | Use a named built-in town only if its topology is adequate, otherwise import/build a custom map; never imply it is the original nuScenes location. |
| Actor appearance | Map nuScenes category/dimensions to documented CARLA blueprint choices. |
| Motion | State whether actors are teleported along a reference trajectory, driven by a controller, or controlled by a behavior model. |
| Ego role | State whether ego is replayed open loop or controlled by the AV stack under test. |
| Synchronization | Use a fixed synchronous tick and record the tick rate in the report. |
| Sensor comparison | Record sensor intrinsics/extrinsics/configuration; do not claim pixel-level equivalence without calibration and scene-asset validation. |

For open-loop trajectory fidelity, setting transforms directly can match positions more closely but bypasses physical dynamics. For a closed-loop test, use a controller and accept that trajectory error may increase. These are different experiment modes and must never be mixed in one metric report.

## 10. esmini Versus CARLA In This Project

| Question | esmini | CARLA |
| --- | --- | --- |
| Can it execute a generated OpenSCENARIO trajectory scenario? | Yes, this is the MVP validation path. | Possible through an adapter/workflow, but it is not the MVP contract. |
| Can it batch-run quickly in headless CI? | Yes, preferred. | Possible but substantially heavier. |
| Can it show a visually rich 3D city? | Limited. | Yes. |
| Can it synthesize camera/LiDAR/radar for AV-stack tests? | Not the intended MVP path. | Yes. |
| Does it remove the need for map/coordinate assumptions? | No. | No; custom map alignment is still required. |
| When should the team use it? | M2-M3: export, regression, replay metrics, batch variants. | After M3: 3D demo, sensors, or closed-loop evaluation. |

The recommended architecture is additive: esmini remains the quick, deterministic OpenSCENARIO gate; CARLA becomes a second backend for higher-fidelity experiments. Both consume the same canonical scenario and emit the same report shape where metrics are comparable.

## 11. Team Onboarding Exercise

Complete this exercise before the first ingestion pull request:

1. Install the devkit against a licensed complete mini dataset.
2. List scenes and choose one source scene.
3. Render one keyframe with `render_sample`.
4. Identify the ego pose, front-camera sample data, and one vehicle annotation by token.
5. Explain how that annotation connects to its `instance` track.
6. Draw the global-to-local coordinate transform used by the future exporter.
7. Write down whether the selected interaction matches a supported highway/intersection template.
8. State which parts would be trajectory-replicated versus only approximated in esmini and CARLA.

Save the selected scene/sample tokens, screenshots, and completed inventory in the ticket evidence for R2S-100.
