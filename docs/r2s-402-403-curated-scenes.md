# R2S-402/R2S-403 Curated Local Scenes

The local `v1.0-mini` metadata currently contains ten scenes. The M4 demo can
discover all ten, but these three are the recommended review set because their
descriptions cover different interaction patterns:

| Scene | nuScenes description | Imported actors | Imported duration |
| --- | --- | ---: | ---: |
| `scene-0061` | Parked truck, construction, intersection, turn left, following a van | 3 | 19.149566 s |
| `scene-0103` | Many pedestrians right, wait for turning car, long bike rack left, cyclist | 3 | 19.400637 s |
| `scene-0553` | Wait at intersection, bicycle, large truck, pedestrians crossing crosswalk | 3 | 19.900489 s |

The scene tokens and source-window endpoints are read from the local
`scene.json` and `sample.json` metadata at runtime. No raw data or derived
artifacts are committed. Import applies the existing vehicle candidate filter,
interaction selection thresholds (`30 m`, `5 s`, maximum `3` actors), and the
existing local-road-aligned transform.

## Reproducible local flow

Start the API and frontend as described in `docs/r2s-401-local-web-demo.md`.
In the browser:

1. Open `LOCAL PATHS`.
2. Confirm the dataset root points to `data/v1.0-mini` or enter the local path.
3. Apply the paths.
4. Select `IMPORT` for any of the three scenes above.
5. Select the imported baseline from the catalog.
6. Run the deterministic 20-variant batch with seed `7`.
7. Select a result row to inspect generated trajectories, validation, ranking,
   and artifact links.
8. Select `EXPORT XOSC` for a valid result.

With replay disabled, the expected aggregate status depends on the imported
scene's kinematics and configured validation limits. With replay enabled and no
working `ESMINI_BIN`/`ESMINI_DAT2CSV`, valid variants remain valid through
validation but are reported as `simulator-failed` after the optional replay
step. They are never reclassified as kinematic invalid results.

This index is intentionally metadata-only. Licensed nuScenes files, generated
canonical artifacts, replay CSV files, and rendered images remain local-only.
