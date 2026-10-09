# M2 replay checkpoint evidence

## Scope

This evidence records one local nuScenes mini source window through the complete
M2 path: extraction, interaction selection, local road-aligned transformation,
OpenDRIVE template selection, OpenSCENARIO export, esmini replay, trace
normalization, replay metrics, and recorded-versus-replayed overlay generation.

The source dataset and generated runtime artifacts remain local. This note keeps
only tokens, configuration-independent metadata, measured results, and commands;
it does not commit raw or derived nuScenes content.

## Source And Selection

- Dataset: nuScenes `v1.0-mini`
- Scene: `scene-0061`
- Scene token: `cc8c0bf57f984915a77078b10eb33198`
- Source window: `ca9a282c9e77460f8360f564131a8af5` through `023c4df2d451409881d8e6ea82f14704`
- Source samples: `11`
- Vehicle candidates tracked across the complete window: `10`
- Selected non-ego actors: `3`
- Selected actor types: one `vehicle.truck`, two `vehicle.car`
- Replay coordinate frame: `local_road_aligned`
- OpenDRIVE template: `straight-two-lane`, version `1.0`
- Map mode: `local-template-approximation`

The selection is deterministic and limited to the three closest qualifying
vehicle actors for this run. The source extraction remains in
`nuscenes_global`; the transform uses the ego's first recorded position and yaw
as the local origin and heading.

## Replay Result

- esmini version: `v3.9.0`, build `6434`
- Completed: `true`
- Timed out: `false`
- Exit code: `0`
- Normalized replay trace: `11` samples per actor
- Timestamp alignment: `recorded_timestamps_linear_interpolation_within_overlap`
- Generated runtime artifacts: `baseline.xosc`, `straight-two-lane-v1.xodr`,
  `replay.csv`, and `recorded-vs-replayed.png`

The baseline completed in esmini and produced a normalized trace for ego and all
three selected actors. The overlay distinguishes recorded solid paths from
replayed dashed paths.

## Metrics

All distance values are in metres, speed values in metres per second, and
heading values in radians.

| Actor | Position RMSE | Final displacement | Heading MAE | Speed MAE | Samples |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ego` | 0.368382 | 0.321937 | 0.003781 | 0.114134 | 11 |
| `instance-e91afa15647c4c4994f19aeb302c7179` | 0.020447 | 0.001375 | 0.000000 | 0.044437 | 11 |
| `instance-bc38961ca0ac4b14ab90e547ba79fbb6` | 0.213146 | 0.324692 | 0.000000 | 0.327757 | 11 |
| `instance-c1958768d48640948f6053d04cffd35b` | 0.204039 | 0.174995 | 0.026853 | 0.085955 | 11 |

## Reproduction

The environment and external paths are configured outside source files:

```bash
source .venv/bin/activate
pip install -e ".[dev,devkit]"
export ESMINI_BIN="/absolute/path/to/esmini"
export ESMINI_DAT2CSV="/absolute/path/to/dat2csv"
```

The executable path is intentionally not recorded in this evidence. Reproduce
the pipeline with the public APIs documented in
`docs/wiki-cli-api-reference.md`, using the source scene/window above and a
temporary output directory. The preflight and inventory checks are:

```bash
real2scenario-preflight \
  --root "$NUSCENES_ROOT" \
  --version "v1.0-mini" \
  --map-mode expansion

real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "v1.0-mini" \
  inventory \
  --output /tmp/nuscenes-inventory.json
```

The actual replay call is `write_openscenario(...)` followed by
`run_esmini(...)`; there is no `real2scenario replay` command yet.
