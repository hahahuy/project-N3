# Next Agent Handoff

Status: `READY FOR IMPLEMENTATION`
Primary next work: finish native runtime integration, sensor generation and acceptance tracks

## Mission

Use the available nuScenes release and official devkit to improve backend source
measurements, native map access, sensor evidence and benchmark inputs. Start with
the authoritative plan in `docs/current/nuscenes-devkit-makeover-handoff.md`.

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

## Remaining Work: Tracks 1-6

1. **Native runtime completion:** preserve the verified host/Compose load-step
   smoke. Reset reloads the confined artifact pair; native control remains
   explicitly unavailable because no stable public ABI is present. A private
   scenario-pair endpoint exposes safe XOSC/XODR artifacts for browser sessions.
2. **Browser live 3D:** complete live-state interaction and visual rendering against
   an actual native session; do not use screenshot streaming as the editor path.
3. **NuScenes evidence view:** add a separate `LIDAR_TOP` multi-sweep view using
   devkit semantics equivalent to `render_sample_data(..., nsweeps=5,
   underlay_map=True)`. Keep the current Top-down view as authoring/map/trajectory;
   include calibration, ego pose, map, sweep offsets, decimation and CAN telemetry
   provenance, and label historical sweep smearing honestly.
4. **Post-edit sensors:** implement or formally scope camera/LiDAR/radar frame
   generation. Until calibrated artifacts exist, keep variant sensor status
   `unsupported` and use only the explicit parent-sweep fallback.
5. **Runtime acceptance:** complete private dataset/browser acceptance with a
   configured esmini capture runtime, retaining fail-closed unavailable states.
6. **Engineering closure:** finish owner-gated CP1 semantic/map review, CP3
   benchmark index/scientific policy, and CP4/CP5 evidence and release sign-off.
7. **Paper closure:** complete CP6 research questions, final evidence bundle and
   reproducibility narrative without promoting provisional metrics to final claims.

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

Before handoff, update the makeover handoff, active work, project status and
evidence index. Add frontend/API/browser tests and state exactly which capability
is implemented, fallback, unavailable or unverified.

## Short Prompt For The Next Agent

> Work through the remaining runtime, evidence-view and closure tracks in
> `docs/current/next-agent-handoff.md`. Read
> `docs/current/next-agent-handoff.md`, `docs/current/technical-contracts.md`, and
> `docs/current/backend-workspace-contract-log.md` first. Replace the assumption
> that esmini is only an asynchronous image/replay subprocess with a bounded native
> `esminiLib` session/service that can load an XOSC/XODR pair, step/pause/reset,
> accept validated control/camera commands, and expose timestamped object state and
> Start with the verified host/Compose native load-step path: finish ABI-scoped
> control/reset behavior and expose a safe scenario artifact-pair flow. Then
> complete browser live 3D, post-edit sensor generation, private runtime acceptance,
> CP1/CP3/CP4/CP5 engineering
> closure, and CP6 paper evidence. The bounded live-session service and browser
> state contract already exist partially. Add the separate nuScenes devkit-style
> `LIDAR_TOP` `nsweeps=5` map-underlay evidence view; do not replace the authoring
> Top-down view. Do not stream screenshots as the editor
> path or claim transform data is an esmini image. Preserve fail-closed behavior,
> private artifacts, canonical schemas, provisional metric status and the CARLA
> post-MVP boundary. Add focused tests and update status/evidence docs. Run the docs
> checker, Python tests, frontend tests and production build. If a track is blocked
> by missing private data or runtime support, record the exact unavailable reason.
