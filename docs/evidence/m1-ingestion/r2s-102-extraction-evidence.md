# R2S-102: Trajectory extraction evidence

## Adapter boundary

`real2scenario.ingestion.extract_scenario` reads nuScenes metadata directly and
returns the simulator-independent canonical `Scenario`. It does not import the
nuScenes devkit, read raw sensor payloads, write XML, or choose interaction
actors automatically.

Input is a `SourceWindow` with scene and inclusive keyframe endpoints plus one
or more explicit nuScenes instance tokens. Explicit actor selection is temporary
and intentional: distance/TTC ranking and manual override belong to R2S-103.

The extracted scenario uses `coordinate_frame="nuscenes_global"`. R2S-201 must
perform the versioned source-global to local road-aligned transform before any
simulator export.

## Extraction method

- Ego states use `LIDAR_TOP` keyframe `sample_data` records linked to
  `ego_pose` records.
- Actor states join `sample_annotation` by `(sample_token, instance_token)`;
  `instance` and `category` provide stable ID and actor type.
- Actor dimensions map nuScenes `[width, length, height]` to canonical
  `width_m` and `length_m`.
- Yaw is derived from nuScenes quaternion `[w, x, y, z]`.
- Speed is a documented planar finite-difference estimate over available
  keyframes. A single-state actor has speed `0.0` m/s.
- All actor timestamps are relative to the source-window start, even if an
  actor first appears later in the window.

## Synthetic evidence

`tests/test_ingestion.py` creates a temporary, synthetic nuScenes metadata
layout. It verifies a successful ego-plus-actor extraction and key error paths:

- selected actor absent from the requested window;
- source-window end preceding its start;
- empty actor selection;
- actor first observed after the source-window start.

No restricted nuScenes content is included in this fixture.

## Real-data smoke evidence

Command executed from the project root using the local licensed dataset:

```bash
source .venv/bin/activate
python -c "from pathlib import Path; import json; from real2scenario import SourceWindow, extract_scenario, artifact_to_json, baseline_artifact_to_dict; root=Path('data/v1.0-mini'); scene=json.loads((root/'v1.0-mini/scene.json').read_text())[0]; samples={row['token']: row for row in json.loads((root/'v1.0-mini/sample.json').read_text())}; token=scene['first_sample_token']; chain=[]; [chain.append(token) or (globals().__setitem__('token', samples[token]['next'])) for _ in range(10)]; annotations=json.loads((root/'v1.0-mini/sample_annotation.json').read_text()); instance_token=next(row['instance_token'] for row in annotations if row['sample_token'] == chain[0]); scenario=extract_scenario(root, SourceWindow(scene['token'], chain[0], chain[-1]), [instance_token]); artifact_json=artifact_to_json(baseline_artifact_to_dict(scenario)); print(scenario.scenario_id, scenario.duration_s, len(artifact_json))"
```

Observed result:

- Scene token: `cc8c0bf57f984915a77078b10eb33198` (`scene-0061`).
- Window: `ca9a282c9e77460f8360f564131a8af5` through
  `9813c23a5f1448b09bb7910fea9baf20` (10 keyframes, 4.549764 s).
- Selected instance token: `6dd2cbf4c24b4caeb625035869bca7b5`.
- Extracted actors: ego (10 states) and `human.pedestrian.adult` (10 states).
- Baseline artifact JSON validated and serialized at 3,409 bytes.

The generated artifact was intentionally not persisted or committed because it
contains derived coordinates from the licensed local dataset.
