# CP1 Scene-0061 Corridor External Evidence

## Scope

Private end-to-end run of the declared CP1 corridor contract:

- source map: `singapore-onenorth`;
- source scene: `scene-0061`;
- buffer: `40.0 m`;
- actor scope: ego plus three explicitly selected interaction actors;
- closure: one-hop incident connectivity;
- geometry mode: default `line`, resolution `5.0 m`;
- artifacts: local/private only.

## Corridor Output

- selected initial records: `62`;
- selected closure records: `82` roads total;
- selected connectivity edges checked: `67`;
- XODR geometries: `576`;
- junction groups: `46`;
- dangling junction references: `0`;
- dangling road links: `0`;
- road-length consistency errors: `0`;
- lightweight subset validation: `pass`;
- esmini probe exit: `0`;
- esmini unresolved-junction warnings: `0`.

Private output directory:

```text
$LOCAL_EVIDENCE_ROOT/
```

## Corridor Road-Match

- states evaluated: `143`;
- matched states: `20`;
- raw rate: `13.986%`;
- provisional 95% status: `below_95_percent`;
- selected actors: `4` including ego;
- centerline candidates: `82` selected lane/connector records;
- diagnostic status: `diagnostic`;
- scientific status: `PROVISIONAL`.

Per-actor results:

- ego: `20/39`, `51.282%`;
- selected actor `instance-e91...`: `0/30`;
- selected actor `instance-e3c...`: `0/39`;
- selected actor `instance-fdd...`: `0/35`.

## Corridor Occupancy

Using polygon-derived effective widths for selected corridor records:

- occupied: `52`;
- outside footprint: `52`;
- unsupported dimensions: `39`.

The ego actor has no annotation dimensions in the current ingestion model, so
unsupported occupancy states are retained explicitly rather than assigned
default dimensions.

## Decision

The scene-local corridor is structurally and runtime verified as a private
engineering artifact. CP1 remains `PARTIAL`: the raw corridor road-match rate
is below the provisional reference, occupancy has unsupported states, junction
semantics remain conservative, and CARLA map loading is unverified.

Attribution analysis found the corridor crop is not causing the low rate: all
143 selected-scope states chose the same nearest lane against the full 2,002
centerline map and the 82-lane corridor. See
`docs/reports/cp1-corridor-attribution-analysis.md`.

The additive lane-sequence diagnostic was later self-verified against the same
private scene-0061 data and corridor. It classified the 143 states as 29
high-confidence, 49 low-confidence, 12 ambiguous, 44 topology-gap and 9
direction-conflict states, with five non-positive centerline segments reported
as geometry failures. See
`docs/reports/cp1-private-sequence-self-verification.md`. This exploratory run
does not replace the legacy baseline or establish CP1 acceptance.

Full Singapore One-North coverage is not part of the current scope and remains
deferred.

## Non-claims

No CP1 scientific acceptance, G3 completion, CARLA compatibility, CP2 or
same-XOSC equivalence is claimed.
