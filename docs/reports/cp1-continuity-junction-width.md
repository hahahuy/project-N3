# CP1 Continuity, Junction and Width Diagnostics

## Scope

Extend the CP1 map prototype with additive connectivity continuity diagnostics,
basic connector junction emission and polygon-backed lane-width sourcing. These
features are synthetic-tested and remain engineering diagnostics, not map
fidelity acceptance.

## Implemented

- Connectivity continuity report with reciprocal-link checks, endpoint position
  gaps, heading gaps, tolerances and raw per-edge failures.
- Connector-backed OpenDRIVE junction elements and incoming connection links.
- Polygon area over discretized centerline length as an explicit width source.
- Labeled fallback width remains available when polygon extraction is absent or
  invalid.
- Manifest fields report width source counts and junction count.

## Tests

```text
.venv/bin/python -m pytest -q
165 passed, 2 warnings
```

Synthetic tests cover clean and broken connectivity, junction emission,
polygon-derived width and fallback-compatible builder behavior. `git diff --check`
passed.

## Remaining CP1 Work

- Validate junction semantics against the full One-North connector graph;
  current emission is intentionally conservative and only emits incoming
  connections for connector-backed groups.
- Improve polygon cross-section width estimation beyond area/centerline length.
- Integrate continuity diagnostics with external map output and scene-0061.
- Implement lane-level road-match with raw per-state/actor reporting.
- Verify esmini/CARLA map loading and external map residuals.

No CP1 acceptance, CP2, CARLA or same-XOSC claim is made.
