# CP2-A Pure-Python Replay Contracts

## Scope

Implement the non-runtime CP2-A slice while CARLA remains environment-deferred:
alignment validation, explicit blueprint mapping, deterministic replay grids,
exact-pose batches, hash revalidation and fake-runtime orchestration.

## Implemented

- Added `carla-alignment-v1` immutable alignment artifact and fail-closed
  residual/frame/policy validation.
- Added explicit blueprint mapping records without importing CARLA.
- Added deterministic replay grids with exact endpoint inclusion.
- Added shortest-path yaw interpolation.
- Added exact-pose plan construction requiring XOSC/XODR assets and identities.
- Added execution-time XOSC/XODR hash revalidation.
- Added batched exact-pose commands with physics disabled and one tick per batch.
- Added fake-runtime orchestration tests including cleanup.

## Verification

Focused CP2-A tests cover:

- alignment residual rejection;
- deterministic replay endpoint/grid behavior;
- shortest yaw interpolation across the +/-pi boundary;
- missing map rejection;
- execution hash mismatch;
- fake batch/tick/cleanup ordering;
- physics-disabled command policy.

The full Python suite is the authoritative verification command and remains
required before this slice is closed.

## Explicit Limits

- No live CARLA server was used.
- No sensors were implemented.
- No physics/controller mode was implemented.
- No Traffic Manager integration exists.
- No custom XODR CARLA import was proven.
- No same-XOSC esmini/CARLA paired run is claimed.
- Existing CARLA decision remains `DEFER` pending reproducible environment
  preflight.
