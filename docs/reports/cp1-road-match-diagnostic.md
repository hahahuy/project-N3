# CP1 Lane Road-Match Diagnostic

## Scope

Add a standalone, deterministic lane-centerline road-match diagnostic over
immutable Scenario trajectories. The diagnostic reports raw per-state,
per-actor and overall rates with distance/heading observations. It does not
emit acceptance pass/fail or alter canonical scenarios.

## Implemented

- Added `lane-road-match-v1` API in `src/real2scenario/road_match.py`.
- Added directed centerline segment projection with clamped projection values.
- Added wrapped heading interpolation/error checks.
- Added deterministic nearest-segment tie-breaking by distance, lane ID and
  segment index.
- Added selected-actor and coordinate-frame validation.
- Added explicit provisional 95% status vocabulary and diagnostic/provisional
  report fields.

## Tests

```text
.venv/bin/python -m pytest -q
169 passed, 2 warnings
```

Focused tests cover exact matching, distance/heading failure reasons, angle
wrapping, deterministic ties, selected actors and frame rejection.
`git diff --check` passed.

## Remaining CP1 Work

- Connect lane records to the external One-North map expansion and scene-0061.
- Add raw external per-state/per-actor evidence and owner review.
- Decide how width/footprint occupancy augments centerline proximity.
- Perform local OpenDRIVE load checks and simulator map-load verification.
- Keep the 95% value provisional; this report emits no scientific pass/fail.

No CP1 acceptance, G3 completion, CP2, CARLA or same-XOSC claim is made.
