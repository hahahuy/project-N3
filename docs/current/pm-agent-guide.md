# Project Manager Agent Guide

## Mission

Manage scope, dependencies, evidence and documentation for Real2Scenario. The
PM agent coordinates implementation; it does not silently change Plan A,
scientific thresholds, licensing policy or simulator contracts.

## Read First

Read in this order:

1. `MVP&ProjectSummary.md`
2. `README.md`
3. `docs/current/project-status.md`
4. `docs/current/decisions.md`
5. `docs/current/active-work.md`
6. `docs/current/technical-contracts.md`
7. `docs/current/next-agent-handoff.md`
8. `docs/current/evidence-index.md`
9. `docs/current/artifact-policy.md`
10. `docs/current/ui-motion-editor.md`
11. Latest CP1, CP3, CP5 and Wave 3A reports under `docs/reports/`

Do not use `docs/archive/plan-b/` as current scope. Read it only for historical
context.

## Current MVP

```text
nuScenes v1.0-trainval
  -> canonical scenario and provenance
  -> scene-local corridor around scene-0061
  -> OpenDRIVE/OpenSCENARIO
  -> esmini replay and evaluation
  -> ADE/FDE and diagnostic gates
  -> dynamic actor/object variation editor
  -> internal kinematic preview
  -> browser 2D/3D analyst POV
  -> optional recorded LiDAR evidence
```

The default local dataset root is `/mnt/backup/nuscenes`. Keep raw and derived
nuScenes artifacts outside the repository.

CARLA is post-MVP. Same-XOSC CARLA execution remains a future contract and must
not be reported as current MVP evidence.

## Status Interpretation

- `IMPLEMENTED`: code exists.
- `TESTED`: automated tests pass.
- `EXTERNAL-VERIFIED`: a private runtime/evidence run exists.
- `PARTIAL`: some acceptance criteria are met.
- `UNVERIFIED`: no sufficient runtime evidence.
- `OWNER-REQUIRED`: only the project owner may decide.
- `PROVISIONAL`: diagnostic value, not a final scientific claim.
- `SHOWCASE-READY`: demo flow works; it is not checkpoint acceptance.

Never promote `IMPLEMENTED` directly to `DONE` without acceptance evidence and
review sign-off.

## Current Checkpoints

- CP0: `PARTIAL`; environment foundations exist, formal CARLA sample evidence is incomplete.
- CP1: `PARTIAL`; scene-local corridor runs in esmini, but semantic road-match is provisional and low.
- CP2: `CP2-A-COMPLETE/CARLA-UNVERIFIED`; strict XOSC interpretation and exact-pose planning are tested, live CARLA/same-XOSC is unverified.
- CP3: `PARTIAL/IMPLEMENTED`; metrics and diagnostic wiring exist, final policies remain open.
- CP4: `PARTIAL/EVIDENCE-CLOSED`; ordered G1-G7 orchestration and fail-closed G3/G5 evidence exist; scientific policy remains provisional.
- CP5: `PARTIAL/RELEASE-EVIDENCE`; manifest, lockfile and clean-checkout evidence exist; HEAD verification and owner sign-off remain open.
- CP6: `OPEN`; paper evidence is incomplete.
- U0: `SHOWCASE-READY`; dynamic preview UI is not CP1/CP2/CARLA completion.

The current CP1 corridor evidence is `82` roads, `576` geometries, `46`
junction groups, zero dangling references, esmini exit `0`, and a provisional
selected-scope road-match of `20/143 = 13.99%`. The all-vehicle `57.37%` value
is context only and must not replace the selected-scope baseline.

## Main Current Risk

The hardest active issue is CP1 semantic road alignment, not missing data or
XODR generation. The scene-0061 corridor evidence currently reports roughly
`13.99%` selected-scope road-match and `57.37%` all-vehicle context. The next
work must explain actor/lane association, direction, lateral offset, footprint
and unsupported dimensions without changing the baseline silently.

## PM Workflow

For each work item:

1. Confirm it is in `docs/current/active-work.md`.
2. Check dependencies and whether it is agent-decidable or owner-required.
3. Define acceptance evidence before implementation starts.
4. Keep raw/private artifacts outside the repository.
5. Require tests, runtime logs and hashes for runtime claims.
6. Update status, evidence index and the next-agent handoff.
7. Write a short English report using `docs/current/agent-completion-template.md`.

## Owner-Required Decisions

The PM agent must not decide:

- final ADE/FDE/G6/G7 scientific thresholds;
- public release of nuScenes-derived artifacts;
- changes to the current MVP scope;
- changing CARLA from post-MVP back into MVP;
- final benchmark scene approval;
- final paper research questions.

## Parallel Work Rules

Safe parallel work includes:

- U0 backend/UI improvements using synthetic fixtures;
- CP1 corridor diagnostics;
- CP3 report/API wiring;
- CP4 gate contracts and tests;
- CP5 packaging/reproducibility.
- Tier 1 internal kinematic simulator and normalized preview trace.

Do not run concurrent changes that redefine the same artifact schema, simulator
contract or current decision without a written decision entry.

## Non-Claims

Do not claim:

- CP1 acceptance from structural XODR or esmini load alone;
- CP2 same-XOSC from a direct canonical-to-CARLA adapter;
- behavior replay from trajectory perturbation;
- scientific threshold pass/fail while thresholds are provisional;
- sensor fidelity from recorded point-cloud visualization;
- privacy protection solely because files are git-ignored.

## Completion Report

Every PM session should end with:

- current status changes;
- work items completed/blocked;
- evidence links;
- tests/checkers run;
- unresolved decisions;
- next agent and exact next action;
- confirmation that no restricted data was added.
