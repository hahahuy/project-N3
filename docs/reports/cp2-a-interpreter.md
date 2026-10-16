# CP2-A XOSC Interpreter Completion

## Status

`IMPLEMENTED`, `TESTED`, `RUNTIME-VERIFIED ON REAL ARTIFACTS`, `CARLA REMAINS UNVERIFIED`

This slice completes the non-runtime CP2-A slice. The interpreter now resolves
the storyboard of any project XOSC file into an auditable execution plan and is
exercised against real exported scenarios. No CARLA server, controller or
physics mode is involved.

## Scope Boundary

CP2-A is the pure/fake-runtime path: alignment validation, blueprint mapping,
replay grids, exact-pose batches, hash revalidation and orchestration. CARLA
runtime execution, custom map import and the same-XOSC paired run remain
post-MVP and unverified.

## Implemented

`src/real2scenario/xosc_subset.py` adds a strict interpreter
(`r2s-xosc-interpreter-v1`):

- **Entities and Init**: every scenario object must have a unique teleport
  position; missing or duplicated teleports are rejected.
- **Story and Act**: exactly one Act is supported; the Act must have a start
  trigger and the Story must have a stop trigger. A missing stop trigger fails
  closed instead of relying on a simulator default.
- **ManeuverGroup / Event**: exactly one Event per Maneuver, an `EntityRef` that
  matches a declared scenario object, and Polyline trajectories only.
- **Trajectory validity**: vertex times must strictly increase, must not start
  before zero, and the trajectory must have at least one vertex.
- **TimeReference**: `FollowTrajectoryAction` requires an explicit
  `TimeReference/Timing` with a supported domain; the resolved scale and offset
  are reported.
- **Triggers**: only `SimulationTimeCondition` triggers are accepted; other
  conditions (`ReachPositionCondition`, `CollisionCondition`, etc.) are refused
  rather than approximated.
- **Parameter and speed declarations**: only the exporter's own double scalar
  declarations and step, time-based speed dynamics are inside the subset.
- **Execution identity**: the interpretation carries the same XOSC/XODR SHA-256
  identity used by the exact-pose planner, so interpretation and execution
  cannot diverge.
- **Timing edits**: a trajectory that legitimately starts after time zero (for
  example a `timing_offset_s` variant) is accepted and reported with
  `starts_at_zero=false` rather than being rejected as malformed.

`interpret_for_execution()` returns the validated subset scenario together with
the strict interpretation so blueprint mapping, replay planning and exact-pose
batches all reference one resolved file.

## Verification

Focused tests cover: successful interpretation of a full in-subset file; missing
stop triggers; unsupported trigger conditions; a scenario object without a
maneuver group; non-monotonic vertex times; a missing time reference; a declared
but absent map asset; multiple Acts; a timing-shifted trajectory; and the
integration from interpretation to blueprint mapping and exact-pose batches with
physics disabled.

Real artifacts: all 48 exported `.xosc` files from the five-scene provisional
benchmark run interpret cleanly, each with 4 entities, matching the recorded
scenario structure.

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
259 passed, 1 warning (existing Starlette/httpx deprecation).
```

## Explicit Limits

- No live CARLA server was used.
- No sensors, controller or physics mode were implemented.
- No Traffic Manager integration exists.
- Custom XODR CARLA import is still unproven.
- No same-XOSC esmini/CARLA paired run is claimed.
- The CARLA environment decision remains deferred pending reproducible preflight.

## Next Action

CP2 stays post-MVP. The next agent-actionable work is the internal kinematic
simulator and the full 2D/3D authoring workspace; the interpreter contract is
now stable enough for that path to consume.