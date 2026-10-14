# R2S-201 Local Coordinate Transform Evidence

`real2scenario.coordinates` converts a recorded source scenario into the
project's `local_road_aligned` frame. The source scenario is never modified.

## Frame contract

- Input frame: `RoadAlignedTransform.source_frame`, normally `nuscenes_global`.
- Output frame: `local_road_aligned`.
- Position units: metres; yaw units: radians; speed units: metres per second.
- Local `x` points forward along the configured road heading; local `y` points
  left; local `z` is up. The canonical model stores the horizontal plane only.
- The transform is a rigid translation and rotation around the configured source
  origin. It does not reconstruct a lossless OpenDRIVE map.

The transformed scenario carries the version, source and target frames, origin,
heading, axes, and configured round-trip tolerance in provenance. The default
transform version is `local-road-aligned-v1`.

## Verification

`tests/test_coordinates.py` covers a known point, source-scenario immutability,
source-frame mismatch, invalid tolerance, inverse round-trip at configured
tolerance, and yaw wrapping on both sides of the `-pi`/`pi` boundary.

The existing visualizer can display a transformed scenario in this same frame;
an original/replay overlay remains M2 checkpoint evidence after the esmini
runner and trace parser land in R2S-204.
