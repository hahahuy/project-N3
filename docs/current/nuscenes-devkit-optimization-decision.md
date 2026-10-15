# nuScenes Devkit Optimization Decision

Status: `APPROVED / IMPLEMENTATION GUIDE`
Date: `2026-10-15`

## Decision

Use the official nuScenes devkit as the authoritative adapter for interpreting
recorded sensor, annotation, map and CAN data. Keep Real2Scenario application
contracts, provenance, private-artifact policy, scenario editing, simulator
sessions and browser rendering as application-owned responsibilities.

The devkit is the semantic reference for behavior equivalent to:

```python
nusc.render_sample_data(sample["data"]["LIDAR_TOP"], nsweeps=5, underlay_map=True)
```

The browser must not call the devkit directly. A cached backend adapter prepares
typed, local-private payloads and provenance; the browser renders those payloads.

## Target Adapter

Create a cached `NuScenesDatasetAdapter` around:

- `nuscenes.nuscenes.NuScenes` for record lookup and dataset metadata;
- `LidarPointCloud.from_file_multisweep` for `LIDAR_TOP` history;
- `RadarPointCloud` for future radar evidence;
- `NuScenes.get_sample_data`, `get_boxes` and `Box` for recorded annotations;
- `transform_matrix` and `pyquaternion.Quaternion` for official transforms;
- `NuScenesMap` and map expansion helpers for map layers and patches;
- `NuScenesExplorer` semantics for camera/point projection;
- `NuScenesCanBus` for synchronized telemetry;
- the existing `MetadataIndex` for large scene/benchmark discovery and cache queries.

## Optimization Order

1. Replace manual LiDAR sweep traversal with `from_file_multisweep`, preserving
   reference timestamp, per-sweep timestamps, offsets and transform provenance.
2. Cache `NuScenes` record access and map APIs per dataset/version.
3. Use NumPy vectorized point filtering/decimation/serialization instead of a
   Python `struct.pack` loop.
4. Use official `get_sample_data`/`get_boxes` and `Box` transforms for recorded
   annotation overlays.
5. Use `NuScenesMap` geometry for map underlay and normalize browser-ready layers.
6. Cache CAN messages and use sorted timestamp lookup without treating CAN as
   spatial pose.
7. Add SciPy `cKDTree` only for measured spatial crop/nearest queries.
8. Add radar and camera projection after the LiDAR evidence contract is stable.

## Evidence Rules

`nuscenes-sensor-evidence-v1` must preserve reference sample-data identity,
sweep tokens/timestamps/offsets, calibration and ego-pose transforms, coordinate
frame, map and annotation provenance, CAN source/timestamp alignment, decimation
metadata, local-private visibility and explicit unavailable reasons.

Historical sweeps must be labelled as historical. Motion smear is expected and
must not be presented as an instantaneous cloud. CAN telemetry never silently
replaces nuScenes `ego_pose` as the spatial pose authority.

## Boundaries

- The current authoring Top-down view remains the map/trajectory/editing view.
- Sensor Evidence is a separate view and must not replace authoring.
- Recorded sensor evidence is not generated variant sensor output.
- Devkit data does not change the canonical scenario schema or scientific policy.
- Raw and derived nuScenes data remain local/private.
- esmini live state, image artifacts, CARLA and replay metrics remain separate.
- Open3D, PyTorch and Pandas are not required without a measured need.

## Acceptance

Add tests for token traversal, transform composition, multi-sweep offsets, map
availability, annotation provenance, CAN alignment, vectorized payload counts,
private-path confinement and unavailable states. Run docs, Python, frontend and
production-build checks; record runtime limitations without synthetic substitution.
