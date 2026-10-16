# CP1 Geometry and Topology Follow-Up

## Status

`SELF-VERIFIED`, `DIAGNOSTIC`, `PROVISIONAL`, `OWNER-REVIEW-REQUIRED`

This report records the source-level follow-up after the first private
lane-sequence self-verification. It preserves the immutable nearest-lane
baseline and does not claim CP1 acceptance.

## Baseline

```text
selected corridor nearest-lane baseline: 20/143 = 13.99%
all-vehicle nearest-lane context: 440/767 = 57.37%
provisional target: 95%
```

## Geometry Repair

Implementation: `centerline-repair-v1` in
`src/real2scenario/mapbuilder/__init__.py`.

Policy:

- remove consecutive duplicate XY samples deterministically;
- retain yaw from the surviving source sample;
- exclude only a path that remains collapsed after filtering;
- record source ID, input/remaining pose counts, repair version and reason;
- never silently delete a source map record.

Private corridor result:

```text
records inspected: 82
records repaired: 12
records excluded: 0
before segments: 594
remaining matcher geometry failures: 0
```

The five previously reported records were repaired rather than excluded:

```text
26c04569-f75f-4198-8284-e3a1a5ee9f16
69699cdc-4d68-4bb2-b977-d33b3082cdee
c119fed8-400d-486a-93a0-6738464a3680
ec65b625-ab99-49a2-bd3e-ba1716184c0a
fea4c05c-c4ce-499d-8bd9-9070f080eb70
```

## Topology Validation

`validate_lane_topology()` checks only declared source connectivity. It does not
infer links by nearest geometry. It validates reciprocal incoming/outgoing
references, endpoint gaps, heading discontinuities and invalid link geometry.

Private corridor result:

```text
selected corridor links checked: 80
topology validation failures: 0
```

This validates the available source connectivity representation. It does not
prove that every source lane semantic is complete, that all connector lane links
are legally represented, or that actor motion is supported by the map.

## Actor Reference Convention

The ingestion contract is explicit through `source_reference_convention()`:

```text
trajectory position: sample_annotation.translation_xy
annotation box origin: 3D bounding-box center translation
annotation heading: sample_annotation.rotation yaw
lane reference: map discretized centerline pose
footprint origin: annotation box center when dimensions are available
correction: none
version: source-reference-convention-v1
```

No actor-specific origin correction was applied. This preserves source
trajectory immutability and avoids tuning the three failing actors separately.

## Repaired Sequence Rerun

Selected corridor scope, 143 states:

```text
high confidence:       29
low confidence:        93
ambiguous:              10
topology gap:            0
direction conflict:     11
geometry failures:       0
mean lateral error: 3.979 m
p95 lateral error:  7.365 m
maximum heading error: 2.595 rad
lane switches:           6
topology violations:     0
```

Per actor:

| Actor | States | High | Low | Ambiguous | Direction | Mean lateral | P95 lateral |
|---|---:|---:|---:|---:|---:|---:|---:|
| ego | 39 | 29 | 0 | 10 | 0 | 0.542 m | 1.424 m |
| `instance-e91...` | 30 | 0 | 22 | 0 | 0 | 3.167 m | 3.364 m |
| `instance-e3c...` | 39 | 0 | 39 | 0 | 11 | 5.031 m | 5.031 m |
| `instance-fdd...` | 35 | 0 | 32 | 0 | 0 | 7.333 m | 7.446 m |

The repair removes the previous five geometry failures. Remaining low
confidence and direction evidence is not converted into acceptance.

The old exploratory selected-scope result was 29 high-confidence, 49
low-confidence, 12 ambiguous, 44 topology-gap and 9 direction-conflict states
with five geometry failures. The repaired result is therefore a source-level
comparison, not a threshold comparison: geometry failures changed from 5 to 0
and selected-corridor topology gaps from 44 to 0, while lateral and direction
residuals remain.

## All-Vehicle Diagnostic Context

The repaired full-map rerun evaluated the 767-state all-vehicle scope:

```text
high confidence:       472
low confidence:        147
ambiguous:               63
topology gap:             6
direction conflict:      79
geometry failures:        0
mean lateral error:    1.507 m
p95 lateral error:     5.032 m
maximum heading error: 2.595 rad
lane switches:           26
topology violations:      6
```

These values are sequence diagnostics. They do not replace the all-vehicle
nearest-lane baseline of `440/767 = 57.37%`.

## Remaining Manual Review

Manual review is narrowed to unresolved lateral association for
`instance-e91...` and `instance-fdd...`, reverse/direction semantics for
`instance-e3c...`, annotation/motion heading conflicts, disagreement about the
no-correction actor reference convention, and the six all-vehicle topology-gap
states outside the selected corridor. No broad inspection of all 143 failed
states is required.

## Owner Decisions Required

1. Retain the automatic four-actor interaction scope.
2. Retain unsupported ego dimensions.
3. Keep reverse direction counterfactual-only.
4. Accept the explicit source-reference convention with no actor-specific correction.
5. Treat remaining lateral/direction findings as unresolved diagnostic evidence,
   not reasons to tune thresholds.

## Final Status

```text
CP1 status: PARTIAL / CORRIDOR-EXTERNAL-VERIFIED
scientific status: PROVISIONAL
acceptance claim: no
```

The repair removes the five geometry defects in the matcher input and validates
explicit corridor connectivity, but semantic alignment and actor reference
policy remain below the declared acceptance boundary.
