# CP1 Agent Handoff: Next Semantic-Alignment Experiment

Status: `SELF-VERIFIED-DIAGNOSTIC / OWNER-REVIEW-REQUIRED`  
Scope: scene-0061, 40 m Singapore One-North corridor

## Current Diagnosis

The lane-sequence matcher is implemented and the first geometry/topology repair
pass is complete. The remaining blockers are reference-model and actor-semantics
questions, not HMM tuning, duplicate-point geometry, or selected-corridor link
integrity:

```text
high confidence:    29
low confidence:     93
ambiguous:           10
direction conflict:  11
topology failures:    0
geometry failures:    0
mean lateral error:   3.979 m
p95 lateral error:    7.365 m
```

Do not solve this by tuning HMM weights, changing actor-specific offsets,
reversing one lane, or replacing the immutable baseline:

```text
selected corridor baseline: 20/143 = 13.99%
all-vehicle baseline:       57.37%
```

## Completed Before This Handoff

- `centerline-repair-v1` inspected 82 corridor records, repaired 12, excluded 0
  and left zero geometry failures.
- Explicit topology validation checked 80 selected-corridor links with zero
  reciprocal-link, endpoint-gap or heading-discontinuity failures.
- The ingestion reference convention is explicit and versioned as
  `source-reference-convention-v1`; no actor-specific correction is applied.
- The immutable nearest-lane baseline remains unchanged.

These completed items must be reported as evidence, not repeated as the next
experiment. Full-map diagnostics still contain six topology-gap states and must
be kept separate from the selected-corridor result.

## Executed Comparison Result

The native/canonical/XODR comparison has now been executed and backend contracts
were added for native nuScenes graph construction, lane-membership separation,
and lightweight XODR lane-reference parsing. Results for the same 143 states:

```text
reference          lane-valid  offset-high  polygon-outside  heading-conflict  unmatched
native nuScenes    90          104          42               11                0
canonical graph    90          104          42               11                0
generated XODR     100         108          0                8                 35
```

Native and canonical agreement rules out canonical graph conversion as the
primary cause. Generated XODR is not treated as native lane truth because its
subset road/lane representation does not preserve the full native polygon
model and the lightweight parser leaves 35 states unmatched.

## Required Work

Implement a private diagnostic that compares the same actor trajectories against
three references:

```text
native nuScenes map
project canonical lane graph
generated OpenDRIVE
```

Use the official nuScenes map expansion API and arcline geometry for the native
reference:

- <https://github.com/nutonomy/nuscenes-devkit>
- <https://www.nuscenes.org/tutorials/map_expansion_tutorial.html>

For every state, report:

- lane/connector ID and provenance;
- polygon containment;
- signed lateral offset;
- annotation-yaw and motion-heading error;
- predecessor/successor validity;
- candidate confidence and failure status.

This native/canonical/XODR decomposition is the primary unresolved CP1
experiment. It maps directly to the remaining blockers:

| Remaining blocker | Required comparison | Proposed resolution |
|---|---|---|
| `instance-e91...` lateral residual | Native polygon/centerline vs canonical graph vs XODR; global reference-point sensitivity | Fix builder/export only if native is good and generated is shifted; otherwise classify source/reference ambiguity. |
| `instance-fdd...` lateral residual | Same three-way comparison plus footprint/width capability separation | Do not apply actor-specific offsets; accept only a globally supported convention or retain unresolved. |
| `instance-e3c...` direction conflict | Annotation yaw, motion heading, native lane heading, canonical heading and XODR heading | Classify source yaw, true reverse motion, native direction error, generated direction error or uncertainty; keep reversal counterfactual-only. |
| Centerline-vs-lane membership | Native/canonical polygon containment and boundary distance | Report `lane_semantically_valid` independently from `lane_centerline_offset_high`. |
| Six full-map topology gaps | Source link provenance and corridor/full-map scope comparison | Classify as boundary gap, unsupported actor motion, source-link issue or builder issue; do not affect selected-corridor topology claim. |
| Unsupported occupancy | Dimension and width provenance | Keep ego occupancy unsupported; do not guess dimensions or mix width sources. |

Compare the three results to identify whether the loss is caused by:

- source track or yaw semantics;
- actor reference-point convention;
- canonical map conversion;
- OpenDRIVE export;
- centerline metric rather than lane membership.

## Required Metric Separation

Do not use centerline distance alone as semantic lane acceptance. Report these
independently:

```text
lane_semantically_valid
lane_centerline_offset_high
lane_polygon_outside
footprint_unsupported
heading_conflict
topology_invalid
```

Keep ego dimensions explicitly unsupported. Never guess them. Keep annotation,
polygon-derived and fallback widths separate.

For `instance-e91...` and `instance-fdd...`, test only globally declared actor
reference conventions. Do not apply actor-specific corrections.

For `instance-e3c...`, compare annotation yaw, motion heading, native lane
heading and generated lane heading. Keep reverse direction counterfactual-only.

## Required Evidence

Create a private report containing:

```text
native-nuscenes-oracle.json
canonical-lane-sequence.json
geometry-conversion-residuals.json
actor-reference-sensitivity.json
direction-counterfactual.json
comparison-summary.md
```

Completed comparison report:
`docs/reports/cp1-native-canonical-xodr-comparison.md`.
The remaining work is targeted actor/reference and cross-scene validation, not
repeating geometry repair or selected-corridor topology repair.

Record git revision, dataset/map/XODR hashes, matcher configuration, repair
version, lane-graph version and actor-selection policy.

Include the completed repair evidence from
`docs/reports/cp1-geometry-topology-follow-up.md`. The five old geometry
failures and 44 old selected-corridor topology gaps must not be reported as
current post-repair defects.

Run the comparison for:

- ego;
- selected interaction actors;
- all vehicles, if available.

## Acceptance Boundaries

Keep the CP1 status `PARTIAL/PROVISIONAL` until the evidence is interpreted.
Do not change the 95% reference, actor-selection policy or lane-direction
policy from this scene alone. Do not claim CP1 acceptance from a higher HMM
score. CARLA is outside this CP1 task and remains a separate CP2 track.

The owner decision after this experiment is limited to:

1. retaining the automatic four-actor scope;
2. retaining unsupported ego dimensions;
3. keeping reverse direction counterfactual-only;
4. accepting or disputing the no-correction source-reference convention; and
5. accepting the remaining lateral/direction findings as unresolved diagnostics
   rather than tuning thresholds.

## References

- Current design: `docs/current/cp1-semantic-alignment-next-solution.md`
- Current matcher: `src/real2scenario/road_match.py`
- CP1 contract: `docs/current/technical-contracts.md`
- HMM map matching: <https://www.microsoft.com/en-us/research/publication/hidden-markov-map-matching-through-noisy-position-data/>
- Argoverse lane graphs: <https://arxiv.org/abs/1911.02620>
