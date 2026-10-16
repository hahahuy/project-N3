# CP1 External Map and Road-Match Evidence

## Scope

Run the current CP1 builder, continuity diagnostic and lane-centerline
road-match diagnostic against the local private Singapore One-North expansion
and `scene-0061`. Derived XODR and detailed state artifacts were written only
under `$LOCAL_EVIDENCE_ROOT`, outside the repository.

## Environment

- Dataset root: `$NUSCENES_ROOT`
- Dataset version: `v1.0-trainval`
- Map: `singapore-onenorth`
- nuScenes devkit: `1.2.0`
- Python: `3.12.14`
- Evidence directory: `$LOCAL_EVIDENCE_ROOT`
- Map SHA-256: `17939122b940d7faff50fa7ff623ded7f739549a781c32dff1ecd1ac7bebca02`

## Map Builder Aggregate

- Geometry mode: `line`
- Resolution: `5.0 m`
- Roads emitted: `2,002`
- Unsupported geometry paths: `0`
- Width source: polygon for `2,002` roads
- Junction groups emitted: `1,065`
- Structural subset validation: `pass`
- Temporary XODR SHA-256:
  `3734372e15e2b5207ddb2ee3c2a25ea49d5f1d2773f74fdce407f38e994ab700`

The generated XODR was temporary/private and was not committed.

## Connectivity Continuity Aggregate

- Connectivity edges: `2,140`
- Checked edges: `2,132`
- Passing: `2,130`
- Failing: `2`
- Unsupported: `8`
- Asymmetric connectivity edges: `0`
- Maximum observed position gap: `3.138051 m`
- Maximum observed heading gap: `0.348039 rad`
- Status: `diagnostic`

The failures and unsupported edges remain raw diagnostic findings. They do not
establish junction correctness or CP1 acceptance.

## Scene-0061 Road-Match Aggregate

- Scene samples: `39`
- Vehicle candidates: `29`
- Selected actors evaluated: `29`
- Centerlines checked: `2,002`
- States evaluated: `767`
- States matched: `440`
- Raw overall match rate: `0.573664` (`57.37%`)
- Provisional 95% status: `below_95_percent`
- Distance tolerance: `0.5 m`
- Heading tolerance: `0.2 rad`
- Diagnostic status: `diagnostic`
- Scientific status: `PROVISIONAL`

The result is a useful baseline, not a scientific acceptance result. The low
rate may reflect the current global-frame centerline comparison, actor selection
scope, centerline-only matching, heading conventions and/or map/trajectory
alignment. No threshold was changed to improve the result.

## Evidence Files

Aggregate-only private outputs:

- `$LOCAL_EVIDENCE_ROOT/cp1-map-aggregate.json`
- `$LOCAL_EVIDENCE_ROOT/cp1-scene-0061-road-match.json`

## Unverified

- Source-map/XODR overlay agreement.
- Lane-width cross-section/footprint occupancy correctness.
- Full connector junction semantics.
- esmini/CARLA map loading.
- CP1 acceptance or G3 completion.
- CP2, CARLA and same-XOSC execution.

## Next Agent

Investigate frame/alignment and lane-selection causes of the `scene-0061`
57.37% baseline, then add a documented comparison using the approved local
road-aligned transform and selected interaction actors. Keep raw private data
outside the repository and preserve the provisional/no-pass-fail boundary.
