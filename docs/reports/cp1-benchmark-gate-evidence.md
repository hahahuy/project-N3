# CP1 Benchmark Candidate Lane Road-Match Evidence (G3 Input)

## Status

`RUNTIME-VERIFIED/DIAGNOSTIC`, `PROVISIONAL`, `CP1 REMAINS PARTIAL/PROVISIONAL`

This slice produces the lane road-match evidence that CP4's G3 gate needs, for
every generated benchmark candidate, and wires it into the batch funnel. It does
not change CP1 policy, the immutable scene-0061 baseline, the matcher
tolerances, the provisional 95% reference or any actor scope.

## What Was Missing

G3 had been fail-closed and correctly `skipped` for every candidate because no
lane road-match evidence existed for benchmark scenarios. The CP1 diagnostics
only covered `scene-0061`, and only the parent trajectory, not generated
candidates.

## Implementation

`scripts/build_benchmark_gate_evidence.py`:

1. rebuilds each benchmark scene's parent scenario in `nuscenes_global`
   coordinates through the cached metadata index;
2. builds the declared scene-local corridor around the parent actor paths
   (`crop_mode=trajectory_corridor`, `buffer_m=40`, `resolution_m=5`,
   `map_name=singapore-onenorth`) and stores the corridor XODR privately;
3. expresses the corridor centerlines in the same local road-aligned frame as
   the generated candidates using the recorded `RoadAlignedTransform`;
4. runs the existing `diagnose_lane_road_match()` per candidate over all
   candidate actors with the unchanged tolerances
   (`max_distance_m=0.5`, `max_heading_error_rad=0.2`);
5. emits `lane-road-match-evidence-v1` records in the gate-evidence format
   consumed by `scripts/run_benchmark_scenes.py --gate-evidence`.

`lane_centerlines_from_opendrive()` was factored out of
`lane_graph_from_opendrive()` so corridor centerlines can be used in emitted
road order, without graph-level direction normalization. That keeps the
comparison against the corridor reference consistent with the immutable CP1
corridor baseline instead of silently reversing lanes.

Frame handling was verified explicitly: the minimum trajectory-to-corridor
distance is identical in the global and local frames (for example `0.194 m` for
`scene-0380`), so the low rates below are a matcher result, not a transform
error.

Nothing in this slice repairs a match, flips a lane, reinterprets ground truth,
extends the corridor to raise a rate, or excludes a candidate.

## Runtime Evidence

Corridor sizes and per-candidate raw match rates over 12 candidates per scene
(grid seed 7, 60 candidates total):

| Scene | Corridor lanes | States per candidate | Mean raw match rate | Max raw match rate |
|---|---|---|---|---|
| scene-0380 | 74 | 132 | 0.0000 | 0.0000 |
| scene-0962 | 138 | 87 | 0.1034 | 0.1264 |
| scene-0945 | 101 | 113 | 0.1593 | 0.3717 |
| scene-0957 | 64 | 164 | 0.2500 | 0.2500 |
| scene-0981 | 81 | 136 | 0.0386 | 0.0441 |

These rates are consistent with the immutable CP1 findings rather than a new
problem: candidate diagnostics show two recurring causes, lanes whose heading is
opposite to the driving direction (heading error near `pi`) and lanes in the
driving direction that are laterally offset by roughly `1-3 m`, beyond the
`0.5 m` tolerance. `scene-0380` matches nothing at all, and its nearest
direction-consistent lane sits about `1.2-2.7 m` from the trajectory.

No tolerance, reference or direction policy was changed to improve these
numbers. They remain `PROVISIONAL`.

## G3 Wiring Result

The same five-scene benchmark was executed twice, once without evidence and
once with this evidence:

```text
without evidence: evaluated G1 48, G2 48, G3  0, G4 60, G5 0, G6 60, G7 60
with evidence:    evaluated G1 48, G2 48, G3 60, G4 60, G5 0, G6 60, G7 60
G3 direct passes: 0 of 60 (below the fixed provisional 0.95 reference)
status counts identical in both runs: 60 generated, 48 valid, 12 invalid, 0 simulator-failed
```

G3 is now evaluated for every candidate instead of skipped for all of them, and
it reports the honest provisional outcome: every candidate fails the reference.
Variant generation, feasibility validation, esmini replay and ADE/FDE values are
unchanged by supplying gate evidence, which is the expected isolation.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
247 passed, 1 warning (existing Starlette/httpx deprecation).
```

## Boundaries

- CP1 stays `PARTIAL/PROVISIONAL`; the immutable `scene-0061` selected-corridor
  baseline `20/143 = 13.99%` is untouched and remains the comparison reference.
- The scene index is agent-selected and unapproved, so this evidence attaches to
  a provisional run.
- Corridors, evidence and manifests remain local/private; nothing derived from
  the dataset was added to the repository.
- G3 stays `PROVISIONAL`; no threshold or acceptance is implied by the gate now
  being evaluated.

## Next Action

Owner interpretation remains required for the direction and lateral-offset
findings. The agent-actionable follow-up is the CP1 reference decomposition
across the benchmark scenes (native, canonical and corridor references per
scene) so the low rates can be attributed per scene rather than inferred from a
single scene.