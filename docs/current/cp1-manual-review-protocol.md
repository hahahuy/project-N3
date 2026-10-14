# CP1 Manual Corridor Review Protocol

## Purpose

This protocol governs manual review of the scoped `scene-0061` corridor. The
goal is to improve auditability and semantic correctness, not to optimize a
road-match percentage after seeing results.

## Immutable Baseline

```yaml
scene: scene-0061
map: singapore-onenorth
buffer_m: 40.0
topology_closure: one_hop_incident_connectivity
geometry_mode: line
resolution_m: 5.0
distance_tolerance_m: 0.5
heading_tolerance_rad: 0.2
actor_scope: ego plus automatic interaction selection
status: diagnostic/provisional
```

The baseline result is `20/143 = 13.99%`. It must remain in every comparison.

## Allowed Manual Work

1. Verify scene identity, source window, actor tokens, categories, state counts,
   timestamps and annotation dimensions.
2. Freeze an owner-approved actor set before scoring an exploratory run.
3. Review trajectory/lane/polygon overlays without removing failures.
4. Classify failures as source/track, frame/yaw, direction, lateral association,
   footprint, unsupported dimensions, off-map or geometry/join.
5. Verify selected corridor tokens, one-hop closure edges and boundary cuts.
6. Approve an external ego dimension envelope only when its source is documented;
   otherwise retain `unsupported` occupancy.
7. Run declared sensitivity comparisons and report all scopes together.

## Required Run Record

```yaml
run_id:
parent_baseline_run:
git_revision:
dataset_version: v1.0-trainval
map_sha256:
scene: scene-0061
source_window:
corridor_buffer_m: 40.0
selected_actor_ids:
actor_selection_method:
selection_rationale:
xodr_sha256:
road_match_config:
width_sources:
dimension_sources:
reviewer:
review_timestamp:
status: diagnostic/provisional
```

Actor IDs and rationale must be frozen before inspecting results. The automatic
selection baseline must not be replaced by a favorable manual set.

## Required Outputs

- complete actor candidate inventory and selection decisions;
- raw per-state match records;
- ranked candidate evidence;
- width and actor-dimension provenance;
- occupancy states separated into occupied, outside and unsupported;
- corridor token/edge manifest;
- map, XODR, code and configuration hashes;
- static overlay with actors, state indices, lanes, polygons and frame axes.

All trajectory-rich and derived artifacts remain under the private evidence root.

## Prohibited Shortcuts

- deleting failing states or actors after seeing scores;
- reversing lane direction only for failing actors;
- replacing rank-1 candidates in the production result;
- changing the `0.5 m`/`0.2 rad` baseline without a declared sensitivity run;
- guessing missing dimensions;
- mixing fallback-width and polygon-width occupancy counts;
- presenting esmini load success as road-match or CP1 acceptance;
- claiming G3, CP1 acceptance, scientific validity or CARLA compatibility.

## Current Decision

The corridor is structurally/runtime verified, but the baseline road-match is
`20/143 = 13.99%`. One actor is a reverse-direction candidate and two show
large lateral offsets. No production policy change is justified until those
findings are reviewed across additional approved evidence.

### Automated Review Reduction

The lane-sequence diagnostic has now been self-verified against the accessible
private scene-0061 corridor data. It evaluated all 143 selected-scope states and
reported 29 high-confidence, 49 low-confidence, 12 ambiguous, 44 topology-gap
and 9 direction-conflict classifications. Five non-positive centerline segments
were reported separately as geometry failures. A broad visual review of every
failed state is not required unless the owner disputes a specific interval or
source-data identity.

The self-verification remains exploratory and does not alter the immutable
baseline, actor-selection policy, lane-direction policy, tolerances or CP1
scientific status. See
`docs/reports/cp1-private-sequence-self-verification.md`.

## Owner Execution Guide

This section is the step-by-step procedure for completing the review and
producing the required private output bundle. Run commands from the repository
root. Do not commit anything under the private evidence root.

### Step 1: Prepare A Private Run Directory

Use a directory outside the repository:

```bash
export R2S_ROOT=$PROJECT_ROOT
export NUSCENES_ROOT=$NUSCENES_ROOT
export NUSCENES_VERSION=v1.0-trainval
export CP1_EVIDENCE_ROOT=$LOCAL_EVIDENCE_ROOT

mkdir -p "$CP1_EVIDENCE_ROOT"/{baseline,review,exploratory}
```

The directory must contain no raw dataset copy. It may contain aggregate JSON,
CSV, logs, hashes and private derived artifacts.

### Step 2: Record The Baseline Run Card

Create a file named:

```text
$CP1_EVIDENCE_ROOT/baseline/run-card.yaml
```

Copy the immutable baseline below and fill in the revision/hash fields before
reviewing any new result:

```yaml
run_id: scene-0061-baseline-40m-line-v1
parent_baseline_run: null
git_revision: "<output of git rev-parse HEAD>"
dataset_root: $NUSCENES_ROOT
dataset_version: v1.0-trainval
map_name: singapore-onenorth
map_sha256: "<sha256 of maps/expansion/singapore-onenorth.json>"
scene_name: scene-0061
scene_token: "<resolved scene token>"
source_window: "<first_sample_token>:<last_sample_token>"
corridor_buffer_m: 40.0
boundary_policy: intersect_closed_trajectory_buffer_centerline_selection
topology_closure: one_hop_incident_connectivity
geometry_mode: line
resolution_m: 5.0
road_match_distance_m: 0.5
road_match_heading_rad: 0.2
actor_selection_method: automatic interaction-selection-v1
selected_actor_ids: [ego, "<actor-1>", "<actor-2>", "<actor-3>"]
xodr_sha256: "<sha256 of private corridor XODR>"
width_source: polygon
dimension_source: annotation_or_unsupported
reviewer: "<name>"
review_timestamp: "<ISO-8601 timestamp>"
status: diagnostic/provisional
```

Useful commands for the identity fields:

```bash
git -C "$R2S_ROOT" rev-parse HEAD
sha256sum "$NUSCENES_ROOT/maps/expansion/singapore-onenorth.json"
sha256sum "$CP1_EVIDENCE_ROOT/baseline/scene-0061-corridor.xodr"
```

### Step 3: Build The Current Baseline Inventory

Before changing actor selection, create an inventory containing every vehicle
candidate in the scene. The inventory must include:

```text
actor_id
category
state_count
first_time_s
last_time_s
dimensions_width_m
dimensions_length_m
minimum_distance_to_ego_m
minimum_ttc_s
automatic_decision
automatic_decision_reason
```

Save it as:

```text
$CP1_EVIDENCE_ROOT/baseline/actor-inventory.json
```

The inventory is the source for any later manual selection. Do not create a
manual set by looking only at the current match percentage.

### Step 4: Review The Baseline Visually

For each baseline actor, inspect a static overlay or equivalent viewer showing:

- scene and coordinate-frame label;
- actor ID and state index;
- actor center and oriented footprint when dimensions exist;
- all 82 corridor centerlines;
- selected rank-1 through rank-3 candidates;
- lane polygons and width source;
- timestamps or sample tokens.

Record one classification for every failed state:

```text
source_or_track_issue
frame_or_yaw_issue
lateral_association
footprint_outside
unsupported_dimensions
off_map
geometry_or_join
uncertain
```

Save the classification table as:

```text
$CP1_EVIDENCE_ROOT/baseline/state-review.csv
```

Minimum columns:

```text
actor_id,state_index,source_record_token,classification,review_note,reviewer
```

Do not edit the production match result while doing this review.

### Step 5: Verify Actor Identity And Dimensions

For every selected actor, compare the canonical extracted data with the source
annotation records:

1. Confirm the instance token belongs to a vehicle category.
2. Confirm first/last annotation tokens and timestamps.
3. Confirm no unexpected track gap or identity switch exists.
4. Confirm `length_m` and `width_m` came from annotation size.
5. Confirm the ego dimension is unavailable unless an approved external source
   is recorded.

Write the result to:

```text
$CP1_EVIDENCE_ROOT/baseline/dimension-review.json
```

If a source-data error is found, document the correction and rerun the complete
baseline. Do not correct only a failing actor.

### Step 6: Freeze Any Manual Actor Set Before Scoring

If the review determines that the automatic selection is not the intended
interaction set, create a separate predeclared run card before running the
diagnostics:

```text
$CP1_EVIDENCE_ROOT/exploratory/manual-actor-run-card.yaml
```

It must include:

```yaml
run_id: scene-0061-manual-actors-<date>
parent_baseline_run: scene-0061-baseline-40m-line-v1
selected_actor_ids: [ego, "..."]
selection_rationale: "<semantic interaction rationale>"
selection_frozen_before_scoring: true
excluded_actor_ids: ["..."]
excluded_actor_reasons: {"actor-id": "<reason>"}
reviewer: "<name>"
```

Run the manual set as an additional comparison. Never replace or delete the
automatic baseline.

### Step 7: Check Direction Semantics

For the actor with the reverse-heading signal, review:

1. actor yaw from the source annotation;
2. motion heading from adjacent trajectory positions;
3. forward lane heading;
4. reverse lane heading;
5. lane polygon and neighboring directed lanes.

Record whether the evidence supports:

```text
lane_direction_mismatch
annotation_yaw_mismatch
true_reverse_travel
uncertain
```

Do not reverse the lane in the baseline. A direction policy change requires the
same evidence from more than one approved actor/scene and a separate decision.

### Step 8: Review Footprint Occupancy Separately

Keep these runs separate:

- polygon-derived effective widths;
- fallback constant widths;
- annotation dimensions;
- unsupported dimensions.

The occupancy diagnostic now records its effective distance/heading config.
Save the raw occupancy output as:

```text
$CP1_EVIDENCE_ROOT/baseline/occupancy-raw.json
```

Report counts separately:

```text
occupied
outside
unsupported
```

Do not combine counts from polygon and fallback runs. Do not assign guessed ego
dimensions.

### Step 9: Produce The Review Summary

Create:

```text
$CP1_EVIDENCE_ROOT/review/review-summary.md
```

Use this structure:

```markdown
# Scene-0061 Corridor Manual Review

## Baseline
- Run ID:
- Git revision:
- Selected actors:
- States:
- Raw match rate:
- XODR hash:

## Actor Decisions
| Actor | Decision | Evidence | Impact |
|---|---|---|---|

## State Failure Classes
| Class | Count | Notes |
|---|---:|---|

## Dimension/Width Review
- Polygon width source:
- Fallback width comparison:
- Unsupported dimensions:

## Direction Review
- Reverse candidates:
- Evidence strength:
- Production policy changed: no/yes

## Exploratory Runs
| Run ID | Frozen scope | Rate | Difference from baseline | Decision |
|---|---|---:|---:|---|

## Decision
- Baseline retained: yes/no
- CP1 corridor acceptance: not claimed
- Next technical action:

## Non-claims
- No G3 acceptance.
- No CARLA compatibility.
- No CP2/same-XOSC claim.
```

### Step 10: Final Handoff

The owner review is complete when the private evidence root contains:

```text
baseline/run-card.yaml
baseline/actor-inventory.json
baseline/state-review.csv
baseline/dimension-review.json
baseline/occupancy-raw.json
exploratory/*.yaml                 # only if manual runs were requested
review/review-summary.md
```

Send the following concise handoff back to the implementation session:

```text
CP1 manual review complete
Baseline run: <run_id>
Baseline retained: yes/no
Manual runs: <run IDs or none>
Actor identity corrections: <none or summary>
Direction finding: <summary>
Occupancy finding: <summary>
Raw evidence root: <private path>
Recommended next code change: <none or exact change>
```

The implementation session will then compare the review record against the
baseline, run tests, and make only explicitly justified code changes.

## Executable Checklist

Use this checklist in order. Do not skip the baseline run card or the actor
inventory.

The repository includes a setup helper for the first four files. Run it once:

```bash
cd "$PROJECT_ROOT"

.venv/bin/python scripts/setup_cp1_manual_review.py \
  --dataset-root "$NUSCENES_ROOT" \
  --dataset-version v1.0-trainval \
  --scene scene-0061 \
  --map-name singapore-onenorth \
  --buffer-m 40 \
  --output "$CP1_EVIDENCE_ROOT"
```

It creates a private bundle containing scene identity, the complete vehicle
candidate inventory, automatic selection decisions, a baseline run card, a
state-review CSV template and a review summary template. It does not copy raw
nuScenes data or generate repository artifacts.

### A. Create The Private Workspace

```bash
export R2S_ROOT=$PROJECT_ROOT
export NUSCENES_ROOT=$NUSCENES_ROOT
export CP1_EVIDENCE_ROOT=$LOCAL_EVIDENCE_ROOT

mkdir -p "$CP1_EVIDENCE_ROOT"/{baseline,review,exploratory}
git -C "$R2S_ROOT" status --short
git -C "$R2S_ROOT" rev-parse HEAD
"$R2S_ROOT/.venv/bin/python" -m pytest -q
```

For the standard setup, use:

```bash
export R2S_ROOT="$PROJECT_ROOT"
export NUSCENES_ROOT="$NUSCENES_ROOT"
export CP1_EVIDENCE_ROOT="$LOCAL_EVIDENCE_ROOT"
export CORRIDOR_EVIDENCE_ROOT="$LOCAL_CORRIDOR_EVIDENCE_ROOT"
```

The generated bundle should already contain:

```text
baseline/actor-inventory.json
baseline/scene-identity.json
baseline/run-card.yaml
review/README.md
review/state-review.csv
review/review-summary.md
```

If the test command is not green, stop the review and record the failure in
`review/review-summary.md`. Do not start a manual acceptance run from a failing
revision.

### B. Copy And Hash Existing Private Baseline Artifacts

```bash
cp $CORRIDOR_EVIDENCE_ROOT/scene-0061-corridor.xodr \
  "$CP1_EVIDENCE_ROOT/baseline/scene-0061-corridor.xodr"
cp $CORRIDOR_EVIDENCE_ROOT/corridor-manifest.json \
  "$CP1_EVIDENCE_ROOT/baseline/corridor-manifest.json"
sha256sum "$NUSCENES_ROOT/maps/expansion/singapore-onenorth.json" \
  > "$CP1_EVIDENCE_ROOT/baseline/map.sha256"
sha256sum "$CP1_EVIDENCE_ROOT/baseline/scene-0061-corridor.xodr" \
  > "$CP1_EVIDENCE_ROOT/baseline/xodr.sha256"
```

Fill `baseline/run-card.yaml` from the template in Step 2. The baseline actor
IDs must include `ego` and the three automatic interaction actors. The run card
must be completed before opening the review overlays.

### C. Resolve The Scene And Actor Inventory

Use the external dataset, not a possibly stale repository artifact. The source
window is the inclusive `scene-0061` first/last sample range from
`v1.0-trainval`. Record the following in
`baseline/actor-inventory.json` for every vehicle candidate:

```json
{
  "actor_id": "instance-token-or-ego",
  "category": "vehicle.car",
  "state_count": 39,
  "first_time_s": 0.0,
  "last_time_s": 19.1,
  "length_m": 4.5,
  "width_m": 1.8,
  "minimum_distance_m": 12.3,
  "minimum_ttc_s": null,
  "automatic_decision": "selected",
  "automatic_decision_reason": "distance_and_ttc"
}
```

For ego, use `null` dimensions unless an approved external envelope is
documented. For rejected actors, retain their rejection reason. Do not filter
the inventory to selected actors.

### D. Review The Overlay Before Scores

Create one private overlay per selected actor under:

```text
$CP1_EVIDENCE_ROOT/review/overlay-<actor-id>.png
```

Each overlay must show:

- global coordinate-frame label;
- actor ID and state index;
- actor center points and oriented footprint where dimensions exist;
- all corridor centerlines;
- rank-1, rank-2 and rank-3 candidates;
- lane polygons and width source;
- timestamps or source annotation tokens.

Record each image SHA-256 in `review/review-summary.md`. If a viewer cannot
show one of these layers, record the missing layer instead of implying it was
reviewed.

### E. Fill The State Review Table

Create `baseline/state-review.csv` with one row for every evaluated state,
including passing states:

```text
actor_id,state_index,source_record_token,classification,review_note,reviewer
ego,0,annotation-token,matched,"rank-1 candidate within baseline thresholds",name
instance-token,4,annotation-token,lateral_association,"centerline offset exceeds tolerance",name
```

Allowed classifications are exactly:

```text
matched
source_or_track_issue
frame_or_yaw_issue
direction_candidate
lateral_association
footprint_outside
unsupported_dimensions
off_map
geometry_or_join
uncertain
```

Do not delete rows. If a state is ambiguous, use `uncertain` and explain why.

### F. Freeze Any Exploratory Actor Set

If manual review concludes that the automatic selection is semantically wrong,
create `exploratory/manual-actor-run-card.yaml` before running it:

```yaml
run_id: scene-0061-manual-actors-YYYY-MM-DD
parent_baseline_run: scene-0061-baseline-40m-line-v1
selection_frozen_before_scoring: true
selected_actor_ids: [ego, instance-token-a]
excluded_actor_ids: [instance-token-b]
selection_rationale: "explicit interaction role documented from source review"
excluded_actor_reasons:
  instance-token-b: "not part of the reviewed interaction"
reviewer: owner
```

Run the exploratory scope in addition to the baseline. The final summary must
show both rates, state counts and actor lists side by side.

### G. Review Dimensions And Widths

Create `baseline/dimension-review.json`:

```json
{
  "actors": [
    {
      "actor_id": "ego",
      "dimension_source": "unavailable",
      "length_m": null,
      "width_m": null,
      "decision": "retain_unsupported"
    },
    {
      "actor_id": "instance-token",
      "dimension_source": "sample_annotation.size",
      "length_m": 4.5,
      "width_m": 1.8,
      "decision": "accepted"
    }
  ],
  "lane_width_run": "polygon-derived",
  "fallback_width_run_separate": true
}
```

Create `baseline/occupancy-raw.json` containing the occupancy report plus:

```json
{
  "road_match_config": {
    "max_distance_m": 0.5,
    "max_heading_error_rad": 0.2
  },
  "width_source": "polygon-derived",
  "dimension_policy": "annotation-or-unsupported"
}
```

Report `occupied`, `outside` and `unsupported` separately. Never merge this
with a fallback-width run.

### H. Review The Direction Candidate

For `instance-e3c...`, record one of these decisions in the summary:

```text
lane_direction_mismatch
annotation_yaw_mismatch
true_reverse_travel
uncertain
```

Support the decision with source yaw, motion heading, forward lane heading,
reverse lane heading and polygon context. Do not modify the baseline lane
direction. A policy change requires repeated evidence across approved actors or
scenes.

### I. Complete `review-summary.md`

Add these required sections to the template from Step 9:

```markdown
## Evidence Files
- Run card: baseline/run-card.yaml
- Actor inventory: baseline/actor-inventory.json
- State review: baseline/state-review.csv
- Dimension review: baseline/dimension-review.json
- Occupancy: baseline/occupancy-raw.json
- Overlays: review/overlay-*.png

## Hashes
- Source map:
- Corridor XODR:
- Git revision:

## Baseline Versus Exploratory
| Run | Actors | States | Matched | Rate | Status |
|---|---:|---:|---:|---:|---|

## Owner Decision
- Baseline retained: yes/no
- Source-data correction required: yes/no
- Production code change justified: yes/no
- Next action:
```

### J. Final Handoff Format

Return this exact summary to the implementation session:

```text
CP1 manual review complete
Baseline run: <run_id>
Baseline retained: yes/no
Exploratory runs: <run IDs or none>
State rows reviewed: <count>
Actor identity corrections: <none or summary>
Direction finding: <summary>
Occupancy finding: <occupied/outside/unsupported>
Evidence root: <private path>
Recommended production change: <none or exact change>
```

The implementation session will only modify production behavior if the handoff
documents a reproducible source-data or contract defect. A higher exploratory
percentage alone is never sufficient.
