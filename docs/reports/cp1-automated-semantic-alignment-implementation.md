# CP1 Automated Semantic Alignment Implementation

## Status

`DIAGNOSTIC`, `PROVISIONAL`, `UNVERIFIED`, `DEFER`

This report records the dependency-free lane-sequence diagnostic. It does not
claim CP1 acceptance, G3 completion, CARLA compatibility or a change to the
production lane-direction policy.

## Algorithm

- Version: `lane-sequence-match-v1`.
- Graph version: `lane-graph-v1`.
- Decoder: deterministic Viterbi-style dynamic programming over top-K lane
  candidates for each actor state.
- Existing nearest-lane API and `LaneRoadMatchReport` remain unchanged.
- Reverse direction is retained as a counterfactual signal and is never used to
  mutate the production lane records.

## Configuration

The versioned `LaneSequenceMatchConfig` exposes all scoring inputs:

```text
candidate_radius_m=8.0
max_candidates=5
position_sigma_m=1.0
heading_sigma_rad=0.35
outside_polygon_penalty=4.0
boundary_penalty=1.0
lane_change_penalty=2.0
reverse_direction_penalty=8.0
```

Position, annotation-heading, motion-heading, speed/progress and topology
costs are recorded by configuration rather than hidden in the public API.

## Lane-Graph Provenance

`build_lane_graph()` copies stable lane IDs, source IDs, sampled poses,
cumulative arc length, explicit predecessor/successor links, legal lane-change
links, connector/junction metadata, polygons, widths and normalized travel
direction from `LaneCenterlineRecord`. Unknown links, invalid polygons,
non-positive geometry and out-of-range widths are reported as geometry failures.
No topology edge is inferred from nearest geometry at match time.

## Outputs And Triage

`diagnose_lane_sequence_match()` returns per-state candidates, best/second path
scores, score margins, confidence, direction classification, explicit statuses,
lane switches, topology violations, geometry failures and review intervals.
`diagnose_lane_sequence_triage()` additionally compares the sequence with the
legacy rank-1 candidates and evaluates only caller-declared transform
hypotheses without mutating the scenario.

Manual review intervals are emitted for low margins, topology gaps, persistent
lateral residuals, heading conflicts, outside geometry and unsupported width
evidence. Missing actor dimensions are reported as occupancy limitations and
do not automatically become lane mismatches.

## Synthetic Verification

`tests/test_road_match.py` covers:

- straight and parallel lanes;
- declared lane changes and undeclared lane changes;
- reverse motion classification;
- noisy/outside-polygon observations;
- missing dimensions;
- deterministic output and source scenario immutability;
- ambiguous lanes and transform-hypothesis triage.

The focused road-match suite passes with the new diagnostic while the original
nearest-lane tests remain unchanged.

## Scene-0061 Comparison Contract

An exploratory private self-verification has now been completed against the
accessible `v1.0-trainval` scene-0061 data and declared 82-record corridor.
It is not an owner-approved acceptance run. Any comparison must retain this
immutable baseline:

```text
selected corridor baseline: 20/143 = 13.99%
all-vehicle baseline: 57.37%
```

The required comparison columns are nearest-lane baseline, HMM best path,
high-confidence-only path, ambiguous/low-confidence fraction, topology
violations, geometry failures and direction counterfactuals. No higher HMM
score may be interpreted as CP1 acceptance.

The self-verification produced 143 retained geometry candidates, classified as:

```text
high-confidence:       29
low-confidence:        49
ambiguous:              12
unmatched-topology:     44
direction-conflict:      9
unmatched-geometry:       0
geometry validation failures: 5
```

The five geometry failures are non-positive centerline segments in map records
`26c04569-f75f-4198-8284-e3a1a5ee9f16`,
`69699cdc-4d68-4bb2-b977-d33b3082cdee`,
`c119fed8-400d-486a-93a0-6738464a3680`,
`ec65b625-ab99-49a2-bd3e-ba1716184c0a` and
`fea4c05c-c4ce-499d-8bd9-9070f080eb70`.

## Known Limitations

- Existing map-builder integration still needs to populate explicit lane links,
  connector semantics and boundary data for private corridor records.
- The current public graph adapter uses lightweight polygon validation and does
  not replace a full OpenDRIVE or source-map topology audit.
- Alignment hypotheses are diagnostic only and require declared map-anchor
  provenance before any production decision.
- Top-N complete paths are not serialized; per-state alternatives and score
  margins are retained for the current diagnostic scope.
- Private nuScenes artifacts are not stored in the repository.
- The self-verification is exploratory and has not been promoted to an
  owner-approved evidence run or persisted as a formal acceptance artifact.

## Decision

The matcher is an auditable automated semantic-alignment diagnostic and reduces
manual review to emitted low-confidence intervals. CP1 remains scientific
status `PROVISIONAL`; baseline policy, actor selection, thresholds, map source,
canonical models and G3 policy are unchanged. Private scene-0061 sequence
evaluation is `SELF-VERIFIED/DIAGNOSTIC`; owner confirmation remains limited
to actor scope, unsupported ego dimensions, counterfactual-only reverse
direction and treatment of the five geometry/topology defects. CP1 remains
`PROVISIONAL` and acceptance is not claimed.
