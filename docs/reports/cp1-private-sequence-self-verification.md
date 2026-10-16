# CP1 Private Sequence Self-Verification

## Status

`SELF-VERIFIED`, `DIAGNOSTIC`, `PROVISIONAL`, `NOT ACCEPTANCE EVIDENCE`

This report records a direct exploratory run of the lane-sequence matcher against
the locally accessible private scene-0061 data. It narrows the remaining owner
review but does not change CP1 policy or acceptance status.

## Provenance

```text
dataset: nuScenes v1.0-trainval
scene: scene-0061
scene token: cc8c0bf57f984915a77078b10eb33198
source window: ca9a282c9e77460f8360f564131a8af5:ed5fc18c31904f96a8f0dbb99ff069c0
map: singapore-onenorth
corridor records: 82
corridor buffer: 40 m
topology closure: one_hop_incident_connectivity
coordinate frame: nuscenes_global
actor scope: ego plus three automatic interaction actors
matcher: lane-sequence-match-v1
```

## Immutable Baseline

```text
legacy corridor baseline: 20/143 = 13.99%
all-vehicle baseline: 57.37%
baseline mutation: none
```

The HMM classifications below must not be reported as replacements for these
legacy nearest-lane rates.

## Sequence Results

Across the same 143 selected-scope states:

| Classification | Count |
|---|---:|
| matched high confidence | 29 |
| matched low confidence | 49 |
| ambiguous lane | 12 |
| unmatched topology | 44 |
| direction conflict | 9 |
| unmatched geometry | 0 |

The decoder retained a lane candidate for all 143 states. The sequence-level
diagnostic also reported five geometry validation failures caused by
non-positive centerline segments:

```text
26c04569-f75f-4198-8284-e3a1a5ee9f16
69699cdc-4d68-4bb2-b977-d33b3082cdee
c119fed8-400d-486a-93a0-6738464a3680
ec65b625-ab99-49a2-bd3e-ba1716184c0a
fea4c05c-c4ce-499d-8bd9-9070f080eb70
```

Those defects were subsequently repaired at the map-builder boundary by
`centerline-repair-v1`, which removes duplicate consecutive XY samples without
deleting source records. The 82-record corridor rerun inspected 82 records,
repaired 12, excluded 0, and produced zero remaining sequence geometry
failures. Explicit topology validation checked 80 corridor links with zero
failures.

Per actor:

| Actor | States | High | Low | Ambiguous | Topology | Mean lateral error |
|---|---:|---:|---:|---:|---:|---:|
| ego | 39 | 29 | 0 | 10 | 0 | 0.542 m |
| `instance-e91...` | 30 | 0 | 22 | 0 | 0 | 3.167 m |
| `instance-e3c...` | 39 | 0 | 0 | 0 | 39 | 5.031 m |
| `instance-fdd...` | 35 | 0 | 27 | 2 | 5 | 7.322 m |

## Confirmed Findings

- The actor scope and automatic selection configuration are documented and no
  evidence justifies replacing them with a favorable manual scope.
- The corridor crop is not the low-rate cause; full-map and corridor nearest
  lane assignments were identical for all 143 baseline states.
- `instance-e3c...` remains a strong reverse-direction candidate, but reverse
  direction is counterfactual only and production lane direction is unchanged.
- `instance-e91...` and `instance-fdd...` remain lateral association candidates,
  not simple direction reversals.
- Missing ego dimensions remain unsupported; no dimensions are guessed.
- XODR structural/runtime evidence remains separate from semantic lane correctness.
- The repair rerun does not improve the actor-reference or direction findings;
  it removes geometry defects without changing tolerances or actor policy.

## Remaining Owner Confirmation

No broad visual review is required to establish the current CP1 decision. The
owner only needs to confirm:

1. Retain the automatic four-actor scope.
2. Retain unsupported ego dimensions.
3. Keep reverse matching counterfactual-only.
4. Treat the five non-positive centerline segments and topology-gap states as
   unresolved diagnostic map/topology findings rather than fabricated matches.

If these decisions are accepted, the review can close as diagnostic/provisional
with follow-up engineering work still open. A disagreement with any specific
classification can trigger targeted overlay review for that interval only.

## Decision

The self-verification reduces manual review substantially, but CP1 remains:

```text
PARTIAL / CORRIDOR-EXTERNAL-VERIFIED
```

No CP1 acceptance, G3 completion, lane-direction policy change, final threshold
change, CARLA compatibility or same-XOSC claim is made.
