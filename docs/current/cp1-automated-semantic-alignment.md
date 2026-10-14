# CP1 Automated Semantic Road Alignment

Status: `RECOMMENDED NEXT EXPERIMENT`  
Updated: 2026-10-13

## Problem

The current CP1 matcher in `src/real2scenario/road_match.py` assigns each
trajectory state independently to the nearest centerline segment. This is a
useful diagnostic, but it is not a semantic lane matcher. It can select the
wrong parallel lane, switch lanes at a junction, reject a valid point because
of a small polygon/coordinate residual, or select a lane whose direction is
inconsistent with the actor's motion.

The current scene-0061 evidence demonstrates this limitation:

```text
all vehicles:              57.37% raw match
selected interaction set:  13.99% raw match
corridor:                  20/143 states matched
```

The next step should not be blind tolerance tuning or a full manual review of
all 143 states. Implement an automated semantic matcher that reasons over the
whole actor track and returns confidence/ambiguity evidence. Manual review
should be limited to the small set of low-confidence intervals that the
algorithm cannot resolve.

## Recommended Solution

Implement a lane-level Hidden Markov Model (HMM) with Viterbi decoding. This is
the standard map-matching pattern described by Newson and Krumm,
*Hidden Markov Map Matching Through Noise and Sparseness*, ACM GIS 2009. Use
the current centerline candidates as emissions and add lane topology,
longitudinal progress, heading and polygon evidence as transition/emission
features.

Primary references:

- Newson and Krumm, *Hidden Markov Map Matching Through Noise and Sparseness*:
  <https://www.microsoft.com/en-us/research/publication/hidden-markov-map-matching-through-noisy-position-data/>
- nuScenes devkit and map expansion:
  <https://github.com/nutonomy/nuscenes-devkit>
- Argoverse lane-segment map representation:
  <https://github.com/argoverse/argoverse-api>
- Lanelet2 routing and lane semantics:
  <https://github.com/fzi-forschungszentrum-informatik/Lanelet2>
- CommonRoad Scenario Designer OpenDRIVE/Lanelet conversion and validation:
  <https://commonroad-scenario-designer.readthedocs.io/en/latest/>

Do not add Lanelet2, Argoverse or CommonRoad as a new runtime dependency for
the first implementation. Reuse their lane-graph concepts in the existing
Python domain model. External tools may be used later as independent
cross-checks.

## Canonical Lane Graph

Before matching, normalize generated lane records into a directed graph. Each
lane/connector must have:

- stable lane ID and source record ID;
- sampled centerline poses;
- cumulative arc length `s`;
- tangent heading at each sample;
- polygon or left/right bounds when available;
- width and width source;
- predecessor IDs;
- successor IDs;
- legal lane-change neighbor IDs, if known;
- junction/connector metadata;
- direction-normalized travel heading.

The existing `LaneCenterlineRecord` can remain the public input for the first
step, but the matcher needs a separate graph structure. Do not infer
predecessor/successor relations solely from nearest geometry at match time.
Use the OpenDRIVE road/lane/section/link data already available during map
building and preserve source IDs in the graph.

Important OpenDRIVE detail: road reference-line direction and lane ID sign do
not by themselves define the actor's legal travel direction. Normalize each
lane's direction from explicit lane links and connector semantics. Keep the
reverse direction as an analysis candidate, not as an automatic production
policy.

## Candidate Generation

For every actor state, retain multiple candidates instead of only rank 1.
Reuse or extend `diagnose_nearest_lane_candidates()`.

Candidate generation should:

1. Query centerline segments within a configurable radius.
2. Query lanes whose polygon contains the point or is within a small buffer.
3. Include neighboring lanes near lane boundaries.
4. Retain the best `K` candidates, initially `K=5`.
5. Keep candidates that fail one feature so the temporal decoder can recover
   from local map noise.
6. Record the following per candidate:
   - Euclidean distance to projected centerline;
   - signed lateral offset;
   - projected longitudinal `s`;
   - actor-vs-lane heading error;
   - motion heading error;
   - polygon containment;
   - distance to polygon boundary;
   - lane direction and reverse-direction status;
   - candidate rank.

Do not discard every outside-polygon candidate. A source pose can be just
outside a reconstructed polygon because of map error, box reference point or
sampling noise. Mark it as evidence and penalize it instead.

Use two headings:

- `annotation_yaw`: the recorded actor orientation;
- `motion_heading`: heading from adjacent trajectory positions.

This distinguishes an annotation yaw problem from a true reverse-motion or
lane-direction problem. At the first/last state, use the nearest valid finite
difference or mark motion heading unavailable.

## HMM Scoring

Let `l_t` be the selected lane candidate at state `t`.

### Emission cost

Start with a documented weighted cost:

```text
emission(l_t) =
    w_distance * lateral_distance^2
  + w_annotation_heading * annotation_heading_error^2
  + w_motion_heading * motion_heading_error^2
  + w_outside * outside_polygon_penalty
  + w_boundary * boundary_distance_penalty
```

Use configurable noise scales rather than hard-coding one universal threshold.
Keep the current baseline thresholds (`0.5 m`, `0.2 rad`) as a separate
comparison, not as the HMM's only decision rule.

### Transition cost

For candidates `l_t` and `l_(t+1)`:

```text
transition =
    INF                                  if graph transition is impossible
    + route_distance_residual
    + speed/progress residual
    + lane-change penalty
    + reverse-direction penalty
    + junction/connector penalty
```

Allow only declared transitions:

- same lane;
- explicit successor;
- explicit legal lane change;
- explicit connector transition;
- optional unknown transition when the map has a declared topology gap.

Do not connect arbitrary nearest lanes across an intersection. That is the
main semantic failure that independent nearest-lane assignment cannot detect.

For consecutive source states, compare:

- observed displacement;
- observed speed multiplied by `dt`;
- candidate arc-length change;
- direction of candidate travel.

This identifies tracks that are geometrically near a lane but cannot have
traveled along that lane between timestamps.

### Viterbi output

Return the best path, alternatives and confidence. At minimum, expose:

- best lane ID per state;
- top `N` paths or top `N` candidates per state;
- best-vs-second-best score margin;
- normalized confidence/posterior where available;
- ambiguous intervals;
- topology violations;
- unmatched states;
- lateral and heading residuals.

The matcher must not turn a low-confidence result into a production match.
Use explicit statuses such as:

```text
matched_high_confidence
matched_low_confidence
ambiguous_lane
unmatched_geometry
unmatched_topology
direction_conflict
outside_polygon
unsupported_width
```

## Automated Failure Triage

Run this triage before requesting manual review.

### 1. Frame/alignment test

Evaluate a small declared transform family around the current transform:

- translation offsets in x/y;
- yaw offset;
- optional global reflection/reverse-heading analysis only;
- no production mutation.

For each hypothesis, report track-level HMM score and residual. If one stable
transform improves all actors, the problem is likely frame alignment. If only
one actor improves, it is likely track identity, actor origin or map semantics.

Do not select the best transform merely because it maximizes the scene score.
The transform must be supported by declared map anchors and provenance.

### 2. Direction test

Compare annotation yaw, motion heading, forward lane heading and reverse lane
heading. Classify automatically:

- `annotation_yaw_mismatch`;
- `motion_reverse_of_lane`;
- `lane_direction_candidate`;
- `consistent_heading`;
- `heading_uncertain`.

Keep reverse-lane matching as a counterfactual diagnostic. Do not change the
production direction policy from one actor or one scene.

### 3. Lane-association test

Compare independent nearest-lane and HMM lane sequences. Report:

- states where rank 1 changes;
- states where HMM chooses rank 2/3;
- lane switches without graph support;
- graph-supported lane switches;
- score margin at each switch.

If HMM resolves the track with low residual and legal transitions while rank 1
fails, classify the issue as `lane_association`, not map geometry failure.

### 4. Geometry test

Before blaming the trajectory, validate every generated lane:

- centerline has finite coordinates and positive length;
- sample spacing has no large gaps;
- polygon is valid and has positive area;
- centerline lies mostly within its polygon;
- width is in a declared range;
- predecessor/successor IDs exist;
- linked lane endpoints are spatially close;
- linked lane headings are compatible;
- junction links do not teleport across the map.

Report geometry residuals independently from actor match rates.

### 5. Footprint test

Keep separate states for:

- center point match;
- polygon containment;
- annotation-dimension occupancy;
- fallback-width occupancy;
- unsupported dimensions.

Never let missing dimensions become a failed semantic lane match. An actor can
be centerline-aligned while occupancy remains `unsupported`.

## Proposed Data Contracts

Add new diagnostic contracts beside the current road-match contracts rather
than changing the meaning of `LaneRoadMatchReport`.

```python
@dataclass(frozen=True, slots=True)
class LaneSequenceMatchConfig:
    candidate_radius_m: float = 8.0
    max_candidates: int = 5
    position_sigma_m: float = 1.0
    heading_sigma_rad: float = 0.35
    outside_polygon_penalty: float = 4.0
    lane_change_penalty: float = 2.0
    reverse_direction_penalty: float = 8.0
    topology_gap_penalty: float = 12.0
```

The exact values must be configuration and sensitivity outputs, not hidden
constants.

Each per-state result should contain:

```text
actor_id
state_index
source_timestamp/token
best_lane_id
best_candidate_rank
projected_s
signed_lateral_offset_m
annotation_heading_error_rad
motion_heading_error_rad
inside_polygon
best_score
second_best_score
confidence/margin
status
```

Each per-track result should contain:

```text
matched_state_count
high_confidence_state_count
low_confidence_state_count
ambiguous_state_count
unmatched_state_count
mean_lateral_error_m
p95_lateral_error_m
max_heading_error_rad
topology_violation_count
lane_switch_count
unsupported_occupancy_count
```

Preserve `diagnostic_status="diagnostic"` and
`scientific_status="PROVISIONAL"`. Do not reinterpret the current provisional
95% threshold until this algorithm has been validated on approved scenes.

## Replacement for Full Manual Review

The automated workflow should be:

1. Freeze the existing scene-0061 baseline unchanged.
2. Build the canonical lane graph and run geometry validation.
3. Generate top-5 candidates for every state and every vehicle scope.
4. Run HMM/Viterbi matching independently for:
   - ego;
   - selected interaction actors;
   - all vehicles.
5. Run direction and transform counterfactuals as analysis only.
6. Produce per-actor and per-state confidence diagnostics.
7. Automatically route only these cases to manual review:
   - low score margin;
   - unresolved topology transition;
   - persistent high lateral residual;
   - conflicting annotation/motion heading;
   - geometry validation failure;
   - transform hypothesis disagreement.
8. Review a small overlay set for those intervals only.
9. Keep the baseline and all automated exploratory runs side by side.

This changes manual review from “inspect every failed state” to “inspect only
states where the automated evidence is genuinely ambiguous.” It does not make
the result scientifically accepted automatically.

## Practical First Experiment

Implement a synthetic-only HMM proof first:

- straight two-lane road;
- curved lane;
- parallel lanes;
- legal lane change;
- junction connector;
- reversed heading counterfactual;
- one point with lateral noise;
- one point outside polygon;
- one missing topology link.

Expected assertions:

- nearest-lane can switch incorrectly, HMM remains on the valid sequence;
- legal lane changes are accepted;
- unsupported lane changes are penalized/rejected;
- reverse heading is surfaced as a diagnostic candidate;
- one noisy point does not break the whole track;
- missing geometry produces `unmatched_topology`, not a fabricated match;
- confidence decreases at ambiguous junctions.

Then run the same matcher against the private scene-0061 corridor and report
the baseline `20/143` alongside:

- independent nearest-lane result;
- HMM best-path result;
- high-confidence-only result;
- low-confidence/ambiguous fraction;
- topology violations;
- geometry validation failures;
- direction counterfactual result.

## Scope and Non-Claims

This approach does not prove that the generated map is a faithful reconstruction
of Singapore One-North. It separates:

- map geometry quality;
- lane graph topology quality;
- trajectory-to-lane association;
- actor footprint occupancy;
- source track/heading quality.

Do not change the CP1 provisional 95% reference, actor selection policy or lane
direction policy based only on a higher HMM score. A higher score is useful
diagnostic evidence, not acceptance.

Do not make the full CP1 test suite depend on private nuScenes data or external
GIS packages. The core matcher must be deterministic and testable with the
existing synthetic lane records.

## Recommended Implementation Order

1. Add a directed lane graph data structure and graph validation diagnostics.
2. Add motion-heading and candidate feature extraction.
3. Add deterministic candidate generation with top-`K` evidence.
4. Add Viterbi sequence decoding with configurable costs.
5. Add confidence, alternative paths and failure classifications.
6. Add synthetic tests for topology, noise, lane changes and reverse heading.
7. Add private scene-0061 report generation without changing baseline scoring.
8. Replace broad manual review with low-confidence interval review.
9. Reassess production policy only after multiple approved scenes.

## Follow-Up Result

The source-level follow-up added `centerline-repair-v1` and explicit
`lane-topology-validation-v1` diagnostics. Duplicate consecutive centerline
samples are removed deterministically with source provenance; collapsed paths
are explicitly excluded rather than silently deleted. The private 40 m corridor
run inspected 82 records, repaired 12, excluded 0, and left zero geometry
validation failures. Explicit topology validation checked 80 corridor links
with zero reciprocal, endpoint or heading failures.

The repaired selected-scope rerun remains diagnostic:

```text
high confidence:       29
low confidence:        93
ambiguous:              10
topology gap:            0
direction conflict:     11
geometry failures:       0
```

The five geometry defects were removed without changing road-match tolerances,
actor selection, source trajectory data or lane-direction policy. Remaining
lateral residuals and direction findings still require policy confirmation and
do not establish CP1 acceptance. See
`docs/reports/cp1-geometry-topology-follow-up.md`.
