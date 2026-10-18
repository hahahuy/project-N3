# Technical Contracts

## Multi-Dataset Platform Boundary

The current implementation is nuScenes-first, but the long-term platform
boundary should be dataset-agnostic after ingestion. A dataset adapter must
normalize:

- actor identity/category and dimensions;
- raw timestamps and source record tokens;
- ego pose and actor trajectories;
- coordinate frame and transform provenance;
- map/geometry source and confidence;
- sensor channels/calibration when sensor evaluation is requested;
- dataset license and artifact visibility metadata.

Dataset-specific assumptions belong in the adapter, not in the canonical
scenario, evaluator, gate or simulator interfaces. A future dataset may be
trajectory-only, map-only, or sensor-rich; unsupported capabilities must be
reported explicitly rather than approximated silently.

### Dataset Metadata Access

Repeated scene preparation must not rescan the full dataset metadata tables. The
contract is:

```yaml
metadata_index_version: nuscenes-metadata-index-v1
access: streaming_single_pass_then_cached
cache_visibility: local_private
cache_validation: source_table_size_and_mtime
preloaded_tables: accepted_by_extract_scenario
canonical_result_change: forbidden
```

The index may cache derived metadata records so that discovery and import are
incremental. It must not select different scenes, actors, timestamps, tolerances
or conventions than a full table read; a cached run and a direct table load must
produce the same canonical scenario. The cache is an engineering artifact, is
kept outside the repository and never becomes access control or scientific
evidence.

### nuScenes-devkit Source Measurements

The optional source adapter contract is `nuscenes-can-pose-v1`:

```yaml
source_adapter: real2scenario.nuscenes_backend.NuScenesSourceAdapter
can_message: pose
matching: nearest_timestamp
max_timestamp_gap_us: 100000
extrapolation: forbidden
ego_speed_precedence: can_then_finite_difference
missing_can: explicit_finite_difference_fallback
artifact_visibility: local_private
```

CAN is an ego measurement source, not a replacement for raw annotation or ego
pose ground truth. The canonical `State` schema remains unchanged in Phase 1;
acceleration and yaw rate are retained at the adapter boundary for later Tier 1
kinematic integration. Every extracted scenario records the adapter version,
CAN status and matched sample count in provenance. Synthetic fixtures and
scenes without `can_bus/` must remain reproducible through finite-difference
fallback.

### Phase 2 Source-State Extension

The versioned extension is `source-state-extension-v1`. It is adapter/Tier 1
data and is deliberately not part of canonical `State` or replay metrics.
It carries `timestamp_us`, `acceleration_mps2` and `yaw_rate_radps`, with
`can_pose_then_finite_difference` precedence and explicit fallback provenance.
`integrate_kinematic_open_loop()` consumes it at a fixed `0.05 s` timestep and
returns ordinary canonical `State` records plus source/simulator provenance.

### Native Map, LiDAR and Prediction Capabilities

`native_map_records()` and `road_ahead_query()` expose read-only devkit oracle
data under `nuscenes-native-map-query-v1` for the nine approved native layers;
they do not replace the OpenDRIVE builder or alter CP1 matching. The LiDAR
descriptor `nuscenes-lidar-payload-v1` requires `LIDAR_TOP`, timestamp,
calibration, source filename and decimation, and is always `local_private`.
Point-cloud bytes and derived payloads remain outside the repository.
`evaluate_prediction_advisory()` emits `nuscenes-prediction-advisory-v1` with
minADE/minFDE and `metric_role=advisory_prediction_only`; these values are not
combined with replay fidelity metrics or CP3 acceptance evidence.

## CP1 Map

- Source: nuScenes vector expansion, Singapore One-North.
- OpenDRIVE target: `1.6`, subset `r2s-odr-subset-v1`.
- Current builder prototype emits deterministic line segments.
- Immediate target: a declared scene-local corridor around `scene-0061` and
  selected actors, including topology closure and raw road-match diagnostics.
- Full Singapore One-North coverage is deferred future work.
- Required corridor work: line/arc fitting, connector junctions, polygon width,
  continuity and lane-level road-match.
- Generated map artifacts are local/private.
- Existing `straight-two-lane` remains regression/default until approved.

### Scene-Local Corridor Contract

```yaml
map_reconstruction_mode: local_nuscenes_corridor
source_map: singapore-onenorth
source_scene: scene-0061
crop_mode: trajectory_corridor
buffer_m: 30-50
boundary_policy: explicit_and_reported
topology_closure: required
road_match_status: PROVISIONAL
artifact_visibility: local_private
```

The corridor must not be cropped to force a trajectory match. Its manifest must
record selected lanes/connectors, buffer, boundary policy, topology closure and
raw road-match observations.

The first corridor implementation is `build_scene_local_corridor()` with a
fixed first-run buffer of `40 m`, closed centerline selection, one-hop incident
connectivity closure and no geometry clipping. External corridor evidence is
available for the first private run: 82 roads, 576 geometries, zero dangling
references and esmini exit 0. Corridor road-match was 20/143 (`13.99%`) with
`scientific_status=PROVISIONAL`; this remains engineering evidence, not CP1
acceptance.

Corridor attribution compared all 2,002 map centerlines with the 82 selected
corridor centerlines for 143 states and found identical nearest-lane assignments
for every state. The low corridor rate is therefore not a crop-selection
artifact; actor/centerline, direction and footprint semantics remain diagnostic
work.

The selected-actor counterfactual found one actor with 39/39 reverse-heading
rescues and two actors with large lateral offsets and no reverse rescue. This is
diagnostic evidence only; lane direction policy must not be changed globally
from a single actor/scene result.

The map-builder boundary must remain source-agnostic so future LiDAR-derived,
surveyed or independently licensed vector maps can provide normalized geometry,
frame, provenance, license and geometry-confidence metadata.

The CP1 arc-fitting implementation is dependency-free and synthetic-test
verified behind explicit `geometry_mode="line_arc"`. The default builder
behavior remains line-only. Arc output and residual manifests are engineering
prototype evidence until external map review, junctions, widths, continuity and
road-match are complete.

Connectivity continuity is currently an additive diagnostic report with raw
per-edge position/heading gaps and reciprocal-link failures. It does not change
OpenDRIVE topology or imply junction correctness or lane-level road-match.

Connector junction and polygon-width output is currently conservative and
synthetic-tested. Polygon widths now prefer the versioned
`polygon-cross-section-median-v1` estimator, with area-over-centerline and
constant-width fallbacks recorded separately. This is an additive CP1
diagnostic change; it does not alter the immutable road-match baseline or imply
lane-level acceptance. Full connector graph semantics and lane-level road-match
remain required before CP1 acceptance.

Lane road-match diagnostic version is `lane-road-match-v1`. Inputs are directed
centerline records and Scenario states in the same coordinate frame. Matching
uses deterministic nearest-segment projection, distance tolerance and wrapped
heading tolerance. Reports preserve raw state observations, per-actor rates,
overall rate and `scientific_status=PROVISIONAL`; no pass/fail or CP1 acceptance
is emitted.

The first scene-0061 matrix found exact equivalence between raw global and
rigidly transformed local centerline matching. Actor scope is therefore part of
every reported road-match claim: the 30-vehicle aggregate was 57.37%, while the
current four-actor interaction selection was 13.99%. Distance/occupancy and
nearest-candidate diagnostics must precede any threshold decision.

Occupancy and candidate diagnostics are additive versions
`lane-footprint-occupancy-v1` and `lane-road-candidates-v1`. They preserve the
legacy centerline result, distinguish unsupported dimensions/width from outside
occupancy, and retain width-source provenance. They do not establish lane
boundaries, collision safety, G3 or CP1 acceptance.

The current external generated XODR passes XML and the project lightweight
subset checks and loads in esmini after topology reference repair. The
independent audit reports zero dangling junction references and zero dangling
road links. Runtime load remains separate from full topology semantics, CARLA
compatibility and CP1 acceptance.

The first private One-North/scene-0061 run evaluated 767 states and matched 440
(`57.37%`). This is a diagnostic baseline only. It must not be converted into a
scientific pass/fail claim or hidden by changing tolerances without a documented
frame, actor-selection or lane-occupancy decision.

The lane-sequence diagnostic was subsequently self-verified against the accessible
private `v1.0-trainval` scene-0061 data and the declared 82-record, 40 m corridor.
It evaluated the same 143 selected-scope states without mutating the legacy
matcher. The exploratory classifications were 29 high-confidence, 49
low-confidence, 12 ambiguous, 44 topology-gap and 9 direction-conflict states;
five non-positive centerline segments were reported as geometry failures. These
results are diagnostic evidence only and are not a replacement for the
`20/143 = 13.99%` baseline or CP1 acceptance.

The follow-up repair contract is `centerline-repair-v1` with minimum retained
XY segment length `1e-6 m`. It removes consecutive duplicate samples
deterministically, records repaired source IDs, and explicitly excludes only a
path that remains collapsed after filtering. The private 40 m corridor rerun
inspected 82 records, repaired 12, excluded 0, and reported 576 retained
segments after repair. Explicit topology validation checked 80 selected-corridor
links with zero reciprocal-link, endpoint-gap or heading-discontinuity failures.
This is engineering diagnostic evidence and does not change the legacy matcher.

The additive semantic follow-up contracts are `actor-reference-sensitivity-v1`
and `direction-counterfactual-v1`. They compare only globally declared actor
reference hypotheses and preserve annotation, motion and lane headings per
state. Axle hypotheses require declared actor length; missing dimensions remain
unsupported. These diagnostics never mutate the canonical scenario, reverse a
production lane, change actor selection or alter matcher tolerances. Their
results are `diagnostic`/`PROVISIONAL` and cannot establish CP1 acceptance.

## CP2 XOSC

CARLA is a post-MVP backend under the superseding MVP scope decision. Current
MVP replay evidence uses esmini; the internal simulator is preview-only.

- OpenSCENARIO subset: `r2s-xosc-subset-v1`.
- Parser is fail-closed and must return structured unsupported errors.
- CP2 requires identical XOSC/XODR hashes for esmini and CARLA.
- CARLA may interpret the supported subset through an intermediate execution
  plan, but may not use canonical JSON as a substitute input.
- Initial scope: `replay_mode=waypoint`,
  `motion_mode=open_loop_transform_playback`.
- Unsupported behavior mode must not fall back to waypoint mode.

### WASM Parity Decision Note

The current Data Analysis result is that native esmini 3.9.0 ignores the
non-standard `Polyline/Vertex/@speed` extension. It must not be added to the
WASM parser as a parity feature. The exporter parity target is
`followingMode="position"`, pre-trigger actor hold, and
`AbsoluteTargetSpeed="0"` during initialization. Native esmini remains the only
source of official ADE/FDE and replay reports; WASM remains preview/correlation
only.

Any exporter change affecting these semantics requires native baseline
recomputation and a native-vs-WASM parity run before correlation claims.

### CP2-A Exact-Pose Planning

- Alignment artifact version: `carla-alignment-v1`.
- Blueprint mapping is explicit and fail-closed; no generic fallback blueprint.
- Replay grid uses deterministic source-time interpolation and shortest-path yaw.
- Exact-pose batches set `physics_enabled=false`, submit all actors together,
  and require one explicit tick after each batch.
- XOSC/XODR hashes are revalidated before execution planning/runtime.
- CP2-A pure/fake-runtime tests do not establish CARLA runtime or same-XOSC
  equivalence. The existing CARLA environment decision remains `DEFER`.

## Trace and Evidence

- Normalized trace schema: `normalized-replay-trace-v2`.
- CARLA runs must record world/map identity, hashes, adapter/subset versions,
  timestep, blueprint mapping, logs, trace and cleanup report.
- No CP2 claim without paired runtime evidence.

## U0 Authoring-Compatible Backend

Wave 3A extends the canonical variant model without changing raw recorded data.
The backend/API slice is complete; remaining MVP simulator and authoring work is
tracked in `docs/current/active-work.md`.

```text
parent Scenario (immutable)
  -> ActorMotionEdit / VariantConfig
  -> child variant preview
  -> G4/G5/G6/G7 diagnostics
  -> optional replay
```

The first backend edit mode is `parameterized` and may include:

- actor ID;
- speed multiplier;
- heading offset;
- initial gap delta;
- timing offset;
- seed.

`waypoint` editing is a later mode. `behavior` must return structured
`unsupported` until an executor exists; it must never fall back silently.

Required invariants:

- parent scenario remains immutable;
- child variant ID is deterministic from parent/config/version;
- raw recorded trajectory remains distinguishable from generated trajectory;
- canonical states must preserve `source_timestamp_us` and
  `source_record_token` through every coordinate-frame transform, and
  `/api/scenarios/{id}/trajectory` must expose both on every state. These are
  frame-independent provenance: `time_s` is relative to scenario start, so the
  source timestamp is the only link from replay time back to a nuScenes keyframe.
  Replayed (`path_kind: replayed`) states have no source provenance and report
  `null`. Losing this linkage is what previously made the recorded ego brake
  pedal channel permanently unavailable with
  `canonical_states_missing_source_timestamp_us`;
- provisional G6/G7 results remain diagnostic;
- all edits retain parent/config/seed/hash provenance;
- the backend must work with a synthetic fixture without CARLA.

The preview API may be implemented before CP1 map acceptance and CP2 CARLA
runtime. It must not change the canonical map source, same-XOSC contract,
license boundary or final scientific thresholds.

### MVP Physics Budget

The project distinguishes trajectory replay from feasibility preview and from
future controller/dynamics experiments:

```text
Tier 0: recorded/canonical scenario -> OpenSCENARIO -> esmini
        open-loop replay and ADE/FDE measurement

Tier 1: edited canonical scenario -> kinematic-open-loop-v1
        internal preview, G4/G5 feasibility and authoring interaction

Tier 2: optional controller/dynamics experiment
        post-MVP, separate mode, diagnostic only
```

Tier 0 is the measurement path. It must not be replaced by Tier 1 or Tier 2
when reporting replay fidelity. Tier 1 is the only physics-adjacent runtime
required for current MVP completion.

#### `kinematic-open-loop-v1`

- fixed timestep: `0.05 s`, matching the esmini comparison configuration;
- deterministic position, heading and velocity propagation;
- explicit acceleration, deceleration, jerk and yaw-rate limit checks;
- footprint collision pre-check with `unsupported` when dimensions are missing;
- no tire, suspension, powertrain, aerodynamic or rigid-body model;
- no silent trajectory clamping or correction;
- every violation or explicit projection includes state index, actor ID,
  observed value, limit and provenance;
- output trace is compatible with `normalized-replay-trace-v2`;
- reference-point convention is explicit and versioned, never inferred silently.

Tier 1 acceptance requires deterministic repeated runs, focused propagation and
collision tests, documented comparison against esmini on the same exported
scenario, zero silent clamps, no restricted artifacts and no new heavy runtime
dependency. Agreement with esmini is an engineering cross-check, not CP2
same-XOSC evidence.

The native C++20 Tier 1 port is available for engineering parity only. It uses
`dt=0.05`, while native esmini uses `dt=0.01`. The C++ WASM `/cpp-wasm` surface
is preview-only. WebGPU is limited to a capability probe and is not
implemented. DEC-018 remains binding: native esmini is the only sanctioned
source of ADE/FDE.

Tier 2 is not part of current MVP acceptance. If added later, it must declare a
separate replay/behavior mode, versioned parameters, capability status and
diagnostic metrics. It must not feed final ADE/FDE claims or silently fall back
to waypoint replay.

### Current Preview/Frame Boundary

The current Wave 3A preview generates and persists edited trajectory `State`
records for each actor. These are time-indexed canonical states and are exposed
through `PreviewResponse.paths` and the private preview `scenario.json` artifact.
They are not rendered sensor frames.

The current UI timeline changes the displayed time label while the SVG still
renders the complete recorded/generated polylines. The preview endpoint does
not yet generate or persist post-edit camera, LiDAR, radar, simulator image or
per-timestamp visual frame artifacts. It also does not expose a frame cursor or
frame retrieval API. Frame generation/sensor reprojection is therefore an open
post-U0 implementation item, separate from trajectory-state generation.

## Workspace Actor Timeline and Gate Lane Contracts

The Workspace gate lane and actor tracks are additive read-only contracts. They
consume canonical scenario evidence and never compute or infer gate outcomes in
the browser.

`workspace-actor-timeline-v1` returns one time-indexed track per actor with an
explicit availability block per channel:

```yaml
contract_version: workspace-actor-timeline-v1
time_domain: {start_s: float, end_s: float}
channels:
  position: canonical-state-v1
  heading: canonical-state-v1
  speed: canonical-state-v1
  acceleration: workspace-finite-difference-acceleration-v1
  braking: nuscenes-can-vehicle-monitor-v1
```

- Position, heading and speed are canonical `State` values.
- Acceleration is a declared deterministic derivative of the canonical speed
  series. It is labelled `finite_difference`, is never clamped, and requires at
  least two strictly increasing timestamps; otherwise the channel reports
  `insufficient_states_for_finite_difference`.
- Braking is the recorded nuScenes CAN `vehicle_monitor.brake` pedal channel and
  exists for the ego actor only. Non-ego tracks report
  `recorded_brake_channel_records_ego_only`, and the channel reports
  `scenario_provenance_declares_no_can_scene`, `dataset_not_configured`,
  `canonical_states_missing_source_timestamp_us` or
  `recorded_brake_channel_absent_for_source_scene` when it cannot be resolved.
- Pedal samples are matched by nearest recorded timestamp with a fixed
  `100000 us` gap. Unmatched timestamps are `null`, which the browser renders as
  `n/a`; a missing channel is never rendered as zero.
- The contract carries no scientific claim. It does not change `State`,
  `source-state-extension-v1`, CP1, or any threshold.

`workspace-gate-timeline-v1` projects G1-G7 onto the scenario time domain:

```yaml
contract_version: workspace-gate-timeline-v1
gates:
  - {gate_id: G1, status: unsupported | skipped | pass | fail | error,
     scientific_status: string, reasons: [string], start_s: float, end_s: float,
     extent_source: scenario_time_domain | declared_main_event_window}
```

- The segment status vocabulary adds `unsupported` to the CP4 gate vocabulary
  for a capability this surface does not evaluate. `unsupported` is never `pass`.
- G1 and G2 are `unsupported` here because the Workspace surface does not
  evaluate the OpenSCENARIO subset or record a simulator run for the canonical
  scenario. G3 is `skipped` because no lane road-match evidence is supplied to
  this surface; CP1 evidence remains a separate flow.
- G4, G5, G6 and G7 reuse the CP4 implementations and therefore reuse their
  statuses, reasons, observed values and `PROVISIONAL` scientific status.
- Extents are the scenario time domain unless G5 records a declared main event
  window, which is then used verbatim. No gate receives an invented window.

## Simulator Frame Contract

The additive `simulator-frame-v1` contract is the first supported POV frame
boundary. The internal `kinematic-open-loop-v1` renderer selects the nearest
canonical actor state to the requested Workspace playhead and returns a
transform-backed frame, not an image placeholder. Each frame includes simulator
identity/version, mode (`third-person` or `in-car`), timestamp, coordinate and
transform versions, camera and actor transforms, and local-private provenance.
The browser may render these transforms as a POV scene only when the capability
block is available. esmini-rendered image frames and CARLA same-XOSC remain
separate capabilities; CARLA remains post-MVP.

### POV image artifact boundary

`workspace-pov-image-v1` is separate from `simulator-frame-v1`. The image route
returns `rendered` only when a private esmini capture manifest names an existing
image artifact, mode, timestamp and simulator provenance. If no real capture
exists it returns `unavailable` with `esmini_image_capture_artifact_unavailable`.
The internal browser transform renderer is not an image artifact and must not be
described as one. CARLA same-XOSC remains out of scope.

`workspace-variant-sensor-v1` similarly reports post-edit sensor frames as
`unsupported` until actual calibrated frame generation exists. A recorded parent
LiDAR sweep is a separate fallback and never a generated variant frame.

## nuScenes Devkit Evidence Adapter Contract

The official nuScenes devkit is the semantic authority for recorded sensor,
annotation, map and CAN interpretation. The backend must use a cached dataset
adapter rather than reload metadata tables or reimplement transforms per request.
The approved implementation and optimization order are defined in
`docs/current/nuscenes-devkit-optimization-decision.md`.

The `nuscenes-sensor-evidence-v1` surface may include multisweep `LIDAR_TOP`,
map, annotation and telemetry layers, but every layer must retain source tokens,
timestamps, coordinate/transform versions, availability and local-private
provenance. Historical sweeps are not instantaneous generated sensor output.
CAN telemetry does not replace nuScenes `ego_pose` for spatial placement.

## Live Esmini Adapter Contract

The approved live 3D architecture uses esmini as a native authoritative simulation
adapter and a browser-native renderer for presentation. The browser must not depend
on a stream of esmini screenshots for normal editing or timeline interaction.

```text
React + Three.js/PlayCanvas
  <-> WebSocket state/control transport
  <-> bounded native esminiLib session
        -> OpenSCENARIO/OpenDRIVE/OSI state
```

The adapter session is responsible for loading a validated XOSC/XODR pair, stepping
with an explicit timestep, pause/resume/reset semantics, validated actor/control
commands, camera state, object transforms, scenario time and capability metadata.
The browser renderer is responsible for road/actor meshes, camera presentation,
interpolation, trajectories and sensor overlays. A state frame from this adapter is
not an image artifact.

Every live session must identify at least:

- esmini/esminiLib version and adapter version;
- XOSC and XODR content hashes;
- simulation time, timestep and coordinate/transform versions;
- session id, scenario id and authoritative state source;
- supported commands and rendering/sensor capabilities;
- explicit `running`, `paused`, `reset`, `unavailable` or `failed` status.

The existing `workspace-pov-image-v1` route remains the image/evidence contract.
It may use esmini off-screen capture and private manifests, but it is separate from
the live state transport. A browser transform renderer remains an internal preview
when the native adapter is unavailable. CARLA same-XOSC remains post-MVP.

The first implementation may use JSON over WebSocket or an equivalent polling
transport behind the same typed contract. Binary state encoding, WebRTC data/video,
Unity WebGL and direct esmini WebAssembly are future optimizations, not prerequisites.

The implemented service exposes `GET /api/esmini/live/capability`, bounded session
creation under `/api/esmini/live/sessions`, validated command POSTs, state polling,
and `/stream` as a WebSocket-friendly JSON transport. It confines XOSC/XODR paths
to the project root and records SHA-256 hashes before loading. A session without a
configured version-compatible native binding is `unavailable`; it may expose its
identity and command vocabulary, but it does not synthesize object state from the
kinematic preview. The current ctypes seam intentionally fails closed when the
installed library does not expose the required ABI, so an operator must provide a
version-compatible binding before native execution can be claimed.

## CP3 Replay and Gate Reporting

- Variant and batch reports may include per-actor replay metrics and ADE/FDE
  distributions.
- Missing FDE values are excluded from the FDE distribution and remain
  `null`/`n/a`, never zero.
- Batch variants expose G4/G5/G6/G7 diagnostics without changing status
  reconciliation. G6/G7 retain `scientific_status=PROVISIONAL`.

The `benchmark-aggregate-v1` contract aggregates completed scene reports in
deterministic scene order while keeping `synthetic`, `nuscenes_local` and other
local evidence classes separate from simulator classes. It reports provisional
ADE/FDE and G1-G7 counts without recording host paths or copying trajectory
artifacts. The five-scene run exists as provisional engineering evidence, but
owner approval of the scene index, final benchmark protocol and scientific
policy remain required before CP3 acceptance.

An agent-selected five-scene metadata index may be used for engineering
preparation without changing the approval boundary. The selected index is
`agent-selected/provisional`; timeout or preparation failure must not be
reported as a scene metric or benchmark result.

### CP4 Gate Evidence

Gates report state only from explicit, validated evidence. The API payload is
the canonical domain evidence record; there is no second, looser shape:

```yaml
g3_evidence_version: lane-road-match-evidence-v1
g3_evidence_scope: single_candidate_by_variant_id
g3_minimum_match_rate: 0.95   # fixed, not caller-supplied
g3_missing_evidence: skipped(road_match_unavailable)
g5_event_source: operator_declared
g5_undeclared_event: skipped(event_definition_not_declared)
g5_malformed_declaration: error
```

```yaml
lane_road_match_evidence:
  evidence_version: lane-road-match-evidence-v1
  scenario_id: <candidate variant_id>
  coordinate_frame: local_road_aligned
  algorithm_version: lane-road-match-v1
  config: {max_distance_m: 0.5, max_heading_error_rad: 0.2}
  overall:
    state_count: int
    matched_state_count: int
    raw_match_rate: float
    provisional_95_status: at_or_above_95_percent | below_95_percent
  diagnostic_status: diagnostic
  scientific_status: PROVISIONAL
```

Candidate road-match evidence is produced by
`scripts/archive/cp1/build_benchmark_gate_evidence.py`, which builds the declared
scene-local corridor, expresses it in the candidates' frame and measures every
candidate with the unchanged tolerances. Supplying evidence must not change
generation, validation, replay or metric values.

- A gate may never pass because evidence is absent, inferred or repaired.
- Evidence applies only to the candidate it is declared for; missing evidence
  keeps that candidate skipped rather than generalising to the batch.
- Evidence that claims another candidate's identity fails closed.
- Event metadata is validated before use and recorded with its source; it is
  never detected from the trajectory and never treated as ground truth.
- Gate status semantics: `pass`, `fail`, `skipped` for a capability that was not
  declared, `error` for supplied evidence that could not be used.
- Evidence provenance is carried into the variant artifact so a report and its
  gate results always agree.

## CP5 Reproducibility and Release Evidence

```yaml
manifest_version: reproducibility-manifest-v1
manifest_scope: project_relative_artifact_inventory
release_evidence_version: release-evidence-v1
release_evidence_mode: clean_git_archive_checkout | working_tree_snapshot_checkout
host_paths_in_manifest: forbidden
lockfile: requirements.lock.txt
sign_off: pending_owner
```

- A run manifest inventories artifacts by relative POSIX path with size and
  SHA-256 plus a hashed configuration block; absolute dataset, evidence and
  simulator paths are caller metadata and never artifact identifiers.
- A run records whether its working tree was clean; a dirty tree must not be
  presented as a release candidate.
- Clean-checkout verification runs the documented verification commands against
  an exported copy of the committed tree and scans it for restricted dataset
  content and committed host paths.
- Release evidence is engineering evidence. It does not certify scientific
  results and it does not substitute for owner sign-off.
