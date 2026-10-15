# UI Showcase Checkpoint — U0

Status: `SHOWCASE-READY`  
Purpose: demonstrate the review and motion-edit concept before completing the
full simulator/sensor authoring workspace. U0 is not the full 2D/3D authoring
workspace acceptance.

## Goal

Show a reviewer a complete local flow using a sanitized synthetic fixture or an
already-approved local artifact:

```text
select scenario
  -> inspect recorded actors
  -> select one actor
  -> change speed/heading/timing parameters
  -> preview a generated child trajectory
  -> validate and show structured reasons
  -> compare recorded vs generated vs optional esmini replay
  -> inspect provenance and export configuration
```

This checkpoint is a product/UX showcase. It is not CP2 CARLA evidence and does
not require live sensor rendering or OSM activation.

## UI Surface

The showcase should contain:

- scenario catalog;
- selected actor list;
- recorded/generated trajectory distinction;
- parameterized motion editor;
- deterministic seed/config display;
- validation result panel;
- artifact/provenance panel;
- timeline scrubber;
- reset-to-parent action.

Optional layers, if already available locally:

- OSM/reference background labelled `reference only`;
- sensor frame panel labelled `recorded sensor`;
- esmini replay overlay.

## Required Edit Controls

- actor selector;
- speed multiplier;
- heading offset;
- initial gap delta;
- timing offset;
- instantaneous velocity;
- direction vector;
- explicit propagation mode;
- `Preview variant`;
- `Validate`;
- `Reset`;
- `Export config`.

Behavior mode must be visibly disabled with an `unsupported` reason until its
executor exists.

The MVP preview uses the internal kinematic simulator. CARLA is post-MVP and is
not required for U0. Recorded LiDAR point clouds may be shown as a provenance-
labelled evidence layer; they are not regenerated sensor output.

## Current Implementation

The frontend integration is implemented in `frontend/src/App.tsx` and
`frontend/src/api.ts`. It provides actor selection, speed/heading/gap/timing
controls, deterministic seed display, preview/validate/reset/export actions,
generated-path overlay, validation/gate display and a timeline scrubber.
See `docs/reports/wave-3a-ui-implementation.md`.

## Acceptance Criteria

- Parent recorded trajectory remains unchanged after editing.
- Child variant has a stable ID, parent ID, seed and config hash.
- Recorded and generated paths have different visual styles.
- Validation reasons are visible for an intentionally invalid edit.
- Preview can be reset to the parent.
- No raw nuScenes data or derived artifact is committed.
- Showcase can run with a synthetic fixture without CARLA.
- Preview generates trajectory states only; post-edit sensor/image/LiDAR frame
  generation is not part of U0 acceptance.
- A short English report records screenshots/video path, command, tests and
  unverified claims.

The implementation has synthetic-fixture browser evidence in
`docs/evidence/m4-ui/u0-motion-editor-showcase.md`. The standard Compose stack
was subsequently started successfully with the frontend/API ports available,
and the owner confirmed the local runtime flow. Repository-local dependency
ownership was corrected before the standard startup verification.

## Evidence Bundle

```text
docs/evidence/m4-ui/u0-motion-editor-showcase.md
```

The evidence report must include:

- environment and commit;
- startup command;
- fixture identity/hash;
- browser flow;
- expected counts/statuses;
- screenshots or recording path outside the repository when restricted;
- limitations and next checkpoint.

## Exit Decision

U0 may be marked `SHOWCASE-READY` without marking CP2 or CP6 complete. Approval
of U0 authorizes deeper UI implementation; it does not authorize CARLA/map/
behavior claims.
