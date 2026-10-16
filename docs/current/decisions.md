# Decision Log

This file is append-only. New decisions supersede old ones explicitly; do not
rewrite historical entries.

## DEC-001 — Plan A Baseline

- Status: `APPROVED BASELINE; MVP ACCEPTANCE SUPERSEDED BY DEC-011`
- Plan A: `MVP&ProjectSummary.md`.
- Both esmini and CARLA remain long-term project targets. Current MVP
  acceptance is governed by DEC-011.

## DEC-002 — CP2 Same-XOSC

- Status: `APPROVED`
- The same `.xosc` bytes/hash and declared companion map/XODR hashes must be
  consumed by esmini and CARLA for CP2.
- A direct canonical JSON to CARLA path is feasibility-only, not CP2 evidence.

## DEC-003 — Dataset and Map Area

- Status: `APPROVED WORKING SCOPE`
- Map area: Singapore One-North.
- `scene-0061` is the CP0-CP2 smoke/regression scene.
- Final 5-10 scene benchmark index remains open for owner approval.

## DEC-004 — Metrics and Provisional Gates

- Status: `APPROVED WORKING CONTRACT`
- Raw annotation/ego pose keyframes are ground truth.
- ADE/FDE thresholds remain provisional.
- G6/G7 temporary funnels are allowed for development only.

## DEC-005 — Artifact Boundary

- Status: `APPROVED`
- Source code uses Apache-2.0.
- Raw nuScenes and nuScenes-derived `.xodr`, `.xosc`, trajectories, replay
  traces and visual artifacts remain local/private.

## DEC-006 — OSM Role

- Status: `DEFERRED PROPOSAL / NOT ACTIVE MAKEOVER SCOPE`
- OSM is an auxiliary alignment/reference/visualization layer.
- nuScenes vector map remains the canonical CP1 map source.
- OSM-derived CARLA worlds are feasibility-only unless a future decision says
  otherwise.
- This remains a deferred proposal and is not part of the active nuScenes-devkit
  backend makeover.

## DEC-007 — Execution Order and Backend Boundary

- Status: `HISTORICAL EXECUTION ORDER; MVP BACKEND SCOPE SUPERSEDED BY DEC-011`
- Next section: Wave 3A U0 authoring-compatible backend.
- Then: CP1 map builder/road-match, CP2 same-XOSC CARLA execution, and only
  after those backend contracts stabilize, full UI/sensor/POV authoring.
- Wave 3A may use synthetic or approved local artifacts and does not wait for
  CARLA same-XOSC runtime evidence.
- Full UI must consume backend contracts; it must not duplicate domain rules or
  mutate canonical recorded scenarios.
- This decision does not alter Plan A scope, CP2 same-XOSC, license boundaries,
  or scientific threshold status.

DEC-011 supersedes the simulator acceptance order above: CARLA execution is
post-MVP, while esmini and the internal kinematic preview are the current MVP
execution backends.

## DEC-008 — Scene-Local CP1 Corridor

- Status: `APPROVED WORKING SCOPE`
- Immediate CP1 target is a local corridor around `scene-0061`, selected actors
  and an explicitly declared buffer/topology closure.
- Full Singapore One-North OpenDRIVE coverage is deferred future work.
- The corridor must report raw geometry, continuity and road-match observations
  and must not crop geometry to force a match.

## DEC-009 — Future Map and LiDAR Source Abstraction

- Status: `APPROVED ARCHITECTURE DIRECTION`
- The map-builder boundary must support a normalized map/geometry provider.
- Future LiDAR-derived or independently licensed map sources may be added with
  source frame, provenance, license and geometry-confidence metadata.
- No future source is active for CP1 until its adapter and artifact policy are
  separately reviewed.

## DEC-010 — Late-Future Multi-Dataset Platform

- Status: `APPROVED FUTURE DIRECTION`
- Current MVP remains nuScenes-first with esmini and the internal kinematic
  preview; CARLA is post-MVP under DEC-011.
- After CP1/CP2/CP5 stabilization, add one second dataset adapter; Waymo Open
  Motion is the default candidate for trajectory/canonical validation subject to
  package and license review.
- Choose nuPlan instead only if planning/ego behavior becomes the approved
  research direction. Treat ScenarioNet as a representation/ecosystem unless a
  specific source dataset is selected.
- Do not add multiple datasets or simulators to current acceptance scope.

## DEC-011 — Superseding MVP Simulator Scope

- Status: `APPROVED SUPERSEDING SCOPE`
- CARLA moves from current MVP acceptance to post-MVP.
- Current MVP execution backends are esmini for fidelity evidence and an
  internal lightweight kinematic simulator for authoring/preview.
- Post-MVP CARLA retains the same-XOSC contract and is evaluated separately.

## DEC-012 — MVP Dynamic Object Authoring

- Status: `APPROVED MVP EXPANSION`
- Editable objects include vehicles, pedestrians, cyclists, trajectory-bearing
  actors and movable static objects such as cones/barriers.
- MVP supports instantaneous velocity and segment/trajectory edits.
- Initial direction controls are heading offset and direction vector.
- Drag waypoint and snap-to-lane are later modes.
- Propagation modes are explicit and configurable; behavior remains separate.
- Invalid variants may be saved for debugging but cannot be ranked as valid.

## DEC-013 — MVP Internal Simulator and POV

- Status: `APPROVED MVP EXPANSION`
- Internal simulator is a fixed-timestep kinematic preview engine, not a physics
  engine, autonomy stack or behavior-fidelity claim.
- It supports position, heading, velocity propagation and collision pre-checks.
- MVP POV includes browser 2D/3D, follow/orbit/timeline controls and vectors.
- Recorded LiDAR point clouds may be shown as evidence with source provenance;
  they are not regenerated sensor output or annotation replacement.
- The full 2D/3D authoring workspace is current MVP work. U0 is only the
  showcase checkpoint and does not satisfy the full workspace requirement.
- The workspace must consume the internal simulator/preview trace and preserve
  recorded, generated, replayed and sensor-evidence layers separately.

## DEC-014 — MVP Physics Budget and Runtime Separation

- Status: `APPROVED MVP IMPLEMENTATION POLICY`
- The MVP uses three explicitly separated runtime tiers:
  - Tier 0: kinematic OpenSCENARIO/esmini replay for trajectory-fidelity
    measurement. It is the ADE/FDE measurement instrument and remains open-loop.
  - Tier 1: a dependency-light fixed-timestep internal kinematic preview for
    variant feasibility, G4/G5 checks, collision pre-checks and authoring UI.
  - Tier 2: optional dynamics-adjacent/controller experiments such as
    longitudinal following or bicycle-model lateral propagation, post-MVP and
    diagnostic only.
- Tier 1 uses a versioned profile, initially `kinematic-open-loop-v1`, with a
  fixed timestep of `0.05 s`, explicit acceleration/deceleration/jerk/yaw-rate
  limits and explicit footprint capability status.
- Tier 1 may reject or report a limit violation, but must not silently clamp or
  rewrite an edited trajectory. Any projection/clamp must be an explicit,
  provenance-bearing diagnostic.
- ADE/FDE replay measurement must remain separate from any model used to create
  or filter a variant. A generated variant must be evaluated through the Tier 0
  replay path rather than scored against its own preview model.
- Tier 1 traces must be compatible with `normalized-replay-trace-v2` so the
  evaluator, reports and UI can consume one trace contract.
- nuScenes does not provide steering, tire, suspension or powertrain ground
  truth. Tire-slip, suspension, powertrain, aerodynamic and rigid-body claims
  are outside the MVP and cannot be justified by the current dataset.
- Tier 2 must never be silently represented as trajectory replay or used to
  claim final scientific fidelity. Unsupported controller/behavior modes remain
   fail-closed in the OpenSCENARIO subset.

## DEC-015 — Devkit-Authoritative Recorded Evidence Adapter

- Status: `APPROVED IMPLEMENTATION DECISION`
- The official nuScenes devkit is the semantic authority for recorded sensor,
  annotation, map and CAN interpretation. Real2Scenario owns typed contracts,
  provenance, private artifact policy, scenario editing, simulator sessions and
  browser rendering.
- Use cached `NuScenes` access, `LidarPointCloud.from_file_multisweep`, official
  `Box`/`get_sample_data` transforms, `NuScenesMap`, `NuScenesExplorer` projection
  semantics and `NuScenesCanBus`. Keep `MetadataIndex` for large discovery and
  benchmark queries.
- Optimize in this order: cached records, multisweep LiDAR, NumPy serialization,
  official annotation/map layers, cached CAN timestamp matching, then optional
  SciPy spatial indexing and radar/camera layers.
- Keep the authoring Top-down view unchanged. A separate Sensor Evidence view
  provides `LIDAR_TOP` history, map underlay, annotations and telemetry.
- Recorded evidence is never generated post-edit sensor output; unavailable
  capabilities remain explicit and raw/derived data stays local/private.

## DEC-016 — Disabled Workspace Controls

- Status: `APPROVED CURRENT MVP BOUNDARY`
- Behavior remains disabled because no behavior executor exists; it must remain
  structured `unsupported` rather than falling back to waypoint or kinematic
  preview semantics.
- Validate remains disabled until the Workspace exposes a connected validation
  action with an API-owned result. The browser must not imply validation by
  reusing gate labels or preview status.
- Replay remains disabled until an accepted replay request, trace contract and
  private artifact flow are connected to the workspace. Internal transform POV
  and recorded Sensor Evidence are not replay substitutes.
- The controls remain visible with explicit unavailable labeling so capability
  boundaries are discoverable and cannot be mistaken for completed workflows.

## DEC-017 — Replay Fidelity Contract and Current Self-Consistency Baseline

- Status: `OWNER-APPROVED / IMPLEMENTED / PROVISIONAL RESULTS`
- Commits: `b52d423` (following mode + integration step), `79a4a8a` (source
  provenance through the frame transform), `3372ff0` (documentation record).
- Decision 1: `followingMode` is returned to `position`. The `timing` mode
  permitted simulated drift that the recorded data does not contain.
- Decision 2: `fixed_timestep` moves `0.05 → 0.01` s. This is a contract change
  and the pinning assertion test was updated with it. `dt = 0.005` is
  bit-identical to `0.01`, so the step is converged and is not a tuning knob.
- Decision 3: the baseline is recomputed and every prior ADE/FDE figure is
  superseded. Validity is unchanged at 808/850 valid — no validity was traded
  for a better error number.
- Decision 4: the web contract exposes `source_timestamp_us` and
  `source_record_token` so a served frame can be traced back to the exact
  recorded sample and sensor record.
- Current baseline (full nuScenes `v1.0-trainval` 850-scene set, 3215 actor
  tracks, esmini v3.9.0): ADE mean **0.0411 m**, median **0.0348 m**, p95
  **0.1035 m**, max **0.1726 m**, FDE max **0.2052 m**, runtime cost **+14 %**.
- Root cause was a **timing anchor**, not the map template. A late-appearing
  actor ran from `t = 0`, covering roughly `track_start_time × speed` metres
  absent from the recording. Two conditions are required to fix it: hold speed
  until the recorded track starts, and align the follow-trajectory
  `StartTrigger` to the recorded track start. The "map template is the primary
  cause" hypothesis is **disproved by measurement** and must not be reused.
- Metric role: these figures are **export-versus-replay self-consistency**. They
  are not replay fidelity against the recorded driving trajectory and do not
  support a claim about simulation faithfulness. CP1 remains `20/143 = 13.99%`.
- **No threshold is proposed.** The aggregate currently exposes a micro mean
  only, and the scene-macro aggregate required by
  `docs/current/metric-benchmark-execution-plan.md` is still missing.
- All results remain `PROVISIONAL`.

## DEC-018 — Claim Boundaries After the Replay Fix

- Status: `OWNER-APPROVED / BINDING ON ALL REPORTING`
- Native esmini is the only sanctioned source of ADE/FDE. Visual preview,
  including the WASM playback surface, is **not** a metric source and no figure
  from it may enter a report.
- The WASM visual preview may be presented as a preview only.
- "Engineering correlation" is the strongest claim currently open for the
  recorded ego brake-pedal channel, and it is not yet granted. See DEC-019.
- **No map-accuracy claim** is permitted: gate G3 has never been evaluated.
- **No safety or TTC claim** is permitted: G6 always fails for implementation
  reasons, not measured ones.
- An unavailable capability must never be reported as a successful result.

## DEC-019 — Recorded Ego Brake Channel Reopened by Provenance Fix

- Status: `OWNER-DECISION REQUIRED / IMPLEMENTATION LANDED PROVISIONALLY`
- Context: `79a4a8a` fixed `RoadAlignedTransform`, which was dropping
  `source_timestamp_us` and `source_record_token` when rebuilding `State`. That
  loss is what kept the recorded ego brake pedal channel permanently
  unavailable with `canonical_states_missing_source_timestamp_us` — 383/383
  annotated states were losing provenance on the way into the local frame.
- Current state: a real scene reports braking `available = true` at coverage
  **0.625** from `nuscenes-can-vehicle-monitor-v1`. The same fix exposed and
  repaired a latent `_match_braking` crash on an empty channel that the missing
  timestamps had been masking.
- **This is a scope change, not only a metric change.** A channel that was
  uniformly unavailable is now partially available, so the UI, the availability
  contract and any downstream reading of the timeline are affected.
- Open decision for the owner: whether the UI may advance to an
  **"engineering correlation"** claim. Recommended position is to record it as
  an implemented capability with a coverage figure and a provenance contract,
  and **not** yet to claim correlation, because coverage is 0.625 rather than
  complete and the channel is ego-only.
- Until decided, the channel stays `PROVISIONAL` and no correlation figure may
  be published.

## DEC-020 — WASM / esminiJS Interactive Simulator

- Status: `OWNER-APPROVED AS FUTURE REPLACEMENT / DIAGNOSTIC-ONLY NOW`
- Commits: `b7e09a5` (handoff prompt and status reconciliation).
- The capability was proposed by external experts. It is **approved as the
  intended replacement for the project's current runner**, but the immediate
  priority is **testing and hardening**, not feature completion.
- **Placement: diagnostic-only.** WASM stays served at `/wasm-smoke` and stays
  out of `VIEW_REGISTRY`. Promotion to a real workspace view type requires a
  separate explicit owner approval after joint review. An agent must not promote
  it on its own judgement.
- **Parity requirements, binding.**
  - Integration timestep is `dt = 0.01`, matching native `--fixed_timestep
    0.01`. The timestep is measurably load-bearing: `0.05 → 0.01` moved ADE mean
    `0.1829 → 0.0411 m` (4.2x). A variable-step or rAF-driven integrator is a
    different integrator and will not agree with native.
  - The Worker owns the fixed-step clock. A UI interval driving steps does not
    satisfy parity.
  - Seek, if implemented, must be `reset` plus re-integration from `t = 0`.
    Jumping to a cached frame breaks parity because state depends on integration
    history. If seek is deferred, **no correlation claim may be made**: without
    seek a frame cannot be lined up with a LiDAR sweep.
- **Fusion means recorded nuScenes sensor data rendered alongside engine actors.**
  It does not mean sensor output from the WASM engine, which has no sensor
  channel. Recorded sensor evidence remains recorded nuScenes data and is never
  presented as engine-generated output.
- **Synchronized cross-panel focus is OPEN and deliberately not answered.** The
  owner's guidance was "decide later"; this entry records it as an open owner
  decision rather than a settled one so it is not lost or silently filled in by an
  agent. The full restated question, the identity-key problem, the candidate
  panels, the interim binding instruction and the revisit triggers are in
  `docs/proposals/wasm-interactive-simulator/next-agent-handoff.md` under
  "Retained open question — Q4". Interim rule: do not lift `selectedId` out of
  `ThreePlaybackCanvas` and do not add cross-panel selection surfaces.
- **`min_track_duration_s` is not applied.** Applying it to one engine only would
  make the two engines score different track populations, so the numbers would not
  be comparable. It is a population-alignment rule, not an accuracy tweak, and any
  future cut must be applied identically to both engines and chosen on physical
  grounds. Currently only **47/3215 tracks (1.5 %)** are under 2 s and residual is
  ~`0.035 m`, so there is no accuracy pressure. The browser engine's follower
  must be compared against native's before any cut is ever considered.
- **Claim boundaries from DEC-018 continue to apply without exception:** browser
  frames are preview/interaction only and never feed ADE/FDE, `replay.csv`, gates
  or any report. Native esmini remains the sole sanctioned metric source.
