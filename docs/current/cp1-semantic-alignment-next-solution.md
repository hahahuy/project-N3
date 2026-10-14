# CP1 Semantic Alignment: Recommended Next Solution

Status: `RECOMMENDED NEXT EXPERIMENT`  
Updated: 2026-10-13

## Conclusion

Do not continue tuning HMM weights or expanding manual review as the primary
response to the latest result:

```text
high confidence:   29
low confidence:    93
ambiguous:          10
topology failures:   0
geometry failures:   0
mean lateral error:  3.979 m
p95 lateral error:   7.365 m
```

With geometry and topology defects removed, the remaining error is more likely
to be a reference-model mismatch than a decoder problem. The next experiment
must determine whether the loss comes from the source track, actor reference
point, native map semantics, canonical graph conversion or OpenDRIVE export.

The recommended decomposition is:

```text
same trajectory
  -> native nuScenes lane/polygon reference
  -> project canonical lane graph reference
  -> generated OpenDRIVE reference
```

Do not use generated XODR as the only authority for judging whether the source
trajectory belongs to a lane.

## Research Basis

The official nuScenes devkit exposes lane/lane-connector records, polygons,
arcline geometry, lane discretization and closest-lane utilities:

- [nuScenes devkit](https://github.com/nutonomy/nuscenes-devkit)
- [nuScenes map API](https://github.com/nutonomy/nuscenes-devkit/blob/master/python-sdk/nuscenes/map_expansion/map_api.py)
- [nuScenes map tutorial](https://www.nuscenes.org/tutorials/map_expansion_tutorial.html)
- [nuScenes paper](https://arxiv.org/abs/1903.11027)

Closest-lane lookup should be used for candidate generation only. Native lane
IDs and directed transitions must be retained for semantic matching.

Newson and Krumm's HMM map-matching work establishes the candidate,
emission, transition and Viterbi pattern for noisy/sparse trajectories:

- [HMM map matching reference](https://www.microsoft.com/en-us/research/publication/hidden-markov-map-matching-through-noisy-position-data/)
- Lou et al., low-sampling-rate map matching,
  [DOI](https://doi.org/10.1145/1653771.1653785)

The current project already implements the decoder pattern. The next step is
validating the reference model rather than searching for a better weight set.

Argoverse and LaneGCN support explicit lane-segment graphs with centerlines,
polygons, directions and adjacency:

- [Argoverse paper](https://arxiv.org/abs/1911.02620)
- [Argoverse API](https://github.com/argoverse/argoverse-api)
- [LaneGCN paper](https://arxiv.org/abs/2007.13732)

Reuse these representation principles without adding a forecasting model or a
new runtime dependency to CP1.

## Priority 1: Native nuScenes Oracle

Implement a private diagnostic matching the same canonical actor states against
the original nuScenes map before OpenDRIVE conversion.

Per state, retain:

- native lane/connector candidates and source IDs;
- polygon containment;
- signed lateral offset to native centerline;
- annotation-yaw and motion-heading error;
- predecessor/successor transition validity;
- native map provenance.

Use the official map API and arcline discretization. Do not read generated XODR
back into the native oracle.

Produce three results:

```text
native map -> trajectory
canonical lane graph -> trajectory
generated OpenDRIVE -> trajectory
```

Interpretation:

| Native | Canonical | XODR | Meaning |
|---|---|---|---|
| good | bad | bad | map-builder/conversion loss |
| good | good | bad | XODR export or consumer loss |
| bad | bad | bad | source track, actor semantics or native-map mismatch |
| good | shifted similarly | shifted similarly | frame/reference-point convention |
| ambiguous | ambiguous | ambiguous | scene cannot establish lane truth |

This is more valuable than further overlays or HMM tuning.

## Priority 2: Separate Lane Membership From Centerline Offset

A vehicle can be inside the correct lane without following its centerline. Keep
the lateral residual, but do not use it alone as a binary lane-semantic result.

Report independently:

- center point inside lane polygon;
- oriented footprint inside polygon when dimensions exist;
- distance to lane boundaries;
- signed lateral coordinate `d`;
- longitudinal coordinate `s`;
- heading agreement;
- topology validity.

Use statuses such as:

```text
lane_semantically_valid
lane_centerline_offset_high
lane_polygon_outside
footprint_unsupported
heading_conflict
topology_invalid
```

If the 3.979 m residual remains inside a valid lane polygon, the centerline
threshold is measuring a different property from lane membership. If it is
outside the polygon, the map or track remains unresolved.

## Priority 3: Global Actor Reference-Point Sensitivity

For `instance-e91...` and `instance-fdd...`, compare globally declared
conventions, never actor-specific corrections:

1. annotation box center;
2. rear axle approximation;
3. front axle approximation;
4. box center plus a fixed heading-derived offset.

Use source dimensions/yaw to justify any correction. Report mean/P95 lateral
error, native/generated residual, polygon containment, heading error and
cross-actor improvement. Accept a convention only if it improves multiple
actors and has source-model support.

## Priority 4: Direction Semantics

For `instance-e3c...`, compare annotation yaw, motion heading, native lane
heading and generated lane heading. Classify:

```text
source_annotation_yaw_error
true_reverse_motion
native_map_direction_error
generated_map_direction_error
coordinate_heading_error
uncertain
```

Do not reverse the production lane graph from one actor. A policy change needs
repeated evidence across approved scenes.

## Priority 5: Source-to-Output Map Residuals

Compare each native lane/connector against the generated representation using:

- centerline RMSE and maximum error;
- bidirectional Hausdorff distance;
- heading error;
- polygon IoU/boundary distance;
- width error along `s`;
- endpoint gap;
- predecessor/successor preservation;
- connector turn-angle preservation.

Use line/arc fitting only when it reduces source-to-output residual. A smoother
arc is not automatically a more faithful map.

If conversion residual is high, either fix the builder, use native geometry as
the semantic reference and XODR as an execution export, or narrow CP1 claims.
Do not tune the matcher to fit a visibly displaced map.

## Dimensions and Occupancy

Keep capabilities separate:

```text
lane association:                 no dimensions required
center-point polygon containment: no dimensions required
oriented footprint occupancy:     dimensions required
ego footprint occupancy:          unsupported without approved dimensions
```

Do not guess ego dimensions. Keep annotation, polygon-derived and fallback
width results in separate fields. Missing ego dimensions block full occupancy
acceptance, not a scoped lane-sequence diagnostic.

## Evidence Bundle

After the oracle/conversion comparison, create a private reproducible bundle:

```text
run-card.yaml
baseline-nearest-lane.json
native-nuscenes-oracle.json
canonical-lane-sequence.json
generated-xodr-match.json
geometry-conversion-residuals.json
topology-validation.json
actor-reference-sensitivity.json
direction-counterfactual.json
occupancy-capability-report.json
review-intervals.json
comparison-summary.md
```

Record git, dataset, source-map, XODR, repair, lane-graph, matcher and actor
selection hashes/configuration. Keep trajectory-rich artifacts private.

## CARLA Scope

CARLA custom-map loading is a separate CP2/simulator track. Do not block CP1
semantic-map evaluation on CARLA and do not use CARLA as the lane-truth oracle.

## Decision Matrix

| Native map | Generated map | Decision |
|---|---|---|
| good | bad | Fix map builder/conversion. |
| good | good, polygon valid, centerline offset high | Separate lane membership from centerline metric. |
| bad | bad | Investigate source track, actor reference, yaw or native-map semantics. |
| direction differs | unknown | Fix direction normalization/connector semantics. |
| no stable reference | unknown | Narrow the scene claim; do not force acceptance. |

## Recommended Order

1. Implement the native nuScenes oracle.
2. Split lane membership from centerline residual.
3. Run global actor-reference sensitivity.
4. Compare native-to-canonical-to-XODR residuals.
5. Classify the reverse-direction actor using all four headings.
6. Produce the reproducible evidence bundle.
7. Run the protocol on 3-5 additional approved scenes.
8. Reassess the provisional 95% policy only after cross-scene evidence.
9. Keep CARLA verification under CP2.

## Final Recommendation

Do not try to force the current scene from a 3.979 m mean lateral error to 95%
through threshold or decoder tuning. If the native oracle is good but generated
output is poor, fix the builder. If native and generated polygons are valid but
centerline offsets are large, distinguish semantic lane membership from
centerline closeness. If the native oracle is also poor, narrow CP1 rather than
tuning the generated map to fit the trajectory.
