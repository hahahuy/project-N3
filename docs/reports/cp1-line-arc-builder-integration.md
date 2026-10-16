# CP1 Line/Arc Builder Integration

## Scope

Integrate the tested pure line/arc fitter behind an explicit builder option,
emit OpenDRIVE constant-curvature arcs, and return deterministic residual
statistics. The existing line-only builder remains the default.

## Implemented

- `build_opendrive_from_nuscenes(..., geometry_mode="line_arc")` is available
  with explicit tolerance configuration.
- `line_arc` emits `<line>` and `<arc curvature="..."/>` geometry from fitted
  segments and uses fitted segment lengths for road length.
- The returned manifest includes geometry mode, fitter version and residual
  segment statistics.
- Default `geometry_mode="line"` remains line-only and reports no residual
  statistics.
- Map loading is isolated behind a testable private loader seam.

## Tests

```text
.venv/bin/python -m pytest -q
162 passed, 2 warnings
```

Synthetic fake-`NuScenesMap` tests verify default compatibility, arc XML,
residual manifest fields and invalid mode rejection. `git diff --check` passed.

## Remaining CP1 Work

- Junction topology/link correctness.
- Polygon-derived lane widths.
- Continuity and lane-level road-match reports.
- Full external One-North map generation and residual review.
- esmini/CARLA map-load evidence.

This remains an engineering prototype and does not claim CP1 map-fidelity
acceptance, CP2, CARLA or same-XOSC completion.
