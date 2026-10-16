# CP1 Corridor Road-Match Attribution Analysis

## Scope

Compare nearest lane candidates for selected `scene-0061` corridor actors
against all One-North centerlines and the 82 selected corridor centerlines.
Existing road-match tolerances and behavior were unchanged.

## Result

- States compared: `143`;
- full-map centerlines: `2,002`;
- corridor centerlines: `82`;
- nearest-lane changes: `0`;
- full-map nearest lanes outside corridor: `0`;
- same nearest-lane rate: `100%`;
- full-map nearest distance mean: `2.6112307 m`;
- full-map nearest distance maximum: `7.2988660 m`.

Private aggregate:

```text
$LOCAL_EVIDENCE_ROOT/corridor-attribution-aggregate.json
```

Detailed raw state comparisons remain private in
`$LOCAL_EVIDENCE_ROOT/corridor-attribution-raw-private.json`.

## Decision

The 40 m corridor crop is not causing the `20/143` (`13.99%`) centerline
road-match result. The same nearest lanes are selected against the full map.
Remaining causes are actor/centerline association, direction/heading semantics,
centerline-versus-footprint interpretation and unsupported actor dimensions.

No thresholds or candidate reassignment policy were changed.

## Non-claims

No CP1 acceptance, G3 completion, lane-boundary correctness, collision safety,
CARLA compatibility, CP2 or same-XOSC equivalence is claimed.
