# Dataset Update Report

## Local Dataset

The working dataset is outside the repository at:

```text
$HOME/datasets/nuscenes
```

No raw data or derived artifacts were copied into the repository.

Inventory supplied/verified locally:

- `maps/`: approximately 457 MB, including raster basemaps and vector map expansion.
- `samples/`: approximately 11 GB, 80,916 files across 12 sensors.
- `sweeps/`: approximately 67 GB, 436,757 files across 12 sensors.
- `v1.0-trainval/`: approximately 2.5 GB, all 11 required tables.
- `v1.0-test/`: approximately 336 MB, metadata only; no instance/annotation tables.

## Preflight

```text
v1.0-trainval: READY, map_mode=expansion
v1.0-test: READY, map_mode=expansion
```

The preflight command was run against `$HOME/datasets/nuscenes` and did not
modify the dataset.

## Scene/Map Inventory

- `v1.0-trainval`: 850 scenes, 68 logs, 4 map records.
- Singapore One-North: 183 metadata scenes.
- Current downloaded sample files match 170 scenes across the available batch;
  94 of those are Singapore One-North.
- A metadata-only candidate set of 50 Singapore One-North scenes was generated
  outside the repository for the next curation step. It is not final benchmark
  approval.

## Vector Map Availability

`maps/expansion/singapore-onenorth.json` is present and contains:

- 936 `lane` records;
- 1,066 `lane_connector` records;
- 2,002 `arcline_path_3` records;
- 4,886 polygons;
- 37,740 nodes;
- connectivity data for 2,002 paths.

This removes the previous CP1 input-data blocker. CP1 geometry fitting,
OpenDRIVE emission, continuity and road-match remain implementation work.

The first local builder run has now been performed outside the repository:

```text
map: singapore-onenorth
roads emitted: 2002
geometry records: 12061
unsupported arcline records: 0
xodr structural validation: pass
xodr sha256: b7bde84a554529110ea99ec9d1def93cab763a2c92aa06797e731b5eb2005d4c
```

This is an engineering prototype only. It currently emits deterministic line
segments from discretized arcline poses; junction element emission, continuity
reports, lane-width polygon estimates and lane-level road-match are still open.

## Configuration Change

`WebSettings` now prefers `$HOME/datasets/nuscenes` when it contains
`v1.0-trainval` or `v1.0-mini`. The dataset version remains configurable via
`NUSCENES_VERSION` and defaults to `v1.0-trainval` for a local full/batch setup.

Recommended explicit environment:

```text
NUSCENES_ROOT=$HOME/datasets/nuscenes
NUSCENES_VERSION=v1.0-trainval
```

## Limitations

- The 50-scene list is candidate metadata only.
- `v1.0-test` cannot support trajectory extraction in this setup because its
  metadata has no `instance` or `sample_annotation` table.
- No sensor or map data was added to git.
