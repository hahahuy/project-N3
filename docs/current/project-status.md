---
report_type: current_status
status: CURRENT
updated_at: 2026-10-15
---

# Project Status

## Scope

Plan A in `MVP&ProjectSummary.md` remains the project baseline. The project is
an academic nuScenes-to-OpenSCENARIO tool and paper with esmini and CARLA as
long-term simulator targets; under the superseding MVP decision, current MVP
acceptance uses esmini plus the internal kinematic preview, while CARLA is
post-MVP.

## One-Line Summary

Real2Scenario is an auditable pipeline that turns recorded driving interactions
into replayable OpenSCENARIO scenarios, measurable simulator traces and
controlled variants.

## Platform Direction

The architecture can evolve into a multi-dataset driving-simulation evaluation
platform, but this is a future direction rather than a current Plan A scope.
The required stable boundary is:

```text
dataset adapter
  -> canonical scenario + source provenance
  -> normalized map/geometry provider
  -> OpenSCENARIO/export contract
  -> simulator backend/trace contract
  -> evaluator/gates/reports/UI
```

For the current MVP, nuScenes remains the canonical dataset and Singapore
One-North remains the active map scope. Future driving LiDAR datasets should be
added through adapters that provide source timestamps, actor/trajectory
semantics, coordinate frames, map/geometry provenance, license metadata and
sensor calibration where applicable. They must not change the canonical model or
silently reuse nuScenes-specific assumptions.

## Environment and Data

- Python environment: `.venv/`, Python 3.12.
- Dataset root: `$NUSCENES_ROOT`, defaulting to `/mnt/backup/nuscenes`.
- Dataset version: `v1.0-trainval`.
- `v1.0-trainval` preflight: `RUNTIME_VERIFIED`.
- `v1.0-test`: metadata only for this setup; no trajectory extraction.
- Singapore One-North vector expansion is available locally.
- CP1 line-segment prototype emitted 2,002 roads and passed structural XODR
  validation. Immediate scope is a scene-local corridor around `scene-0061`;
  full Singapore One-North coverage is deferred future work.
- Current candidate set: 50 metadata-only Singapore One-North scenes; final
  benchmark index is not frozen.

## Checkpoints

| Checkpoint | Status | Current evidence/limitation |
|---|---|---|
| CP0 | `PARTIAL` | Python/esmini foundations exist; CARLA handshake/smoke was observed locally, but CP0 sample evidence needs a phase report. |
| CP1 | `PARTIAL/CORRIDOR-EXTERNAL-VERIFIED` | 40 m scene-local corridor is structurally/runtime verified; raw road-match is 13.99% provisional, occupancy has unsupported states, and CARLA remains unverified. |
| CP2 | `CP2-A-COMPLETE/CARLA-UNVERIFIED` | Alignment, blueprint mapping, replay planning, exact-pose batches and the strict XOSC interpreter are implemented and tested, including on real exported scenarios; CARLA runtime, custom XODR import and the paired same-XOSC run remain unverified and post-MVP. |
| CP3 | `PARTIAL/IMPLEMENTED` | ADE/FDE/provenance aggregates, diagnostic gates and deterministic multi-scene aggregation are wired through reports/API/UI, and a real five-scene provisional run exists; the approved scene index, benchmark protocol and final scientific policy remain open. |
| CP4 | `PARTIAL/EVIDENCE-CLOSED` | G1-G7 batch integration and funnel reconciliation exist; G3 and G5 consume explicit fail-closed evidence and G3 is now evaluated for all 60 benchmark candidates (zero passes below the provisional reference), but G6/G7 scientific policy is open and no final acceptance exists. |
| CP5 | `PARTIAL/RELEASE-EVIDENCE` | Apache-2.0 boundary, benchmark manifest, dependency lockfile and a clean-checkout release evidence bundle exist; `HEAD` verification is blocked on committing the verified tree and owner sign-off remains open. |
| CP6 | `OPEN` | RQs and paper evidence bundle are not complete. |

## Current Claims

- CP1 map output is an engineering prototype, not accepted map fidelity.
- CP1 priority is a declared scene-local corridor, not full-map completion.
- CARLA direct-transform execution is feasibility-only.
- Same-XOSC CP2 requires identical `.xosc` and companion map hashes.
- CARLA is post-MVP; current MVP uses esmini plus an internal kinematic preview.
- CP2-A exact-pose planning and strict XOSC interpretation are implemented and
  tested; CARLA remains environment-deferred and no same-XOSC claim is made.
- G6/G7 temporary funnel results are diagnostic and `PROVISIONAL`.
- Workspace recipe, variant lineage, synchronized Compare and evidence-layer
  workflows are implemented as additive contracts. Recipe history is explicitly
  in-process and non-destructive; replay metrics remain `PROVISIONAL`; no final
  scientific threshold or canonical recorded scenario was changed.
- Constrained maneuver authoring now uses named recipe steps and explicit time ranges, with Tier 1 `kinematic-open-loop-v1` limits, violations, provenance and immutable-parent rollback markers visible in the local preview UI; CP1 remains `20/143 = 13.99%` provisional.
- Browser acceptance now covers the real local recipe editor, Tier 1 steering/acceleration/braking/target-speed preview, rollback/undo state, synchronized Compare, timeline/gate text equivalents, evidence layers and keyboard/mobile-capable controls. The no-dataset runtime correctly reports LiDAR and esmini image artifacts unavailable.
- Variant sensor status is explicit through `workspace-variant-sensor-v1`: post-edit frames remain `unsupported` until generated artifacts exist, while a recorded parent sweep is reported separately with provenance. `workspace-pov-image-v1` serves only real private esmini capture artifacts; transform-only internal POV remains distinct and is never mislabeled as an image.
- The separate Sensor Evidence view preserves Top-down as the authoring/map/trajectory pane. Its `nuscenes-sensor-evidence-v1` contract follows nuScenes `LIDAR_TOP` recorded-history semantics equivalent to five-sweep `render_sample_data`: sweep tokens/timestamps, calibration and ego poses, private payload links, decimation, layer controls, synchronization status and honest historical-sweep smearing are exposed. Map underlay and CAN telemetry are independently reported unavailable unless configured; post-edit sensor frames remain unsupported.
- The approved next simulator architecture is a native, bounded `esminiLib` live-session adapter with WebSocket-friendly state/control messages and a browser-native Three.js/PlayCanvas renderer. The existing subprocess/image-capture path remains for replay, validation and evidence; it is not the primary live 3D interaction path. Full esmini WebAssembly, Unity WebGL and WebRTC remote rendering are deferred alternatives.
- `esmini-live-session-v1` is now implemented as a bounded optional native-binding service with XOSC/XODR confinement and SHA-256 identity, lifecycle/control/camera validation, REST commands and a WebSocket-friendly state stream. Upstream esmini v3.10.0 was cloned outside the repository, host v3.9 and v3.10 shared-library load/step smokes pass, and Compose container load/step returned four named private scenario objects at `t=0.05s`. Browser camera state is separate from the native viewer. No kinematic or screenshot fallback is claimed as esmini state.
- Native reset now reloads the same confined XOSC/XODR pair because the public esminiLib ABI has no stable reset symbol. Native control remains explicitly unavailable with `esminiLib_control_abi_unavailable`; camera commands remain browser-renderer state.
- `POST /api/esmini/live/scenario-pairs` safely materializes a private generated XOSC/XODR pair from an existing scenario artifact and creates its bounded live session. Pair directories use a hashed scenario key and are served only through the existing confined artifact route.
- The remaining CP1/CP3/CP4/CP5 closure items are still owner decisions: CP1 semantic policy and baseline interpretation, CP3 approved index/scientific policy, CP4 final gate policy, and CP5 release sign-off. CP6 research questions and paper evidence are likewise owner-required. Existing diagnostics and metrics remain provisional.
- Compose now exposes `ESMINILIB_PATH` alongside `ESMINI_BIN` and `ESMINI_DAT2CSV`; the mounted `/opt/esmini` tree must include the executable, shared library, catalogs/models and compatible runtime assets.
- The browser POV surface includes a native-state renderer path that consumes timestamped live objects when a live session is available and labels it separately from internal transform preview and `workspace-pov-image-v1` artifacts. Frontend API coverage keeps the live-state contract separate from image-frame requests; full browser session walkthrough remains open because the UI does not fabricate a session without an exposed artifact pair. CARLA remains post-MVP and variant post-edit sensor frames remain unsupported.
- The add-view flow is wired for up to four panes with Top-down, 3rd-person POV, In-car POV and LiDAR 3D types; close, make-main, maximize/restore, reset-layout and responsive arrangements are covered. The current default Top-down is the authoring/map/trajectory view. The approved nuScenes devkit-style `LIDAR_TOP` multi-sweep evidence view (`nsweeps=5`, map underlay, ego pose/calibration and CAN telemetry) is a separate next view mode, not a replacement for authoring Top-down.
- The approved optimization is recorded in `docs/current/nuscenes-devkit-optimization-decision.md`: use cached devkit semantics for multisweep LiDAR, official transforms/boxes/maps/projections and CAN, then use NumPy/vectorized payloads and measured spatial indexing while keeping application contracts and provenance separate.
- ADE/FDE scientific thresholds are not finalized.

## Remaining Work Order

The Wave 3A backend, Workspace authoring slice and Phase 2 devkit contracts are
implemented and verified locally. Remaining implementation order is: the separate
nuScenes `LIDAR_TOP` multi-sweep evidence view; full browser live-session
acceptance; post-edit sensor/render frame generation or explicit unavailable
boundaries; private runtime/browser acceptance; CP1/CP3/CP4/CP5 engineering
closure; and CP6 paper/evidence closure. Esmini image capture remains a replay and
evidence path, not the live editor path. CARLA same-XOSC remains separate and
post-MVP.

```text
Native esminiLib live-session adapter and state/control contract
  -> browser-native Three.js/PlayCanvas live renderer
  -> separate nuScenes LIDAR_TOP nsweeps=5 evidence view with map underlay
  -> post-edit camera/LiDAR/radar frames or explicit unsupported contracts
  -> complete private runtime/browser acceptance
  -> CP1/CP3/CP4/CP5 engineering closure
  -> CP6 paper and evidence closure
  -> post-MVP CP2 same-XOSC CARLA execution
```

CP1, CP3, CP4, CP5 and UI/sensor work continue as separate gated tracks. No UI,
sensor or POV implementation may redefine the canonical scenario, same-XOSC
contract, license boundary or scientific thresholds.

## Workspace Wiring Checkpoint

- Workspace now consumes real native map geometry and time-indexed actor state
  when the configured nuScenes dataset/devkit supplies them.
- Constrained maneuver fields are wired to preview requests; arbitrary
  displacement and per-axis velocity edits remain outside the API schema.
- Private decimated `LIDAR_TOP` serving and browser canvas rendering are
  implemented with API calibration/ego-pose transforms, timestamp, frame,
  decimation and count provenance. Post-edit sensor frames are not generated or
  claimed; variant views must remain on the explicit parent-sweep/unavailable
  contract until backend support exists. CARLA remains post-MVP.
- Local runtime acceptance verified real `scene-0001` actor/map Workspace data
  and a binary decimated LiDAR payload; evidence is provisional and private.

## Wave 3A Checkpoint Started

- Started 2026-10-12 after confirming the existing local demo has catalog,
  trajectory, batch, validation and esmini surfaces but no actor-level preview
  edit contract.
- Active implementation is limited to the documented parameterized edit mode:
  speed, heading, initial gap, timing and seed.
- Backend work must remain synthetic-fixture capable and must not claim CP1/CP2,
  CARLA same-XOSC, final thresholds or public nuScenes artifact release.
- Wave 3A backend slice verified: actor-scoped deterministic preview, structured
  validation/G4-G7 response, private artifact output and fail-closed behavior
  mode. U0 frontend is `SHOWCASE-READY`.
- U0 frontend source integration, synthetic-fixture browser flow and standard
  Compose runtime are verified. U0 is `SHOWCASE-READY`; this does not claim
  CP1, CP2, CARLA, sensor or behavior execution completion.
- U0 preview generates edited trajectory states and a private child scenario
  artifact. The approved internal kinematic simulator/frame-producing preview
  remains incomplete: U0 does not yet generate post-edit camera/LiDAR/radar
  frames, and its timeline is a path-view timestamp control, not a frame
  renderer. The target workspace now explicitly includes simulator third-person
  and in-car POVs, native map POV, recorded LiDAR POV and time-indexed actor
  state; these are not yet fully wired.
- Full 2D/3D authoring workspace remains unfinished MVP work. U0 currently
  provides catalog/review, parameterized trajectory preview, path overlay and a
  timeline label, but not the complete simulator-backed authoring POV, native
  map POV, recorded LiDAR POV or constrained maneuver editor.
- UI0 interaction audit on `review/ui0-interaction-audit` exercised the desktop
  and mobile control surface. It fixed a generated-batch-result 404 caused by
  probing `/api/scenarios/{variant_id}` before loading the supported batch
  trajectory endpoint; frontend tests/build and a clean browser reload pass.

- Simulator-backed POV slice now exposes `simulator-frame-v1`: the internal
  kinematic preview returns timestamp-selected actor/camera transforms for
  third-person and ego-mounted in-car views. esmini image frames and CARLA
  same-XOSC remain separate; CARLA is post-MVP.
- CP3 metric/gate wiring is verified with Python and frontend tests/build; replay
  aggregates remain diagnostic and no final ADE/FDE thresholds are set.
- CP1 arc-fitting is integrated behind an explicit `geometry_mode="line_arc"`
  with synthetic residual tests; external map fidelity acceptance remains open.
- CP1 continuity diagnostics are implemented and tested with synthetic joins;
  they do not emit junctions or establish lane-level road-match acceptance.
- CP1 has conservative synthetic-tested connector junction and polygon-width
  paths; full One-North topology/width review and lane-level road-match remain
  open.
- CP1 lane road-match is now a standalone diagnostic with raw state/actor rates;
  external One-North/scene-0061 integration and the provisional 95% review are
  now supported by a private baseline; the observed 57.37% rate is below the provisional
  reference and requires alignment/selection investigation.
- CP1 scene-0061 matrix analysis found exact global/local transform equivalence;
  current interaction-selected actors score 13.99% versus 57.37% for all 30
  vehicles. Distance/occupancy and candidate-selection diagnostics remain open.
- CP1 occupancy/candidate diagnostics are implemented. The selected scene-0061
  private baseline reports 39 occupied, 65 outside and 39 unsupported states;
  the comparison used fallback width and incomplete dimensions, so polygon-width
  evidence remains open.
- CP1 generated full-map XODR passes XML/subset checks and loads in esmini after topology
  repair; the independent audit reports zero dangling junction references and
  zero dangling road links. This is baseline evidence only; corridor closure,
  CARLA and full CP1 acceptance remain unverified.
- CP1 corridor selection/one-hop closure is implemented and synthetic-tested;
  the next evidence run uses the declared `scene-0061` corridor with a fixed
  first-run buffer of `40 m`.
- CP1 corridor external run completed: 82 roads, 576 geometries, 46 junctions,
  zero dangling references and esmini exit 0. Corridor road-match is 20/143
  (`13.99%`) and remains diagnostic/provisional.
- CP1 direction/footprint analysis separates the three zero-rate actors: one
  has 39/39 reverse-heading counterfactual rescues, while two have large lateral
  offsets and no reverse rescue. No production direction policy change is made.
- CP1 manual review is governed by `docs/current/cp1-manual-review-protocol.md`;
  baseline actor scope and tolerances remain immutable while exploratory
  owner-approved runs are compared separately.
- CP1 corridor attribution found identical nearest lanes against the full map and
  corridor for all 143 selected-scope states; the crop is not the low-rate cause.
- CP1 lane-sequence matcher was self-verified against the accessible private
  scene-0061/v1.0-trainval corridor data as an exploratory diagnostic. Across
  143 selected-scope states it produced 29 high-confidence, 49 low-confidence,
  12 ambiguous, 44 topology-gap and 9 direction-conflict classifications;
  five non-positive map segments were reported separately. This does not replace
  the immutable 20/143 baseline or constitute an owner-approved acceptance run.
- The self-verification narrows owner confirmation to retaining the automatic
  actor scope, retaining unsupported ego dimensions, keeping reverse direction
  counterfactual-only, and treating the geometry/topology defects as unresolved
  diagnostic findings. Broad visual review is not required unless a specific
  classification is disputed.
- CP1 geometry follow-up added deterministic `centerline-repair-v1`: the 82
  corridor records inspected had 12 repaired by removing duplicate samples and
  zero excluded; the five previously reported non-positive defects are now
  repaired at the map-builder boundary. Explicit topology validation checked
  80 corridor links with zero reciprocal/endpoint/heading failures. The rerun
  still reports low-confidence lateral/direction evidence, so this is not CP1
  acceptance.
- CP1 native/canonical/XODR comparison was executed for the same 143 states.
  Native and canonical results agree: 90 lane-semantic-valid, 104 high
  centerline-offset, 42 polygon-outside and 11 heading-conflict states. The
  generated XODR diagnostic is not a native lane-truth oracle and has 35
  unmatched states under the lightweight export parser. The remaining issue is
  therefore actor/reference or native-map semantics, not canonical conversion;
  no actor offsets, lane reversal or tolerance changes are justified.
- CP5 reproducibility manifest is implemented independently of CP1. It records
  project/runtime metadata, caller-supplied dataset/map/simulator metadata,
  config hash, visibility, and project-relative artifact hashes; benchmark
  orchestration and clean-checkout evidence remain open.
- CP1 actor-reference and direction diagnostics are implemented as additive
  contracts. They compare globally declared center/axle/fixed-offset hypotheses,
  preserve unsupported dimensions, and retain annotation/motion/lane headings;
  they do not change the canonical reference convention or production lane
  direction. The private scene-0061 run found native direction classifications
  of 47 aligned, 53 annotation-only, 16 annotation-yaw-error, 3 true-reverse
  and 24 uncertain states; global hypotheses did not resolve the lateral actors.
  CP1 remains `PARTIAL/PROVISIONAL` pending owner interpretation and cross-scene
  evidence.
- Owner interpretation of that diagnostic is explicitly deferred as a later
  objective. This does not approve any actor correction, lane reversal, threshold
  change or CP1 acceptance. Additive CP4 orchestration work may proceed while
  the private diagnostic bundle remains available for re-entry.
- CP2-A is now complete as a non-runtime slice. The XOSC interpreter resolves
  Init teleports, the Story/Act structure, maneuver groups, trajectory validity,
  the `TimeReference` and start/stop trigger conditions into an auditable plan
  carrying the same execution identity the exact-pose planner revalidates. It is
  fail-closed on anything outside the declared subset, and it interprets all 48
  real exported `.xosc` files from the provisional benchmark run. CARLA runtime
  remains unverified and post-MVP.
- Wave 3A gate and metric wiring is complete. Preview and batch responses now
  share one explicit metric-availability contract, so a missing replay trace is
  reported as unavailable with a reason instead of being inferred from status
  counts, and metrics are never fabricated or defaulted.
- The MVP physics policy is explicit: Tier 0 esmini replay measures trajectory
  fidelity; Tier 1 `kinematic-open-loop-v1` handles lightweight feasibility
  preview; controller/dynamics experiments are Tier 2 post-MVP.
- CP5 now has benchmark reproducibility and release evidence. Each benchmark run
  emits a `reproducibility-manifest-v1` that inventories every run artifact by
  relative path with size and SHA-256 plus a hashed configuration block, git
  revision, working-tree cleanliness, runtime and simulator metadata, and
  `requirements.lock.txt` pins the verified environment.
  `scripts/verify_release.py` runs the documented verification against a clean
  `git archive` export of `HEAD` or a working-tree snapshot and emits a
  `release-evidence-v1` bundle. That check exposed a real dependency of the
  suite on the git-ignored local dataset, which is now an
  explicit skip; clean-checkout verification of the current sources passes, while
  `HEAD` verification remains blocked until the verified tree is committed. Owner
  sign-off is still pending.
- CP1 has extended its reference, footprint and topology diagnostics to all five
  benchmark scenes and all 60 candidates. Native and canonical references agree
  exactly on every scene, and the generated OpenDRIVE reproduces the corridor
  reference exactly, which rules out map conversion and OpenDRIVE export as the
  cause of the low strict road-match rate. Lane-semantic validity is high
  (`66-100%` of states) while strict centerline match stays between `0.0000` and
  `0.2500`, so the residual is a lateral offset between the driven path and the
  emitted corridor centerlines. All five corridors pass the OpenDRIVE subset
  check with zero dangling junction references and zero dangling road links,
  derive every lane width from the nuScenes polygon, and fit arcs within the
  declared `0.05 m` tolerance. Ego dimensions remain explicitly unsupported in
  every scene.
- CP1 has produced per-candidate lane road-match evidence for all 60 benchmark
  candidates. A corridor is built per benchmark scene around the parent actor
  paths, expressed in the candidates' local frame, and measured with the
  unchanged matcher tolerances. Mean raw match rate ranges from `0.0000`
  (`scene-0380`) to `0.2500` (`scene-0957`); the recurring causes remain lane
  direction disagreement and lateral offset beyond the `0.5 m` tolerance. G3 is
  now evaluated for every candidate rather than skipped, and reports zero passes
  below the fixed provisional reference. Nothing was tuned and CP1 remains
  `PARTIAL/PROVISIONAL`.
- CP4 now has explicit gate evidence contracts. `lane-road-match-evidence-v1`
  carries validated road-match counts into the G3 gate for exactly one declared
  candidate, rejects unknown fields, inconsistent counts, missing matcher
  configuration and any non-provisional claim, and keeps the `0.95` reference
  fixed; the API cannot supply a replacement threshold. G5 consumes an explicit
  operator-declared event window that is validated before use and written into
  variant provenance. A candidate without a declared event is now `skipped`
  instead of `error`, so G5 reports a real evaluated split (3 pass, 2 fail on a
  five-scene declared-event run) instead of permanent errors. G3 stays skipped
  until CP1 produces candidate road-match evidence; no evidence was fabricated.
- CP4 now has additive ordered G1-G7 orchestration with structured skipped/error
  states and cumulative funnel counts. G1 subset validation, G2 simulator status
  recording and G3 provisional road-match evaluation do not establish complete
  schema, simulator, lane-truth or final scientific acceptance. Batch/API
  integration now exposes all seven gate states and aggregate funnel counts;
  replay-disabled candidates remain explicitly unverified for simulator gates.
  A mixed synthetic batch now reconciles one valid, two invalid and one
  simulator-failed candidate under the provisional funnel contract.
- CP3 now has a deterministic multi-scene benchmark aggregate contract that
  separates synthetic, local nuScenes and simulator classes, aggregates
  provisional ADE/FDE and G1-G7 counts, and excludes host paths/raw artifacts.
  An agent-selected five-scene Singapore One-North metadata index now exists
  privately without owner approval; canonical preparation exceeded the current
  execution window, so no real multi-scene metrics or acceptance claim exists.
- The backend Workspace contract slice implements B-WORKSPACE-01, B-WORKSPACE-02
  and B-WORKSPACE-06 through read-only document/scenario endpoints. Actor roles,
  dimensions, paths, provenance and metric availability are explicit; map, 3D
  and LiDAR layers remain unavailable with API-owned reasons rather than fake
  geometry or values.
- That CP3 preparation blocker is now cleared. A cached metadata index
  (`nuscenes-metadata-index-v1`) streams the trainval tables once into a local
  private SQLite cache, and `extract_scenario` accepts preloaded tables, so
  scene discovery and import no longer rescan the multi-hundred-megabyte
  metadata files per scene. Scene discovery and import output is unchanged.
- The first real multi-scene benchmark run is complete on the agent-selected
  provisional index: five Singapore One-North scenes, grid seed 7, 12 variants
  each, esmini `v3.9.0`, 60 generated with 48 valid, 12 invalid and 0 simulator
  failures. Replay self-consistency ADE ranges from about `0.03 m` to `43 m`
  depending on scene, G3 stays skipped for missing road-match evidence and G5
  errors on missing event definitions. All values remain `PROVISIONAL`; no CP3
  acceptance, threshold or benchmark-index approval is claimed.
- Owner-approved nuScenes-devkit backend makeover Phase 1 is implemented: CAN
  `pose` optionally supplies matched ego speed with explicit finite-difference
  fallback, and polygon lane widths prefer a sampled cross-section median. The
  canonical State schema, CP1 baseline and scientific thresholds remain unchanged;
  source-state, sensor/map APIs and Workspace wiring are implemented with
  fail-closed runtime boundaries.

## Latest Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
  315 passed, 1 warning. The warning is the existing Starlette/httpx deprecation;
the cache provider is disabled because the default pytest cache path is not
writable in this worktree.

cd frontend && npm test && npm run build
 37 tests passed across the API boundary and the Workspace keyboard, mobile and
accessibility suites; the production build succeeds.
```

## Next Safe Work

### Tracks 1-6 disposition

- Track 1 native runtime proof: `HOST-AND-COMPOSE-SMOKE-VERIFIED`. Upstream
  v3.10 release artifacts were cloned outside the repository, the v3.10 ctypes
  ABI was wired, and both v3.10 and host v3.9 load/step smokes return two objects.
  Compose exposes `ESMINILIB_PATH`, mounts `/opt/esmini`, and a container session
  loaded/stepped a private XOSC/XODR pair with four named objects. Native control
  and reset remain ABI-scoped unavailable; browser camera state is renderer-owned.
- Track 2 browser live 3D: `IMPLEMENTED-PARTIAL/HOST-NATIVE-SMOKE`. The browser
  state renderer, capability/state API clients and timeline-bound POV surface are
  wired; full browser acceptance against an actual native session remains open.
- Track 3 post-edit sensors: `UNSUPPORTED-EXACT-REASON`. No calibrated post-edit
  camera/LiDAR/radar generator or generated artifact manifest exists. Variant
  status remains `unsupported` with `post_edit_sensor_frames_not_generated`; only
  the explicit recorded parent-sweep fallback is allowed.
- Track 4 private runtime acceptance: `PARTIAL/PROVISIONAL`. Private native
  map/state/LiDAR and browser acceptance are recorded; Compose assets/configuration
  are verified and native replay reaches esmini, but image capture fails closed
  with `Viewer initialization failed` because the container has no usable display.
- Track 5 engineering closure: `PARTIAL/PENDING-OWNER`. CP1 remains the immutable
  `20/143 = 13.99%` provisional baseline; CP3 scene/index/scientific policy,
  CP4 scientific gate policy and CP5 owner sign-off remain open. Working-tree
  release verification passes, but committed-HEAD proof still depends on commit
  and owner sign-off.
- Track 6 paper closure: `OPEN/OWNER-REQUIRED`. Existing CP1/CP3/CP4/CP5
  engineering evidence is inventory only; final research questions and final
  scientific results are not approved, so no paper claim is promoted.

1. Review the recorded CAN pedal channel where a source scene declares recorded
   timestamps and complete any remaining per-sample text-equivalent review.
2. Run esmini image capture on a runtime with viewer/off-screen support and
   publish a private capture manifest; the API remains fail-closed without it.
3. Implement post-edit camera/LiDAR/radar generation only when real calibrated
   frame generation is available; retain the parent-sweep and unavailable states.
4. Add owner acceptance evidence for the completed Workspace flows.
5. Add advisory nuScenes prediction evaluation without mixing metric roles.
6. Resume CP1/CP3/CP4/CP5 closure tracks after source/UI contracts stabilize.
7. Complete the CP6 paper evidence bundle from accepted, reproducible results.
8. Implement CP2 same-XOSC CARLA execution only as post-MVP work.
9. Defer full Singapore One-North coverage and alternate providers until the
   active source and corridor contracts are accepted.
