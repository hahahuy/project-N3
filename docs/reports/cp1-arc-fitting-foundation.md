# CP1 Arc-Fitting Foundation

## Scope

Add a dependency-free, deterministic pure geometry fitter for line and
constant-curvature arc candidates. The existing map builder default remains
line-only; no external nuScenes artifact is generated or committed.

## Implemented

- Added `GeometrySegment` with source indexes, cumulative `s`, pose, length,
  curvature and maximum source-pose residual.
- Added `fit_line_arc_geometry()` with deterministic greedy segmentation.
- Straight paths remain line segments.
- Non-collinear circular paths can emit constant-curvature arc segments.
- Degenerate/invalid geometry configuration fails closed.

## Tests

```text
.venv/bin/python -m pytest -q
159 passed, 2 warnings
```

Focused CP1 tests cover straight paths, known circular arcs, residuals and
invalid fitter configuration. `git diff --check` passed.

## Unverified and Remaining

- The fitter is not yet integrated into `build_opendrive_from_nuscenes()`.
- No residual manifest/report is emitted yet.
- Junction emission, polygon-derived lane widths, continuity, lane-level
  road-match and esmini/CARLA map loading remain open.
- No CP1 map-fidelity acceptance claim is made.
- No CP2, CARLA or same-XOSC claim is made.

## Next Agent

Integrate the fitter behind an explicit `geometry_mode="line_arc"` option,
emit `<arc>` geometry and residual manifest statistics, and preserve the
existing default line mode with regression coverage.
