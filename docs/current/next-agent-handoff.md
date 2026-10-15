# Next Agent Handoff

Status: `READY FOR ACCEPTANCE / OWNER REVIEW`
Primary next work: execute private runtime acceptance and obtain the documented owner decisions

## Mission

The approved backend and Workspace implementation is complete for the current
contracts. Use the available private runtime and official devkit only to produce
acceptance evidence; do not start another makeover or expand scope. The seven
acceptance groups and their exact actions are in
`docs/reports/tracks-1-6-disposition.md`.

Do not restart the old CP1 semantic-alignment handoff, Plan B milestones or CARLA
runtime work. Existing CP1/CP3/CP4/CP5 material is historical or parallel
evidence unless explicitly assigned in `active-work.md`.

## Read In Order

1. `MVP&ProjectSummary.md`
2. `README.md`
3. `docs/current/project-status.md`
4. `docs/current/decisions.md`
5. `docs/current/active-work.md`
6. `docs/current/technical-contracts.md`
7. `docs/current/nuscenes-devkit-makeover-handoff.md`
8. `docs/current/nuscenes-devkit-leverage-proposal.md`
9. `docs/current/evidence-index.md`
10. `docs/current/artifact-policy.md`

For the approved esmini adapter task, also read the live adapter sections in
`docs/current/technical-contracts.md` and `docs/current/backend-workspace-contract-log.md`.

## Current Direction

```text
nuScenes v1.0-trainval
  -> devkit-backed source adapter
  -> canonical scenario and provenance
  -> native map/query capabilities
  -> OpenDRIVE/OpenSCENARIO contracts
  -> native esminiLib adapter and Tier 1 kinematic preview
  -> metrics, gates, private sensor evidence and UI
```

Phase 1 and the additive Phase 2 backend contracts are implemented and tested.
The Workspace authoring and timeline slices are also implemented/tested:
optional CAN ego speed, source-state acceleration/yaw-rate alignment, Tier 1
propagation, native map/query routes, private LiDAR descriptors, actor timeline,
gate timeline, recipe/rollback, lineage, Compare, evidence layers and advisory
prediction metrics. The next task is to finish acceptance and the remaining
renderer/sensor gaps, not redesign those contracts. The bounded live-session
  contract and browser native-state renderer are now implemented; host/Compose
  native execution is verified. Remaining gaps are capability acceptance, private
  capture/display support and owner-gated scientific/paper closure.

## Remaining Work: Acceptance Tracks

1. **Private runtime/browser acceptance:** run scenario-pair creation, polling,
   timeline synchronization, native rendering, step and reset against configured
   private data, recording exact evidence or unavailable reasons.
2. **Native control boundary:** determine whether a compatible public ABI exists;
   otherwise accept `esminiLib_control_abi_unavailable` and label reset-by-reload.
3. **Image capture:** test configured/off-screen capture; retain
   `capture_viewer_unavailable` unless real image artifacts and a manifest exist.
4. **Post-edit sensors:** obtain an owner scope decision; until calibrated frame
   generation is real and verified, keep variant sensors `unsupported`.
5. **CP1/CP3/CP4/CP5 closure:** obtain semantic, benchmark, gate and release
   decisions while preserving the immutable CP1 `20/143 = 13.99%` baseline.
6. **CP6 paper closure:** finalize research questions and evidence bundle without
   promoting provisional engineering diagnostics to scientific claims.
7. **UI scope decision:** keep Behavior, Validate and Replay explicitly disabled
   and classified as deferred/unavailable unless a separate scope is approved.

CARLA same-XOSC remains explicitly post-MVP and is not part of tracks 1-6.

## Approved Live 3D Direction

The approved architecture is a hybrid, not a browser screenshot stream:

```text
Browser React + Three.js/PlayCanvas renderer
  <-> WebSocket state/control protocol
  <-> long-lived native esminiLib session adapter
        -> OpenSCENARIO/OpenDRIVE execution and OSI/state output
```

The browser-native renderer owns interactive roads, actors, cameras, trajectories,
LiDAR/radar overlays and timeline interpolation. The native esmini adapter owns
authoritative scenario stepping, triggers, controllers, road-relative behavior and
simulation state. The existing asynchronous esmini subprocess/capture path remains
for replay, validation and evidence images; it is not the primary live 3D path.

Do not compile the full esmini viewer to WebAssembly or make per-timeline image
capture the first implementation. A reduced WASM port, Unity WebGL client and
WebRTC remote rendering are future alternatives, not current scope.

## Non-Negotiable Boundaries

- Preserve canonical schema until a source-state extension is specified.
- Preserve CP1 `20/143 = 13.99%` and all approved matcher policies.
- Keep raw and nuScenes-derived artifacts outside the repository.
- Never silently substitute CAN, route or LiDAR data for recorded ground truth.
- Keep prediction metrics separate from replay fidelity metrics.
- CARLA same-XOSC remains post-MVP.
- Treat esmini/internal preview POVs and CARLA POVs as separate capability
  statuses; do not claim a rendered POV from a static placeholder.
- Keep variant post-edit sensor frames unsupported until actual frame generation
  exists; expose parent-sweep fallback only with explicit provenance.
- Treat `esminiLib` as the authoritative live simulation adapter; do not expose
  internal transform preview as esmini rendering.
- Keep live adapter sessions bounded, isolated and explicitly versioned with
  XOSC/XODR hashes, timestep and capability status.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

Before handoff, update the active work, project status, evidence index and track
disposition. State exactly which capability is implemented, fallback, unavailable
or unverified. Do not claim completion from tests without runtime evidence and
owner sign-off.

## Short Prompt For The Next Agent

> Execute the seven acceptance groups in
> `docs/reports/tracks-1-6-disposition.md`, starting with the configured private
> browser/runtime walkthrough. Do not redesign the bounded live-session service or
> regenerate sensors without an owner-approved scope. Preserve the separate
> recorded `LIDAR_TOP` evidence view, fail-closed image and variant-sensor states,
> canonical schemas, provisional metric status and CARLA post-MVP boundary. Record
> exact unavailable reasons, owner decisions and release evidence; passing tests
> alone is not project completion.
