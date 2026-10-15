# Next Agent Handoff

Status: `READY FOR IMPLEMENTATION`
Primary next work: native esmini adapter for live browser 3D state/control

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
  -> esmini and Tier 1 kinematic preview
  -> metrics, gates, private sensor evidence and UI
```

Phase 1 and the additive Phase 2 backend contracts are implemented and tested.
The Workspace authoring and timeline slices are also implemented/tested:
optional CAN ego speed, source-state acceleration/yaw-rate alignment, Tier 1
propagation, native map/query routes, private LiDAR descriptors, actor timeline,
gate timeline, recipe/rollback, lineage, Compare, evidence layers and advisory
prediction metrics. The next task is to finish acceptance and the remaining
renderer/sensor gaps, not redesign those contracts.

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

> Implement the approved live esmini adapter in this repository. Read
> `docs/current/next-agent-handoff.md`, `docs/current/technical-contracts.md`, and
> `docs/current/backend-workspace-contract-log.md` first. Replace the assumption
> that esmini is only an asynchronous image/replay subprocess with a bounded native
> `esminiLib` session/service that can load an XOSC/XODR pair, step/pause/reset,
> accept validated control/camera commands, and expose timestamped object state and
> capability metadata over a WebSocket-friendly backend contract. Keep the browser
> renderer authoritative for live 3D presentation; do not stream screenshots as the
> primary interaction path and do not claim transform data is an esmini image.
> Preserve the existing fail-closed replay/image-capture routes, private artifact
> policy, CARLA post-MVP boundary and canonical schemas. Add focused backend/API
> tests, document runtime limitations, and run the docs checker plus Python tests.
