---
report_type: current_status
status: CURRENT
updated_at: 2026-10-12
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
- ADE/FDE scientific thresholds are not finalized.

## Execution Order

The Wave 3A backend and U0 showcase slice is implemented and verified. U0 is a
showcase, not the complete MVP authoring workspace. The remaining current-MVP
  work is CP1/CP3/CP4/CP5 evidence/sign-off closure plus the Tier 1 internal
  kinematic simulator,
full 2D/3D authoring workspace, frame-aware timeline and optional recorded LiDAR
evidence. CARLA runtime and same-XOSC remain post-MVP.

```text
CP1 semantic-alignment owner review and diagnostics
  -> CP3 benchmark evidence + CP4 G1-G7 orchestration + CP5 reproducibility
  -> internal kinematic simulator
  -> full 2D/3D authoring workspace + frame-aware timeline
  -> optional recorded LiDAR evidence + CP6 paper bundle
  -> post-MVP CP2 same-XOSC CARLA execution
```

CP1, CP3, CP4, CP5 and UI/sensor work continue as separate gated tracks. No UI,
sensor or POV implementation may redefine the canonical scenario, same-XOSC
contract, license boundary or scientific thresholds.

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
  renderer.
- Full 2D/3D authoring workspace remains unfinished MVP work. U0 currently
  provides catalog/review, parameterized trajectory preview, path overlay and a
  timeline label, but not the complete simulator-backed authoring POV.
- UI0 interaction audit on `review/ui0-interaction-audit` exercised the desktop
  and mobile control surface. It fixed a generated-batch-result 404 caused by
  probing `/api/scenarios/{variant_id}` before loading the supported batch
  trajectory endpoint; frontend tests/build and a clean browser reload pass.
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

## Latest Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
259 passed, 1 warning. The warning is the existing Starlette/httpx deprecation;
the cache provider is disabled because the default pytest cache path is not
writable in this worktree.
```

## Next Safe Work

1. Start the CP1 semantic-alignment diagnostic from
   `docs/current/next-agent-handoff.md` and
   `docs/current/cp1-agent-handoff-next.md`.
2. Owner confirm the remaining CP1 policy decisions recorded in
   `docs/reports/cp1-private-sequence-self-verification.md`; no broad visual
   review is required unless classifications are disputed.
3. Close CP3 benchmark evidence with owner review of the completed provisional
   multi-scene run and of the agent-selected scene index; do not turn provisional
   metrics into final thresholds.
4. Commit the verified tree and repeat clean-checkout release verification so
   the `HEAD` bundle can pass, then attribute the low per-scene road-match rates
   across native, canonical and corridor references without changing provisional
   policy, tolerances or artifact boundaries.
5. Implement the internal fixed-timestep kinematic simulator and its normalized
   preview trace/collision pre-check contract, then build the 2D/3D workspace
   against `docs/current/ui-mvp-flow-spec.md`.
6. Build the full 2D/3D authoring workspace: scene layers, actor selection and
   editing, follow/orbit/analyst POV, vectors, timeline cursor and provenance.
7. Add post-edit frame generation/timestamp-addressable artifacts and the
   optional recorded LiDAR evidence layer where approved local data exists.
8. Complete the CP6 paper evidence bundle from accepted, reproducible results.
9. Implement the CP2 XOSC interpreter and CARLA custom-map execution path only
   as post-MVP work.
10. Defer full Singapore One-North coverage and alternate LiDAR/map-source
   adapters until the corridor path is accepted.
11. Late-future multi-dataset platform work is defined in
   `docs/current/late-future-platform-plan.md` and is not part of current
   CP0-CP6 acceptance.
