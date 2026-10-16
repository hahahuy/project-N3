# CP1 Connectivity Continuity Diagnostics

## Scope

Add an additive, deterministic map-only continuity report over nuScenes lane
connectivity. The report checks reciprocal connectivity and compares source
endpoints to target starts for position and heading gaps. It does not change
OpenDRIVE emission or infer accepted junction semantics.

## Implemented

- Added `analyze_connectivity_continuity()`.
- Added configurable resolution, position and heading tolerances.
- Added deterministic edge ordering and raw per-edge failures.
- Reports pass/fail/unsupported edge counts, asymmetric connectivity and gap
  distributions.
- Missing or short geometry is reported as `unsupported`.
- Reports remain `status=diagnostic` and `artifact_visibility=local_private`.

## Tests

```text
.venv/bin/python -m pytest -q
164 passed, 2 warnings
```

Synthetic tests cover clean joins, position/heading failures and asymmetric
connectivity. `git diff --check` passed.

## Remaining CP1 Work

- Define and emit OpenDRIVE junction elements and complete topology links.
- Derive lane widths from polygons with explicit fallback provenance.
- Integrate diagnostics with external One-North map output and scene-0061.
- Implement lane-level road-match and raw per-state reporting.
- Verify map load in esmini/CARLA.

This is not CP1 acceptance, map-fidelity approval, CP2, CARLA or same-XOSC
evidence.
