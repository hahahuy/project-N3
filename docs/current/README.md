# Current Context

Read this directory after `MVP&ProjectSummary.md`. These files are the current
project context for agents and future sessions. Start with
`next-agent-handoff.md`; the nuScenes-devkit makeover is the active implementation
track.

This directory is the status/decision layer, not the complete implementation
reference. For code ownership and wiring, continue with
[`../architecture/system-overview.md`](../architecture/system-overview.md),
[`../architecture/boundary-map.md`](../architecture/boundary-map.md) and the
relevant page under [`../subsystems/`](../subsystems/README.md).

- `project-status.md`: checkpoint status and remaining blockers.
- `active-work.md`: work queue and dependencies.
- `decisions.md`: append-only decision log.
- `technical-contracts.md`: CP1/CP2 and simulator contracts.
- `evidence-index.md`: claim-to-evidence index.
- `artifact-policy.md`: visibility and licensing boundaries.
- `osm-integration-proposal.md`: OSM proposal; not active by default.
- `ui-motion-editor.md`: proposed object motion editor and layer/POV model.
- `ui-mvp-flow-spec.md`: MVP audience, primary user flow, state matrix and
  acceptance criteria; hand-off document for a frontend/UX agent.
- `ui-showcase-checkpoint.md`: lightweight U0 showcase before the unfinished
  full 2D/3D MVP authoring workspace.
- `frontend-workspace-handbook.md`: how to run, structure and change the browser
  app under `frontend/`; retained as a historical/current frontend log. The
  subsystem entrypoint is now `docs/subsystems/frontend/README.md`.
- `wave-3a-backend.md`: completed Wave 3A backend report and historical context;
  current simulator work is defined in `technical-contracts.md` and
  `active-work.md`.
- `platform-direction.md`: future multi-dataset/LiDAR platform direction.
- `late-future-platform-plan.md`: approved priorities after the current MVP.
- `next-agent-handoff.md`: current implementation handoff and non-negotiable
  boundaries.
- `nuscenes-devkit-makeover-handoff.md`: authoritative makeover phases,
  boundaries and next actions.
- `pm-agent-guide.md`: short guide for agents coordinating scope, evidence and dependencies.
- `carla-recorded-trajectory-replay-research.md`: post-MVP CARLA research;
  not a current implementation assignment.
- `cp1-automated-semantic-alignment.md`: HMM/Viterbi lane-sequence matching
  and automated CP1 failure triage to reduce manual review.
- `cp1-semantic-alignment-next-solution.md`: native nuScenes oracle,
  source-to-XODR residual decomposition, and the recommended path beyond the
  remaining lateral-alignment blocker.
- CP1 semantic-alignment files: parallel diagnostic evidence; they are not the
  current next-agent assignment.

## Proposals

- `docs/proposals/wasm-interactive-simulator/`: expert-supplied planning
  documents for a future esmini-WASM playback and interaction slice. The P0
  build feasibility step has not started; these documents do not replace the
  current native replay or workspace contracts.
