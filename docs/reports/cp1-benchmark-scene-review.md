# CP1 Benchmark Scene External Review (References, Footprints, Topology)

## Status

`RUNTIME-VERIFIED/DIAGNOSTIC`, `PROVISIONAL`, `CP1 REMAINS PARTIAL/PROVISIONAL`

This slice extends the three CP1 diagnostic families that previously existed only
for `scene-0061` to all five provisional benchmark scenes, over all 60 generated
candidates:

1. per-candidate lane reference attribution (native nuScenes, canonical lane
   graph, generated corridor OpenDRIVE, unnormalized corridor centerlines);
2. per-candidate footprint/occupancy evidence with unsupported vehicle
   dimensions and lane-width sources kept separate;
3. per-scene corridor topology, junction emission and line/arc residual
   evidence on real One-North data.

No matcher tolerance, lane direction, reference convention, actor scope or ground
truth interpretation changed, and nothing was repaired to raise a rate. The
immutable `scene-0061` selected-corridor baseline `20/143 = 13.99%` is untouched.

## Implementation

`scripts/cp1_benchmark_scene_review.py` composes the existing domain contracts
rather than adding new science:

- the parent scenario is rebuilt in `nuscenes_global` through the cached
  metadata index, and the recorded `RoadAlignedTransform` expresses every
  reference in the candidates' local road-aligned frame, so the comparison
  measures reference semantics rather than a frame mismatch;
- each corridor is built twice, in `line` and `line_arc` geometry mode, and both
  OpenDRIVE files are stored privately;
- `lane_centerlines_from_nuscenes()` and `lane_centerlines_from_opendrive()`
  return records in emitted road order, while `build_lane_graph()` provides the
  direction-normalized graph view, so both reference conventions stay explicit
  and separable instead of being conflated;
- occupancy uses the generated corridor widths with the width source recorded
  per state, and vehicles without dimensions are reported as unsupported rather
  than assigned a guessed footprint.

## Finding 1: Corridor Topology, Junctions and Arc Residuals Are Clean

| Scene | Lanes | Roads | Junctions | Width source | Arc segs | Line segs | p95 residual | Max residual | Subset | Dangling junction refs | Dangling road links |
|---|---|---|---|---|---|---|---|---|---|---|---|
| scene-0380 | 74 | 74 | 45 | 74 polygon / 0 fallback | 81 | 35 | 0.0466 m | 0.0490 m | valid | 0 | 0 |
| scene-0962 | 138 | 138 | 73 | 138 polygon / 0 fallback | 136 | 77 | 0.0447 m | 0.0488 m | valid | 0 | 0 |
| scene-0945 | 101 | 101 | 54 | 101 polygon / 0 fallback | 92 | 45 | 0.0405 m | 0.0492 m | valid | 0 | 0 |
| scene-0957 | 64 | 64 | 39 | 64 polygon / 0 fallback | 76 | 25 | 0.0444 m | 0.0495 m | valid | 0 | 0 |
| scene-0981 | 81 | 81 | 45 | 81 polygon / 0 fallback | 85 | 33 | 0.0475 m | 0.0492 m | valid | 0 | 0 |

Every corridor passes the OpenDRIVE subset check, emits zero dangling junction
references and zero dangling road links, derives every lane width from the
nuScenes polygon rather than the fallback constant, and fits arcs within the
declared `0.05 m` tolerance. Junction emission and arc fitting are therefore
externally verified for these corridors; they remain engineering prototype
evidence, not accepted map fidelity.

## Finding 2: Lane Membership Is Valid While Centerline Distance Fails

State counts aggregate all 12 candidates per scene. Each column is reported
separately, never combined into a single acceptance number.

| Scene | Reference | lane_semantically_valid | lane_centerline_offset_high | heading_conflict | unmatched | states |
|---|---|---|---|---|---|---|
| scene-0380 | native nuScenes | 1248 | 21 | 336 | 0 | 1584 |
| scene-0380 | canonical lane graph | 1248 | 21 | 336 | 0 | 1584 |
| scene-0380 | generated corridor XODR | 1320 | 831 | 264 | 0 | 1584 |
| scene-0380 | corridor centerlines | 1320 | 831 | 264 | 0 | 1584 |
| scene-0962 | native nuScenes | 1044 | 183 | 0 | 0 | 1044 |
| scene-0962 | canonical lane graph | 1044 | 183 | 0 | 0 | 1044 |
| scene-0962 | generated corridor XODR | 975 | 450 | 57 | 12 | 1044 |
| scene-0962 | corridor centerlines | 975 | 450 | 57 | 12 | 1044 |
| scene-0945 | native nuScenes | 1272 | 36 | 84 | 0 | 1356 |
| scene-0945 | canonical lane graph | 1272 | 36 | 84 | 0 | 1356 |
| scene-0945 | generated corridor XODR | 1224 | 687 | 105 | 27 | 1356 |
| scene-0945 | corridor centerlines | 1224 | 687 | 105 | 27 | 1356 |
| scene-0957 | native nuScenes | 1692 | 0 | 276 | 0 | 1968 |
| scene-0957 | canonical lane graph | 1692 | 0 | 276 | 0 | 1968 |
| scene-0957 | generated corridor XODR | 1692 | 462 | 276 | 0 | 1968 |
| scene-0957 | corridor centerlines | 1692 | 462 | 276 | 0 | 1968 |
| scene-0981 | native nuScenes | 1368 | 0 | 264 | 0 | 1632 |
| scene-0981 | canonical lane graph | 1368 | 0 | 264 | 0 | 1632 |
| scene-0981 | generated corridor XODR | 1434 | 429 | 198 | 0 | 1632 |
| scene-0981 | corridor centerlines | 1434 | 429 | 198 | 0 | 1632 |

Three conclusions follow, and they are consistent across all five scenes:

1. **Native and canonical agree exactly again**, now on five independent scenes
   rather than one. Canonical map conversion is ruled out as the cause of the low
   strict road-match rate.
2. **The generated OpenDRIVE reproduces the corridor reference exactly**; the
   unnormalized and normalized corridor views are identical row for row. Export
   is ruled out as the cause.
3. **Lane membership and centerline distance disagree.** Between roughly 66% and
   100% of states are lane-semantically valid, while the strict `0.5 m` /
   `0.2 rad` centerline match rates are `0.0000` to `0.2500`. The corridor
   reference additionally shows many more `lane_centerline_offset_high` states
   than the native reference (`429-831` versus `0-183`), which localizes the
   residual to a lateral offset between the driven path and the emitted corridor
   centerlines rather than to a wrong lane assignment.

`heading_conflict` remains the largest classification for the native reference in
four of five scenes, which is the direction question CP1 already flagged and
which remains counterfactual-only.

## Finding 3: Footprint Evidence Is Partial by Construction

| Scene | States | Occupied | Outside | Unsupported | Actors without dimensions | Width sources |
|---|---|---|---|---|---|---|
| scene-0380 | 1584 | 363 | 729 | 492 | ego | generated corridor XODR |
| scene-0962 | 1044 | 474 | 78 | 492 | ego | generated corridor XODR |
| scene-0945 | 1356 | 429 | 435 | 492 | ego | generated corridor XODR |
| scene-0957 | 1968 | 1251 | 225 | 492 | ego | generated corridor XODR |
| scene-0981 | 1632 | 273 | 867 | 492 | ego | generated corridor XODR |

Every scene reports exactly `492` unsupported states, which is the `41`-state ego
trajectory across `12` candidates: the canonical scenario never carries ego
dimensions. Those states stay `vehicle_dimensions_unavailable` and were not
filled with a guess. All lane widths come from the generated corridor and the
source is recorded per state, so annotation-derived, polygon-derived and
fallback widths remain separable. Occupancy counts for `scene-0380` and
`scene-0981` should be read with the offset finding above: a vehicle can be
inside its lane yet more than `0.5 m` from the lane centerline.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
247 passed, 1 warning (existing Starlette/httpx deprecation).
```

## Boundaries

- CP1 stays `PARTIAL/PROVISIONAL`; nothing here accepts map fidelity, lane truth
  or a tolerance.
- The benchmark scene index is agent-selected and unapproved.
- Corridors, review JSON and any derived artifact remain local/private.
- Reverse direction stays counterfactual-only and no lane was reversed.
- CARLA remains unverified and post-MVP.

## Next Action

Owner interpretation of the direction and lateral-offset findings, using this
per-scene attribution rather than the single-scene inference it replaces. The
agent-actionable follow-up is to decide, from this evidence, whether the
accepted lane-semantic metric should be reported separately from the centerline
metric in the G3 gate; that is a scientific policy decision and is not taken
here.