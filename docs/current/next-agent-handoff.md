# Next Agent Handoff — Start Here

Status: `READY FOR IMPLEMENTATION`  
Owner: Project Manager agent  
Primary next work: CP1 semantic-alignment follow-up

This document is the start point for the next implementation agent. Begin with
the repository orientation below. Do not assume that a previous agent's task,
branch, private artifact or runtime environment is available.

## Mission

Continue Real2Scenario without changing the approved scope, contracts, artifact
policy or scientific interpretation. The first implementation slice is the
owner-reviewable CP1 semantic-alignment diagnostic described in
`docs/current/cp1-agent-handoff-next.md`.

Do not begin CARLA runtime work, new dataset adapters, full UI authoring, OSM
activation or final threshold selection as part of this CP1 handoff. Full UI
authoring remains a later current-MVP work item in the completion sequence below.

## Start From Zero

### 1. Inspect the repository

Run from the repository root:

```bash
git status --short
git log --oneline -10
```

There may be unrelated uncommitted changes. Do not revert, reset or overwrite
them. Confirm the Python environment and available commands:

```bash
python --version
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

The expected current baseline is the documentation checker passing and the full
suite passing. Record any difference before implementation.

### 2. Read the project context

Read these documents in order:

1. `MVP&ProjectSummary.md`
2. `README.md`
3. `docs/current/pm-agent-guide.md`
4. `docs/current/project-status.md`
5. `docs/current/decisions.md`
6. `docs/current/active-work.md`
7. `docs/current/technical-contracts.md`
8. `docs/current/evidence-index.md`
9. `docs/current/artifact-policy.md`
10. `docs/current/cp1-agent-handoff-next.md`
11. this document

Read the linked CP1 reports before changing CP1 code:

- `docs/reports/cp1-corridor-external-evidence.md`
- `docs/reports/cp1-geometry-topology-follow-up.md`
- `docs/reports/cp1-native-canonical-xodr-comparison.md`
- `docs/reports/cp1-corridor-attribution-analysis.md`
- `docs/reports/cp1-corridor-direction-footprint-analysis.md`
- `docs/reports/cp1-private-sequence-self-verification.md`

Historical Plan B files under `docs/archive/plan-b/` are not current scope.

### 3. Confirm the assigned work

Before editing code, confirm the item and status in
`docs/current/active-work.md`. The assigned first slice is:

```text
CP1 semantic-alignment diagnostic
  -> actor/reference semantics and cross-reference comparison
  -> private evidence bundle
  -> owner-reviewable report
```

If the owner has not approved a change to actor scope, lane direction, reference
convention, tolerance or ground truth policy, do not make that change. Record
the blocker and produce diagnostics instead.

## Current MVP Scope

```text
nuScenes v1.0-trainval
  -> canonical scenario and provenance
  -> scene-local map corridor around scene-0061
  -> OpenDRIVE/OpenSCENARIO
  -> esmini replay and evaluation
  -> ADE/FDE and diagnostic gates
  -> dynamic actor/object variation editor
  -> internal lightweight kinematic preview
  -> full 2D/3D authoring workspace and analyst POV
  -> optional recorded LiDAR evidence layer
```

Use `/mnt/backup/nuscenes` as the default local dataset root unless a task
explicitly supplies another `NUSCENES_ROOT`.

CARLA is post-MVP. Same-XOSC CARLA execution, custom-map import and paired
comparison remain future work. Esmini and the internal kinematic preview are the
current MVP execution backends.

Full Singapore One-North coverage, alternate datasets and OSM activation are
deferred work. Full 2D/3D authoring is not deferred from the MVP; it is
unfinished work after the current U0 showcase.

## Current Checkpoint State

- CP0: `PARTIAL`; formal CARLA sample evidence is incomplete.
- CP1: `PARTIAL/CORRIDOR-EXTERNAL-VERIFIED`; structural corridor and esmini
  evidence exist, but semantic road-match remains provisional and low.
- CP2: `CP2-A-COMPLETE/CARLA-UNVERIFIED`; strict XOSC interpretation and
  exact-pose planning are tested; live CARLA and same-XOSC execution are
  unverified and post-MVP.
- CP3: `PARTIAL/IMPLEMENTED`; metrics, aggregates and diagnostic gate wiring
  exist; final scientific policy remains open.
- CP4: `PARTIAL`; complete G1-G7 orchestration remains open.
- CP5: `PARTIAL/REPRO-MANIFEST`; manifest foundations exist; benchmark, release
  and sign-off evidence remain open.
- CP6: `OPEN`; paper evidence is incomplete.
- U0: `SHOWCASE-READY`; this is not CP1, CP2, CARLA or sensor completion.

## CP1 Immutable Baseline

The active target is a 40 m scene-local corridor around `scene-0061`, not the
full Singapore One-North map.

Current private corridor evidence:

- `82` roads;
- `576` geometries;
- `46` junction groups;
- zero dangling junction references;
- zero dangling road links;
- esmini exit code `0`;
- selected-scope baseline `20/143 = 13.99%`;
- all-vehicle context `57.37%`.

The selected-scope `20/143` result is immutable for comparison. The all-vehicle
value is context only and must not replace the selected-scope baseline.

The low result is not currently explained by corridor crop or global/local
transform. Geometry repair and selected-corridor topology repair are complete.
The remaining work is actor/reference semantics, lane membership, direction,
lateral offset, footprint capability and cross-reference diagnosis.

## First Implementation Task

Implement or extend a private diagnostic comparing the same trajectories against:

1. native nuScenes map reference;
2. project canonical lane graph;
3. generated OpenDRIVE reference.

For each state, preserve provenance and report independently:

- lane/connector identity;
- polygon containment;
- signed lateral offset;
- annotation yaw and motion-heading error;
- predecessor/successor validity;
- candidate confidence and failure reason;
- `lane_semantically_valid`;
- `lane_centerline_offset_high`;
- `lane_polygon_outside`;
- `footprint_unsupported`;
- `heading_conflict`;
- `topology_invalid`.

Use the official nuScenes map expansion API and existing project contracts. Do
not tune HMM weights, apply actor-specific offsets, reverse a lane, change the
actor set, change tolerances or reinterpret ground truth to improve the score.
Reverse direction remains counterfactual-only.

The detailed experiment contract is in
`docs/current/cp1-agent-handoff-next.md`. The native/canonical/XODR comparison
already exists; do not repeat completed geometry repair or selected-corridor
topology work unless a new failure is demonstrated.

## Required Evidence

Keep raw/private artifacts outside the repository. The report must record:

- git revision;
- dataset, map and XODR hashes;
- matcher and repair configuration;
- lane-graph/reference-convention versions;
- actor-selection policy;
- command and runtime version;
- per-reference result counts;
- unresolved classifications;
- owner-required decisions.

Use the existing report locations for private outputs and write the English
summary under `docs/reports/`. Update `docs/current/evidence-index.md` if a new
report is added or an existing claim is superseded.

## Acceptance Boundaries

The task is complete only when:

- the immutable `20/143 = 13.99%` baseline is preserved;
- native, canonical and generated-reference results are separated;
- geometry/topology repairs are not incorrectly reported as current defects;
- unsupported ego dimensions remain explicitly unsupported;
- no actor-specific correction or silent policy change is introduced;
- tests cover the diagnostic contracts;
- private runtime evidence is reproducible from documented commands;
- CP1 remains `PARTIAL/PROVISIONAL` unless the owner approves a new decision.

Do not claim CP1 acceptance from structural XODR validity, esmini load success,
a higher matcher score or a single-scene counterfactual.

## Current MVP Completion Sequence

The first agent starts with CP1 semantic alignment. After that slice, the PM
should schedule the remaining current-MVP work in this order:

1. Owner interpretation and cross-scene confirmation of CP1 diagnostics while
   preserving the `20/143` baseline.
2. CP3 approved-scene benchmark execution and aggregate evidence.
3. CP4 complete G1-G7 orchestration with provisional scientific labeling.
4. CP5 owner sign-off and verified-tree release evidence.
5. Implement the Tier 1 `kinematic-open-loop-v1` simulator with normalized
   preview traces, explicit limit diagnostics and collision pre-checks. Do not
   add rigid-body physics or controller behavior.
6. Full 2D/3D authoring workspace: scene layers, actor selection/editing,
   follow/orbit analyst POV, vectors, timeline cursor and provenance.
7. Post-edit frame generation and timestamp-addressable artifacts, plus the
   optional recorded LiDAR evidence layer where local data and calibration are
   approved.
8. CP6 paper evidence bundle from accepted, reproducible results.

The full 2D/3D authoring workspace is unfinished current-MVP work, not a
post-MVP CARLA feature. CARLA same-XOSC execution follows separately as
post-MVP work and must not block the internal MVP simulator or authoring path.

## Non-Negotiable Boundaries

- Do not change Plan A scope without a superseding decision.
- Do not restore CARLA to current MVP acceptance.
- Do not claim same-XOSC runtime without paired logs, traces and hashes.
- Do not call trajectory edits behavior replay.
- Do not treat recorded LiDAR visualization as regenerated sensor output.
- Do not report provisional ADE/FDE/G6/G7 values as final pass/fail claims.
- Do not publish raw nuScenes or nuScenes-derived artifacts.
- Do not treat git-ignored files as technical access control.
- Do not remove historical documentation without reference review and owner approval.

## Completion Protocol

Before handing off:

1. Run focused tests for the changed diagnostic.
2. Run `scripts/check_docs_consistency.py`.
3. Run the full test suite with the documented command.
4. Update `active-work.md`, `project-status.md` and `evidence-index.md` if
   status or claims changed.
5. Write an English report using
   `docs/current/agent-completion-template.md`.
6. State tests, runtime evidence, unverified claims, blockers and the exact next
   action.
7. Confirm that no restricted data or derived artifact was added.

The next agent after this slice is the owner/CP1 follow-up agent. It must receive
the report path, the evidence paths, the preserved baseline and any unresolved
owner decision.
