# CP1 Native, Canonical and XODR Comparison

## Status

`SELF-VERIFIED`, `DIAGNOSTIC`, `PROVISIONAL`, `OWNER-REVIEW-REQUIRED`

This report records the executed reference-model experiment requested by the CP1
handoff. It does not replace the immutable nearest-lane baseline or claim CP1
acceptance.

## Scope and Baseline

```text
dataset: nuScenes v1.0-trainval
scene: scene-0061
corridor: 40 m, 82 source records
actor scope: ego plus three automatic interaction actors
states: 143
legacy selected-corridor baseline: 20/143 = 13.99%
legacy all-vehicle context: 440/767 = 57.37%
provisional target: 95%
```

The same source trajectories and source window were compared against:

1. native nuScenes lane/polygon geometry;
2. the repaired canonical lane graph;
3. freshly generated repaired OpenDRIVE parsed through the lightweight XODR
   diagnostic adapter.

## Backend Changes

The following capabilities are suitable for the backend and are now implemented:

- `lane_graph_from_nuscenes()` creates a provenance-preserving native graph
  using official map expansion records, polygons, source links and repaired
  discretized paths;
- `lane_graph_from_opendrive()` parses generated line geometry and applies the
  declared lane-width offset for the emitted lane `-1` reference;
- `compare_lane_references()` compares named references without changing the
  legacy matcher;
- lane membership is separated from centerline residual through explicit
  statuses and counts:
  `lane_semantically_valid`, `lane_centerline_offset_high`,
  `lane_polygon_outside`, `footprint_unsupported`, `heading_conflict` and
  `topology_invalid`.

These APIs are dependency-free apart from the existing optional nuScenes map
adapter and do not add GIS or simulator dependencies to the test path.

## Geometry and Topology Provenance

```text
repair version: centerline-repair-v1
corridor records inspected: 82
corridor records repaired: 12
corridor records excluded: 0
corridor topology links checked: 80
corridor topology validation failures: 0
remaining matcher geometry failures: 0
```

## Reference Results

| Reference | States | Lane-semantic valid | Centerline offset high | Polygon outside | Heading conflict | Unmatched | Mean lateral | P95 lateral | Max heading |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Native nuScenes | 143 | 90 | 104 | 42 | 11 | 0 | 3.973 m | 7.365 m | 2.756 rad |
| Canonical graph | 143 | 90 | 104 | 42 | 11 | 0 | 3.973 m | 7.365 m | 2.756 rad |
| Generated XODR | 143 | 100 | 108 | 0 | 8 | 35 | 3.564 m | 7.629 m | 0.372 rad |

The native and canonical results are identical for the selected corridor. This
means the current semantic loss is not caused by canonical graph conversion.
The native reference itself reports 42 polygon-outside states and 11 heading
conflicts, so the unresolved issue is source/reference semantics or native-map
association for the affected actors.

The generated XODR result is not directly comparable as a lane-truth oracle:
it has 35 unmatched states in the lightweight parser and different polygon
semantics because the emitted OpenDRIVE subset represents a road reference line
and a lane width rather than the full native polygon model. This is evidence for
an export/reference limitation, not justification to tune the source matcher.

## Actor Findings

- `instance-e91...`: native and canonical lateral residual remains approximately
  `3.167 m`; no direction rescue. Classify as unresolved lateral association,
  source reference or native-map semantics.
- `instance-e3c...`: native and canonical heading conflict remains present;
  reverse direction remains a counterfactual only. No production lane reversal.
- `instance-fdd...`: native and canonical lateral residual remains approximately
  `7.333 m`; no actor-specific correction is supported.
- Ego dimensions remain unavailable and occupancy remains unsupported.

## Backend Decision

### Add to backend

- Native graph construction with source/provenance IDs.
- Explicit native/canonical/XODR reference comparison.
- Lane membership versus centerline residual separation.
- Lightweight XODR lane reference parsing with declared lane-width offset.
- Formal reference comparison report contracts and deterministic tests.

### Do not add to production behavior

- Actor-specific position offsets.
- Global lane reversal or failing-actor lane reversal.
- Increased nearest-lane or heading tolerances.
- Native-map mutation to improve the selected score.
- Guessed ego dimensions.
- Treating generated XODR as the native lane-truth oracle.

## Remaining Owner Decisions

1. Retain the automatic four-actor scope.
2. Retain unsupported ego dimensions.
3. Keep reverse direction counterfactual-only.
4. Accept the no-correction actor-reference convention.
5. Accept native polygon-outside and heading-conflict findings as unresolved
   diagnostics pending additional approved scenes.

## Acceptance Boundary

```text
CP1 status: PARTIAL / CORRIDOR-EXTERNAL-VERIFIED
scientific status: PROVISIONAL
acceptance claim: no
```

The comparison narrows the cause: native and canonical agree, while source
trajectory/reference semantics remain unresolved. CP1 cannot be marked complete
from this scene or from the diagnostic score.
