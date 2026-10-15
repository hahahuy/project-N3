# Decision Log

This file is append-only. New decisions supersede old ones explicitly; do not
rewrite historical entries.

## DEC-001 — Plan A Baseline

- Status: `APPROVED BASELINE; MVP ACCEPTANCE SUPERSEDED BY DEC-011`
- Plan A: `MVP&ProjectSummary.md`.
- Both esmini and CARLA remain long-term project targets. Current MVP
  acceptance is governed by DEC-011.

## DEC-002 — CP2 Same-XOSC

- Status: `APPROVED`
- The same `.xosc` bytes/hash and declared companion map/XODR hashes must be
  consumed by esmini and CARLA for CP2.
- A direct canonical JSON to CARLA path is feasibility-only, not CP2 evidence.

## DEC-003 — Dataset and Map Area

- Status: `APPROVED WORKING SCOPE`
- Map area: Singapore One-North.
- `scene-0061` is the CP0-CP2 smoke/regression scene.
- Final 5-10 scene benchmark index remains open for owner approval.

## DEC-004 — Metrics and Provisional Gates

- Status: `APPROVED WORKING CONTRACT`
- Raw annotation/ego pose keyframes are ground truth.
- ADE/FDE thresholds remain provisional.
- G6/G7 temporary funnels are allowed for development only.

## DEC-005 — Artifact Boundary

- Status: `APPROVED`
- Source code uses Apache-2.0.
- Raw nuScenes and nuScenes-derived `.xodr`, `.xosc`, trajectories, replay
  traces and visual artifacts remain local/private.

## DEC-006 — OSM Role

- Status: `DEFERRED PROPOSAL / NOT ACTIVE MAKEOVER SCOPE`
- OSM is an auxiliary alignment/reference/visualization layer.
- nuScenes vector map remains the canonical CP1 map source.
- OSM-derived CARLA worlds are feasibility-only unless a future decision says
  otherwise.
- This remains a deferred proposal and is not part of the active nuScenes-devkit
  backend makeover.

## DEC-007 — Execution Order and Backend Boundary

- Status: `HISTORICAL EXECUTION ORDER; MVP BACKEND SCOPE SUPERSEDED BY DEC-011`
- Next section: Wave 3A U0 authoring-compatible backend.
- Then: CP1 map builder/road-match, CP2 same-XOSC CARLA execution, and only
  after those backend contracts stabilize, full UI/sensor/POV authoring.
- Wave 3A may use synthetic or approved local artifacts and does not wait for
  CARLA same-XOSC runtime evidence.
- Full UI must consume backend contracts; it must not duplicate domain rules or
  mutate canonical recorded scenarios.
- This decision does not alter Plan A scope, CP2 same-XOSC, license boundaries,
  or scientific threshold status.

DEC-011 supersedes the simulator acceptance order above: CARLA execution is
post-MVP, while esmini and the internal kinematic preview are the current MVP
execution backends.

## DEC-008 — Scene-Local CP1 Corridor

- Status: `APPROVED WORKING SCOPE`
- Immediate CP1 target is a local corridor around `scene-0061`, selected actors
  and an explicitly declared buffer/topology closure.
- Full Singapore One-North OpenDRIVE coverage is deferred future work.
- The corridor must report raw geometry, continuity and road-match observations
  and must not crop geometry to force a match.

## DEC-009 — Future Map and LiDAR Source Abstraction

- Status: `APPROVED ARCHITECTURE DIRECTION`
- The map-builder boundary must support a normalized map/geometry provider.
- Future LiDAR-derived or independently licensed map sources may be added with
  source frame, provenance, license and geometry-confidence metadata.
- No future source is active for CP1 until its adapter and artifact policy are
  separately reviewed.

## DEC-010 — Late-Future Multi-Dataset Platform

- Status: `APPROVED FUTURE DIRECTION`
- Current MVP remains nuScenes-first with esmini and the internal kinematic
  preview; CARLA is post-MVP under DEC-011.
- After CP1/CP2/CP5 stabilization, add one second dataset adapter; Waymo Open
  Motion is the default candidate for trajectory/canonical validation subject to
  package and license review.
- Choose nuPlan instead only if planning/ego behavior becomes the approved
  research direction. Treat ScenarioNet as a representation/ecosystem unless a
  specific source dataset is selected.
- Do not add multiple datasets or simulators to current acceptance scope.

## DEC-011 — Superseding MVP Simulator Scope

- Status: `APPROVED SUPERSEDING SCOPE`
- CARLA moves from current MVP acceptance to post-MVP.
- Current MVP execution backends are esmini for fidelity evidence and an
  internal lightweight kinematic simulator for authoring/preview.
- Post-MVP CARLA retains the same-XOSC contract and is evaluated separately.

## DEC-012 — MVP Dynamic Object Authoring

- Status: `APPROVED MVP EXPANSION`
- Editable objects include vehicles, pedestrians, cyclists, trajectory-bearing
  actors and movable static objects such as cones/barriers.
- MVP supports instantaneous velocity and segment/trajectory edits.
- Initial direction controls are heading offset and direction vector.
- Drag waypoint and snap-to-lane are later modes.
- Propagation modes are explicit and configurable; behavior remains separate.
- Invalid variants may be saved for debugging but cannot be ranked as valid.

## DEC-013 — MVP Internal Simulator and POV

- Status: `APPROVED MVP EXPANSION`
- Internal simulator is a fixed-timestep kinematic preview engine, not a physics
  engine, autonomy stack or behavior-fidelity claim.
- It supports position, heading, velocity propagation and collision pre-checks.
- MVP POV includes browser 2D/3D, follow/orbit/timeline controls and vectors.
- Recorded LiDAR point clouds may be shown as evidence with source provenance;
  they are not regenerated sensor output or annotation replacement.
- The full 2D/3D authoring workspace is current MVP work. U0 is only the
  showcase checkpoint and does not satisfy the full workspace requirement.
- The workspace must consume the internal simulator/preview trace and preserve
  recorded, generated, replayed and sensor-evidence layers separately.

## DEC-014 — MVP Physics Budget and Runtime Separation

- Status: `APPROVED MVP IMPLEMENTATION POLICY`
- The MVP uses three explicitly separated runtime tiers:
  - Tier 0: kinematic OpenSCENARIO/esmini replay for trajectory-fidelity
    measurement. It is the ADE/FDE measurement instrument and remains open-loop.
  - Tier 1: a dependency-light fixed-timestep internal kinematic preview for
    variant feasibility, G4/G5 checks, collision pre-checks and authoring UI.
  - Tier 2: optional dynamics-adjacent/controller experiments such as
    longitudinal following or bicycle-model lateral propagation, post-MVP and
    diagnostic only.
- Tier 1 uses a versioned profile, initially `kinematic-open-loop-v1`, with a
  fixed timestep of `0.05 s`, explicit acceleration/deceleration/jerk/yaw-rate
  limits and explicit footprint capability status.
- Tier 1 may reject or report a limit violation, but must not silently clamp or
  rewrite an edited trajectory. Any projection/clamp must be an explicit,
  provenance-bearing diagnostic.
- ADE/FDE replay measurement must remain separate from any model used to create
  or filter a variant. A generated variant must be evaluated through the Tier 0
  replay path rather than scored against its own preview model.
- Tier 1 traces must be compatible with `normalized-replay-trace-v2` so the
  evaluator, reports and UI can consume one trace contract.
- nuScenes does not provide steering, tire, suspension or powertrain ground
  truth. Tire-slip, suspension, powertrain, aerodynamic and rigid-body claims
  are outside the MVP and cannot be justified by the current dataset.
- Tier 2 must never be silently represented as trajectory replay or used to
  claim final scientific fidelity. Unsupported controller/behavior modes remain
  fail-closed in the OpenSCENARIO subset.
