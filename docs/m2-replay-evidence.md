# M2 Replay Evidence

## Real esmini run

The M2 baseline was generated and replayed locally from the existing licensed
nuScenes mini data for `scene-0061`:

- Scene token: `cc8c0bf57f984915a77078b10eb33198`.
- Window: first through thirty-ninth keyframe, `19.149566173553467` seconds.
- Selected actor tokens: `6dd2cbf4c24b4caeb625035869bca7b5`,
  `48d58b69b40149aeb2e64aa4b1a9192f`, and
  `bd26c2cdb22d4bb1834e808c89128898`.
- OpenDRIVE approximation: `straight-two-lane`, version `1.0`, registry
  `opendrive-template-registry-v1`.
- esmini: `v3.9.0`, build `6434`.
- Runner timestep: `0.05` seconds.
- Replay result: exit code `0`, completed successfully, `1536` normalized trace
  states.

The runner uses esmini's binary DAT recording and the matching `dat2csv`
utility with 12-decimal output. Its command is reconstructed from:

```bash
export ESMINI_BIN=/path/to/esmini/bin/esmini
export ESMINI_DAT2CSV=/path/to/esmini/bin/dat2csv
```

The source-to-replay pipeline uses `extract_scenario`,
`select_interaction_actors`, `transform_to_local_road_aligned`,
`select_opendrive_template`, `write_openscenario`, and `run_esmini` in that
order. The generated `.xosc` stages the selected `.xodr` beside it and refers to
the map by relative filename.

## Artifacts

Derived artifacts are intentionally outside Git because they contain trajectory
data derived from the licensed local dataset:

- `/tmp/m2-scene-0061/baseline.xosc`
- `/tmp/m2-scene-0061/straight-two-lane-v1.xodr`
- `/tmp/m2-scene-0061/replay.dat`
- `/tmp/m2-scene-0061/replay.csv`
- `/tmp/m2-scene-0061/metrics.json`
- `/tmp/m2-scene-0061/recorded-vs-replayed.png`

The overlay uses solid `recorded` and dashed `replayed` lines. Metrics use
`recorded_timestamps_linear_interpolation_within_overlap` alignment:

| Actor | Samples | Position RMSE (m) | Final displacement (m) | Heading MAE (rad) | Speed MAE (m/s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| ego | 39 | 0.2574 | 0.1030 | 0.0257 | 0.1021 |
| instance-48d58b69b40149aeb2e64aa4b1a9192f | 30 | 0.0561 | 0.0720 | 0.0060 | 0.0429 |
| instance-6dd2cbf4c24b4caeb625035869bca7b5 | 39 | 0.0299 | 0.0014 | 0.0000 | 0.0487 |
| instance-bd26c2cdb22d4bb1834e808c89128898 | 37 | 0.0426 | 0.0025 | 0.0031 | 0.1178 |

## Limitation

This is trajectory replay on a curated local OpenDRIVE template. It is not a
lossless nuScenes map conversion, and the reported metrics measure trajectory
fidelity only. The template selection and approximation mode remain explicit in
scenario provenance.
