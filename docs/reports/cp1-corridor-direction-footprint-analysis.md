# CP1 Corridor Direction and Footprint Analysis

## Scope

Private counterfactual analysis of the three zero-rate selected actors in the
`scene-0061` corridor. Production thresholds, actor selection, lane ranking and
canonical data were unchanged.

## Results

Across `104` states:

- forward centerline matches: `0`;
- reverse-joint rescues: `39`;
- reverse rescue rate: `37.5%`;
- forward distance-valid states: `39`;
- forward heading-valid states: `30`;
- footprint supported states: `104`.

Per actor:

| Actor | States | Forward matches | Reverse joint matches | Lateral/footprint finding |
|---|---:|---:|---:|---|
| `instance-e91...` | 30 | 0 | 0 | mean signed offset `3.167 m`; all 30 outside footprint |
| `instance-e3c...` | 39 | 0 | 39 | mean signed offset `0.201 m`; all 39 occupied; forward heading error `3.138 rad` |
| `instance-fdd...` | 35 | 0 | 0 | mean signed offset `7.134 m`; 22 outside, 13 occupied; reverse heading still above tolerance |

The `instance-e3c...` actor is a strong direction-semantics candidate: spatial
distance passes, forward heading fails by approximately pi, and reversed
heading passes for all states. The other two actors are not explained by a
simple direction reversal; they show large lateral association offsets.

## Decision

Do not reverse centerline directions globally or change the production matcher.
The evidence supports two separate follow-ups:

1. Validate lane-direction/source-yaw semantics for the single reverse candidate
   across additional approved scenes before changing policy.
2. Investigate actor/map association and lane-footprint semantics for the two
   lateral-offset actors.

The corridor remains structurally/runtime verified but scientifically partial.

## Private Evidence

```text
$LOCAL_EVIDENCE_ROOT/corridor-direction-footprint-aggregate.json
$LOCAL_EVIDENCE_ROOT/corridor-direction-footprint-raw-private.json
```

## Non-claims

No lane reversal, CP1 acceptance, G3 completion, collision/occupancy guarantee,
CARLA, CP2 or same-XOSC claim is made.
