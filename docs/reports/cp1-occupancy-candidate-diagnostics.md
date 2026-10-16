# CP1 Occupancy and Candidate Diagnostics

## Scope

Additive diagnostics for the low `scene-0061` road-match baseline. Existing
`lane-road-match-v1` behavior is unchanged. The new APIs expose nearest
candidate evidence and a separate rectangular vehicle-footprint lateral
occupancy result.

## Implemented

- `lane-road-candidates-v1` reports ranked candidate segments, distances,
  signed lateral offsets, heading errors and tolerance flags.
- `lane-footprint-occupancy-v1` reports occupied/outside/unsupported states
  using lane full width and actor length/width when available.
- Width source is preserved explicitly.
- Missing dimensions or width produce `occupied=None`, never a false failure.
- Existing centerline match fields, status and reason values remain unchanged.

## Tests

```text
.venv/bin/python -m pytest -q
172 passed, 2 warnings
```

Focused tests cover candidate truncation/rank preservation, fallback/width
source, supported occupancy and unsupported actor dimensions.

## Private Scene-0061 Baseline

The selected four-actor scope contained `143` states. Using a constant `3.5 m`
fallback width:

- occupied: `39`
- outside footprint: `65`
- unsupported dimensions/width: `39`
- alternative jointly-valid candidate after a rank-1 failure: `0`

Private aggregate output:

```text
$LOCAL_EVIDENCE_ROOT/cp1-scene-0061-occupancy-candidates.json
```

This does not replace the centerline match rate. Polygon-derived widths and
complete actor dimensions are required for the next external comparison.

## Non-claims

No CP1 acceptance, G3 completion, exact lane-boundary correctness, collision or
drivable-area guarantee, CP2, CARLA or same-XOSC claim is made.
