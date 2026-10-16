# WASM Interactive Simulator Proposal

Status: `P0 COMPLETE / P2 PARTIAL / RECONCILED 2026-10-16`

> **Reconciliation note.** This directory previously read `P0 NOT STARTED` and
> claimed the repository contained no esminiJS source, build, artifact, Worker
> protocol or renderer. That is now **false**. `frontend/wasm-esmini/` holds the
> build seam and provenance, `frontend/src/wasm-smoke/` is a working browser
> Worker smoke page served at `/wasm-smoke`, and `frontend/src/wasm-playback/`
> holds a Worker protocol plus a Three.js renderer with OrbitControls,
> raycast selection, camera focus tweening and cuboid actors. LiDAR/radar fusion
> and synchronized cross-panel focus are **not** implemented. See
> [`next-agent-handoff.md`](next-agent-handoff.md) for the current state.
>
> The `wasm-playback` view type was **removed** from `VIEW_REGISTRY` and is
> reachable only at `/wasm-smoke`, deliberately decoupled from the workspace.
> The renderer is raw Three.js, **not** react-three-fiber.

This directory stores the two expert-supplied documents for the proposed U5
interactive simulator:

- [`wasm-interactive-simulator-handoff.md`](wasm-interactive-simulator-handoff.md)
- [`interactive-object-selection-analysis.md`](interactive-object-selection-analysis.md)

They are planning inputs, not current contracts. The repository does not yet
contain the esminiJS source, Emscripten build, WASM artifact, Worker protocol or
react-three-fiber renderer described by the proposal.

## Current Reconciliation

The handoff must be read against the current checkout:

### Data Analysis correction

The current analysis supersedes the earlier assumption that `Vertex/@speed`
must be implemented by WASM for native parity. Measurements show native esmini
3.9.0 ignores that extension and adding it to WASM would create a parity gap.
The parity target is `followingMode="position"`, pre-trigger hold and
`AbsoluteTargetSpeed=0`; native esmini remains authoritative for ADE/FDE.

| Handoff claim | Current repository |
|---|---|
| 3D view is only a placeholder | Partly stale. `third-person` and `in-car` already render internal transform/native-state POV views, but not a WASM 3D engine. |
| Add-view blocks non-top-down views | Stale. `AddViewMenu` already offers `third-person`; `MAX_VIEWS` is three. |
| `fetchWorkspaceScenario` points to a missing route | Stale. `GET /api/workspace/scenarios/{scenario_id}` exists and `App` consumes it. |
| Both workspace helpers are dead | Only `fetchWorkspaceDocument` is currently unused; `fetchWorkspaceScenario` is wired. |
| Native replay can be replaced by browser WASM | Rejected. Native `run_esmini()` remains Tier 0 measurement. |
| Live parameter edits work through the engine | Treat as unverified until the selected esminiJS build proves otherwise. |

The canonical artifact serializer already preserves `source_timestamp_us` and
`source_record_token` in state payloads. The web `TrajectoryState` response
models currently omit those fields, so engineering-correlation UI must extend
the web contract rather than assuming the artifact lacks source provenance.

The WASM-pair cache key currently derives only from `scenario_id`. Exporter
semantic changes therefore require pair regeneration or an exporter-version
component in the cache key before trusting a browser artifact.

## Recommended Website Sequence

1. **P0 feasibility spike:** build/load the exact esminiJS commit as an ES
   module in a bare Worker page. Confirm `step_frame`, object states and road
   geometry before changing the existing workspace.
2. **P1 hygiene:** pin existing frontend dependencies, record the selected
   esmini version and add build provenance. Do not add speculative renderer
   dependencies before P0 succeeds.
3. **P2 playback slice:** add a Worker client/protocol and a new playback-only
   view behind a capability flag. It should render road geometry and actor boxes,
   support fixed-step playback/seek, and show the existing template-map warning.
4. **P3 interaction:** add selection and one-shot injection only after playback
   is smooth. Store actions by stable actor identity/name and remap engine IDs
   after reset.
5. **P4 boundary verification:** prove browser frames never enter native replay
   metrics, reports or `replay.csv`; update release and license records.

The first website change should therefore be a capability-gated playback seam,
not a replacement of `ViewPane`, `POVView`, native replay, or existing API
helpers. Keep the current internal POV view as the fallback while the WASM
capability is unavailable.
