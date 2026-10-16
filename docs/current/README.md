# Current Context

Read this directory after `MVP&ProjectSummary.md`. These files are the current
project context for agents and future sessions. Start with
`next-agent-handoff.md`.

The nuScenes-devkit backend makeover is **complete** for the approved contracts.
The active track is **acceptance and closure**, not implementation. See
`active-work.md` for the seven acceptance groups and
`../reports/tracks-1-6-disposition.md` for their owners and next actions.

This directory is the status/decision layer, not the complete implementation
reference. For code ownership and wiring, continue with
[`../architecture/system-overview.md`](../architecture/system-overview.md),
[`../architecture/boundary-map.md`](../architecture/boundary-map.md) and the
relevant page under [`../subsystems/`](../subsystems/README.md).

## Status and decisions

- `project-status.md`: checkpoint status, current claims and remaining blockers.
- `active-work.md`: work queue, dependencies and acceptance task groups.
- `next-agent-handoff.md`: current handoff and non-negotiable boundaries.
- `decisions.md`: append-only decision log. Owner decisions are DEC-001
  onward; DEC-017 onward cover the replay baseline and WASM approval.
- `evidence-index.md`: claim-to-evidence index.
- `artifact-policy.md`: visibility and licensing boundaries.
- `technical-contracts.md`: CP1/CP2 and simulator contracts.

## Active work plans

- `viewpanel-makeover-prompt.md`: **inventory and boundary contract for the
  WASM-DATA agent**, whose task is replacing the current view panel with the
  WASM/esmini player. The earlier "restructure the view panel" framing was
  withdrawn as wrong; keep the inventory, discard the cleanup proposal.
- `metric-benchmark-execution-plan.md`: approved near-future CP3 work. Note the
  open blocker: the current baseline is a pooled actor-track micro aggregate and
  scene-macro is still missing, which blocks any threshold proposal.
- `demo-hardening-backlog.md`: public-exposure hardening. S-6 batch cap and
  S-5 pagination remain open.
- `mission-batch-concurrency-benchmark.md`: the S-6 record. Load-bearing — the
  production guide cites it for the open batch-cap risk.
- `product-scene-exposure.md`: scene exposure recommendation.

## Frontend

- `frontend-workspace-handbook.md`: how to run, structure and change the browser
  app under `frontend/`. Subsystem entrypoint is now
  `../subsystems/frontend/README.md`.
- `frontend-workspace-log.md`: frontend work log.
- `ui-motion-editor.md`: motion editor and layer/POV model.
- `ui-mvp-flow-spec.md`: MVP audience, primary user flow, state matrix and
  acceptance criteria.

## Backend

- `nuscenes-devkit-makeover-handoff.md`: authoritative makeover phases and
  boundaries. Phase 1 and Phase 2 are implemented.
- `nuscenes-devkit-leverage-proposal.md`: the original devkit leverage
  proposal; Phase 1 is complete.
- `nuscenes-devkit-optimization-decision.md`: approved cached-adapter
  optimization.
- `backend-workspace-contract-log.md`: backend contract task register.

## CP1 (paused, retained for resumption)

CP1 is `PARTIAL/PROVISIONAL` at the immutable baseline `20/143 = 13.99%` and
owner interpretation is still required. The diagnostic chain is consolidated in
[`../reports/cp1-evidence-lineage.md`](../reports/cp1-evidence-lineage.md).

- `cp1-manual-review-protocol.md`: the governed manual review protocol.

## Future direction

- `platform-direction.md`: multi-dataset/LiDAR platform direction, including the
  restriction on publishing restricted data cited by the security guide.
- `late-future-platform-plan.md`: approved priorities after the current MVP.

## Reference

- `environment-environments.md`: environments and dataset layout.
- `local-artifact-bundles.md`: local/private evidence bundle inventory.
- `pm-agent-guide.md`: guide for agents coordinating scope and evidence.
- `agent-completion-template.md`: completion report template.

## Proposals (not current scope)

- `../proposals/wasm-interactive-simulator/`: expert-supplied planning documents
  and the current handoff. **P0 is complete** and P2 is partial; WASM is
  diagnostic-only at `/wasm-smoke` and deliberately kept out of the view
  registry. See `../proposals/wasm-interactive-simulator/next-agent-handoff.md`.
- `../proposals/post-mvp/`: deferred and post-MVP work — CARLA recorded
  trajectory replay research and the OSM integration proposal. Neither is a
  current assignment.